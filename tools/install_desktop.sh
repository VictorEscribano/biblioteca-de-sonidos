#!/usr/bin/env bash
# Instala el lanzador: entrada de aplicacion (buscable y anclable a favoritos)
# + icono en el escritorio.
set -eu

BASE="$(cd "$(dirname "$0")/.." && pwd)"
APPS="$HOME/.local/share/applications"
ICONS="$HOME/.local/share/icons/hicolor/scalable/apps"
DESKTOP_DIR="$(xdg-user-dir DESKTOP 2>/dev/null || echo "$HOME/Desktop")"
ID="sfx-library"

mkdir -p "$APPS" "$ICONS" "$DESKTOP_DIR"
chmod +x "$BASE/tools/launch.sh"

# El icono va como SVG al tema hicolor: GNOME lo rasteriza solo y asi no hace
# falta ningun conversor instalado.
cp "$BASE/tools/sfx-library.svg" "$ICONS/$ID.svg"

cat > "$APPS/$ID.desktop" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=Biblioteca de Sonidos
GenericName=Efectos de sonido
Comment=Busca, escucha y exporta efectos de sonido para DaVinci Resolve
Exec=$BASE/tools/launch.sh
Icon=$ID
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
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo "Instalado:"
echo "  aplicación : $APPS/$ID.desktop"
echo "  escritorio : $DESKTOP_DIR/$ID.desktop"
echo "  icono      : $ICONS/$ID.svg"
echo
echo "Para anclarlo a favoritos: abre Actividades, busca «Biblioteca de"
echo "Sonidos», clic derecho y «Añadir a favoritos»."
