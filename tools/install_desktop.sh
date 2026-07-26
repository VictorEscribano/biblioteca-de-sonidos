#!/usr/bin/env bash
# Instala el lanzador: entrada de aplicacion (buscable y anclable a favoritos)
# + icono en el escritorio.
set -eu

BASE="$(cd "$(dirname "$0")/.." && pwd)"
APPS="$HOME/.local/share/applications"
HICOLOR="$HOME/.local/share/icons/hicolor"
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
ID="sfx-library"

mkdir -p "$APPS" "$HICOLOR/scalable/apps" "$DESKTOP_DIR"
chmod +x "$BASE/tools/launch.sh"

cp "$BASE/tools/sfx-library.svg" "$HICOLOR/scalable/apps/$ID.svg"

# Sin index.theme, gtk-update-icon-cache falla en silencio y el tema local no
# llega a registrarse.
if [ ! -f "$HICOLOR/index.theme" ]; then
  cat > "$HICOLOR/index.theme" <<'THEME'
[Icon Theme]
Name=hicolor
Comment=Fallback icon theme
Directories=scalable/apps,16x16/apps,24x24/apps,32x32/apps,48x48/apps,64x64/apps,128x128/apps,256x256/apps

[scalable/apps]
Size=128
MinSize=8
MaxSize=512
Context=Applications
Type=Scalable
THEME
  for s in 16 24 32 48 64 128 256; do
    cat >> "$HICOLOR/index.theme" <<THEME

[${s}x${s}/apps]
Size=$s
Context=Applications
Type=Fixed
THEME
  done
fi

# PNG en varios tamaños ademas del SVG: algunos entornos no rasterizan SVG en
# el escritorio aunque GTK resuelva el nombre, y con PNG siempre funciona.
python3 - "$BASE/tools/sfx-library.svg" "$HICOLOR" "$ID" <<'PY' 2>/dev/null || \
  echo "  (sin PNG: se usará solo el SVG)"
import sys, os
import gi
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import GdkPixbuf

svg, hicolor, name = sys.argv[1:4]
for size in (16, 24, 32, 48, 64, 128, 256):
    d = os.path.join(hicolor, f"{size}x{size}", "apps")
    os.makedirs(d, exist_ok=True)
    pb = GdkPixbuf.Pixbuf.new_from_file_at_size(svg, size, size)
    pb.savev(os.path.join(d, f"{name}.png"), "png", [], [])
print(f"  PNG generados: 16 a 256 px")
PY

# Icon= con ruta absoluta: no depende de que el tema de iconos resuelva el
# nombre ni de que la cache este al dia.
ICON_ABS="$HICOLOR/256x256/apps/$ID.png"
[ -f "$ICON_ABS" ] || ICON_ABS="$HICOLOR/scalable/apps/$ID.svg"

cat > "$APPS/$ID.desktop" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Biblioteca de Sonidos
GenericName=Efectos de sonido
Comment=Busca, escucha y exporta efectos de sonido para DaVinci Resolve
Exec=$BASE/tools/launch.sh
Icon=$ICON_ABS
Terminal=false
Categories=AudioVideo;Audio;Video;
Keywords=sfx;sonido;audio;efectos;resolve;davinci;biblioteca;
StartupNotify=true
EOF

chmod +x "$APPS/$ID.desktop"
cp "$APPS/$ID.desktop" "$DESKTOP_DIR/$ID.desktop"
chmod +x "$DESKTOP_DIR/$ID.desktop"

# GNOME exige marcar el lanzador como de confianza o muestra "Untrusted".
gio set "$DESKTOP_DIR/$ID.desktop" metadata::trusted true 2>/dev/null || true

update-desktop-database "$APPS" 2>/dev/null || true
gtk-update-icon-cache -f -t "$HICOLOR" 2>/dev/null && echo "  caché de iconos actualizada" || true

echo "Instalado:"
echo "  aplicación : $APPS/$ID.desktop"
echo "  escritorio : $DESKTOP_DIR/$ID.desktop"
echo "  icono      : $ICON_ABS"
echo
echo "Si GNOME sigue mostrando el icono genérico, refresca la shell:"
echo "  killall -HUP gnome-shell     (X11)"
echo "  o cierra sesión y vuelve a entrar (Wayland)"
