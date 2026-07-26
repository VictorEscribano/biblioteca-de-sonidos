#!/usr/bin/env bash
# Lanzador para el icono de escritorio.
# Arranca el servidor si no esta ya en marcha y abre el navegador.
set -u

BASE="$(cd "$(dirname "$0")/.." && pwd)"
PORT="${SFX_PORT:-7777}"
URL="http://sfx.localhost:${PORT}/"
LOG="$BASE/_cache/serve.log"

cd "$BASE" || exit 1
mkdir -p "$BASE/_cache"

# Sin -S y con stderr silenciado: en arranque en frio el fallo es lo normal,
# no un error que deba salir por pantalla.
is_up() { curl -fs -o /dev/null --max-time 2 \
            "http://127.0.0.1:${PORT}/api/index" 2>/dev/null; }

notify() {
  command -v notify-send >/dev/null && \
    notify-send -a "Biblioteca de Sonidos" -i sfx-library "$1" "${2:-}" 2>/dev/null
}

if ! is_up; then
  if [ ! -f "$BASE/index.json" ]; then
    notify "Falta el índice" "Ejecuta: ./sonidos index"
    exit 1
  fi
  # setsid para que el servidor sobreviva al cierre del lanzador.
  setsid nohup python3 "$BASE/tools/serve.py" --port "$PORT" --no-browser \
    >>"$LOG" 2>&1 < /dev/null &

  for _ in $(seq 1 40); do          # hasta 8 s de margen al arranque
    sleep 0.2
    is_up && break
  done

  if ! is_up; then
    notify "No se pudo arrancar" "Mira $LOG"
    exit 1
  fi
fi

xdg-open "$URL" >/dev/null 2>&1 &
