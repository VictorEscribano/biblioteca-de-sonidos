#!/usr/bin/env bash
#
# Instalador de la Biblioteca de Sonidos.
#
# Deja el sistema listo: comprueba dependencias, descarga las librerías
# gratuitas de uso comercial, indexa todo e instala el lanzador de escritorio.
#
#   ./install.sh                      # ~20 GB, lo recomendado
#   ./install.sh --budget-gb 5        # instalación ligera
#   ./install.sh --skip-download      # solo indexa lo que ya haya
#   ./install.sh --no-desktop         # sin icono de escritorio
#
set -euo pipefail

BASE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$BASE"

BUDGET_GB=20
CAP_MB=20
DO_DOWNLOAD=1
DO_DESKTOP=1
WORKERS=6

while [ $# -gt 0 ]; do
  case "$1" in
    --budget-gb)    BUDGET_GB="$2"; shift 2 ;;
    --cap-mb)       CAP_MB="$2";    shift 2 ;;
    --workers)      WORKERS="$2";   shift 2 ;;
    --skip-download) DO_DOWNLOAD=0; shift ;;
    --no-desktop)   DO_DESKTOP=0;   shift ;;
    -h|--help)      sed -n '2,12p' "$0" | sed 's/^# \?//'; exit 0 ;;
    *) echo "Opción desconocida: $1"; exit 1 ;;
  esac
done

# ---------- presentación ----------
bold=$(tput bold 2>/dev/null || true)
dim=$(tput dim 2>/dev/null || true)
red=$(tput setaf 1 2>/dev/null || true)
grn=$(tput setaf 2 2>/dev/null || true)
ylw=$(tput setaf 3 2>/dev/null || true)
rst=$(tput sgr0 2>/dev/null || true)

step() { echo; echo "${bold}==> $*${rst}"; }
ok()   { echo "  ${grn}✓${rst} $*"; }
warn() { echo "  ${ylw}!${rst} $*"; }
die()  { echo "  ${red}✗${rst} $*" >&2; exit 1; }

# ---------- 1. dependencias ----------
step "Comprobando dependencias"

command -v python3 >/dev/null || die "Falta python3."
PYV=$(python3 -c 'import sys; print("%d.%d" % sys.version_info[:2])')
python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)' \
  || die "Se necesita Python 3.8 o superior (tienes $PYV)."
ok "python3 $PYV"

if ! command -v ffprobe >/dev/null; then
  echo
  echo "  Falta ${bold}ffmpeg${rst} (aporta ffprobe, que lee la duración y el"
  echo "  formato de cada audio). Instálalo con:"
  echo "     ${dim}Debian/Ubuntu:${rst} sudo apt install ffmpeg"
  echo "     ${dim}Fedora:${rst}        sudo dnf install ffmpeg"
  echo "     ${dim}Arch:${rst}          sudo pacman -S ffmpeg"
  echo "     ${dim}macOS:${rst}         brew install ffmpeg"
  die "Vuelve a ejecutar cuando lo tengas."
fi
ok "ffprobe $(ffprobe -version 2>/dev/null | head -1 | cut -d' ' -f3)"

if ! python3 -c 'import requests' 2>/dev/null; then
  warn "Falta el módulo 'requests'. Instalando…"
  python3 -m pip install --user --quiet requests \
    || die "No se pudo instalar 'requests'. Prueba: python3 -m pip install --user requests"
fi
ok "python-requests"

# ---------- 2. espacio en disco ----------
step "Comprobando espacio en disco"
AVAIL_GB=$(df -BG --output=avail "$BASE" 2>/dev/null | tail -1 | tr -dc '0-9')
if [ -n "${AVAIL_GB:-}" ]; then
  NEED=$((BUDGET_GB + 3))
  if [ "$AVAIL_GB" -lt "$NEED" ]; then
    die "Solo hay ${AVAIL_GB} GB libres y hacen falta ~${NEED} GB.
     Reduce el presupuesto:  ./install.sh --budget-gb $((AVAIL_GB > 8 ? AVAIL_GB - 5 : 3))"
  fi
  ok "${AVAIL_GB} GB libres (se usarán ~${BUDGET_GB} GB)"
fi

mkdir -p library _staging/{freesound,sonniss,kenney,gamesounds,manual} _cache exports

# ---------- 3. descargas ----------
if [ "$DO_DOWNLOAD" -eq 1 ]; then
  step "Descargando packs CC0 de Kenney.nl"
  echo "  ${dim}~750 sonidos de interfaz, impactos y voces. 14 MB. CC0.${rst}"
  python3 tools/dl_kenney.py || warn "Kenney falló; se continúa."

  step "Catalogando el espejo de Sonniss GDC"
  echo "  ${dim}Bundles GDC 2015-2023: royalty-free, comercial, sin atribución.${rst}"
  if [ ! -f _cache/gamesounds_catalog.json ]; then
    python3 tools/crawl_gamesounds.py || die "No se pudo catalogar gamesounds.xyz"
  else
    ok "catálogo ya presente (bórralo para rehacerlo)"
  fi

  step "Descargando sonidos de Sonniss GDC"
  echo "  ${dim}Presupuesto ${BUDGET_GB} GB, tope ${CAP_MB} MB por archivo.${rst}"
  echo "  ${dim}Puedes cortar con Ctrl-C y relanzar: es reanudable.${rst}"
  python3 tools/dl_gamesounds.py \
      --budget-gb "$BUDGET_GB" --cap-mb "$CAP_MB" --workers "$WORKERS" \
    || warn "La descarga terminó con incidencias; se indexa lo que haya."
else
  step "Descargas omitidas (--skip-download)"
fi

# ---------- 4. indexado ----------
step "Indexando la biblioteca"
echo "  ${dim}Deduplica, extrae metadatos, clasifica en 12 categorías y"
echo "  genera index.json y CREDITS.md.${rst}"
python3 tools/build_index.py || die "Falló el indexado."

# ---------- 5. lanzador ----------
if [ "$DO_DESKTOP" -eq 1 ] && [ "$(uname)" = "Linux" ]; then
  step "Instalando el lanzador de escritorio"
  bash tools/install_desktop.sh || warn "No se pudo instalar el lanzador."
fi

chmod +x sonidos tools/*.sh 2>/dev/null || true

# ---------- listo ----------
step "${grn}Instalación completada${rst}"
./sonidos estado 2>/dev/null || true
cat <<EOF

  ${bold}Para abrirla:${rst}
     ./sonidos                    ${dim}# o el icono «Biblioteca de Sonidos»${rst}
     ${dim}luego ve a${rst} http://sfx.localhost:7777

  ${bold}Para añadir más:${rst}
     ${dim}desde la propia app:${rst} botón «Añadir librería»
     ${dim}desde terminal:${rst}     ./sonidos add <zip|carpeta> --vendor "Nombre"

  ${bold}Freesound${rst} ${dim}(opcional, ~1.700 sonidos más en calidad original):${rst}
     python3 tools/dl_freesound.py --setup
     python3 tools/dl_freesound.py --run --budget-gb 5
     ./sonidos index

EOF
