#!/usr/bin/env bash
# Crea .deb, .rpm e AppImage a partire da dist/NameReforge (output di PyInstaller).
# Uso: packaging/linux/build_packages.sh <versione> [deb] [rpm] [appimage]   (senza formati: tutti)
# Richiede: fpm (deb, rpm; per l'rpm serve anche il comando `rpm`), appimagetool (AppImage).
set -euo pipefail

cd "$(dirname "$0")/../.."
VERSION="${1:-0.0.0}"; shift || true
VERSION="${VERSION#v}"
[[ "$VERSION" =~ ^[0-9] ]] || VERSION="0.0.0"   # branch o nome non numerico: versione di prova
FORMATS=("$@"); [[ ${#FORMATS[@]} -gt 0 ]] || FORMATS=(deb rpm appimage)

SRC=dist/NameReforge
[[ -x "$SRC/NameReforge" ]] || { echo "manca $SRC: lancia prima PyInstaller" >&2; exit 1; }
ICON=src/nameforge/assets/icon.png
DESKTOP=packaging/linux/nameforge.desktop
OUT=dist
WORK=$(mktemp -d); trap 'rm -rf "$WORK"' EXIT

# Dipendenze di sistema: Qt (xcb) le cerca sulla macchina, non fanno parte del pacchetto PyInstaller.
DEB_DEPS=(libgl1 libegl1 libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1
          libxcb-render-util0 libxcb-shape0 libfontconfig1 libdbus-1-3)
RPM_DEPS=(mesa-libGL mesa-libEGL libxkbcommon-x11 xcb-util-cursor xcb-util-wm xcb-util-image xcb-util-keysyms
          xcb-util-renderutil fontconfig dbus-libs)

stage_tree() {   # /opt/nameforge, /usr/bin/nameforge, .desktop e icona nei percorsi standard
    local root="$WORK/pkgroot"
    rm -rf "$root"
    mkdir -p "$root/opt" "$root/usr/bin" "$root/usr/share/applications" "$root/usr/share/icons/hicolor/256x256/apps"
    cp -a "$SRC" "$root/opt/nameforge"
    ln -s /opt/nameforge/NameReforge "$root/usr/bin/nameforge"
    sed 's|@EXEC@|nameforge|' "$DESKTOP" > "$root/usr/share/applications/nameforge.desktop"
    cp "$ICON" "$root/usr/share/icons/hicolor/256x256/apps/nameforge.png"
    mkdir -p "$root/usr/share/doc/nameforge" && cp LICENSE "$root/usr/share/doc/nameforge/copyright"  # percorso standard del .deb
    echo "$root"
}

fpm_build() {    # $1 = deb|rpm, poi le dipendenze
    local type=$1; shift
    local root; root=$(stage_tree)
    local deps=(); for d in "$@"; do deps+=(--depends "$d"); done
    fpm -s dir -t "$type" -n nameforge -v "$VERSION" -a x86_64 --force \
        --description "Rinomina molti file in una volta, con anteprima e annullamento." \
        --url https://github.com/klode82/NameReforge --maintainer "Aurigalab" --category utils --license MIT \
        "${deps[@]}" -p "$OUT/NameReforge-$VERSION-linux-x86_64.$type" -C "$root" .
}

appimage_build() {
    local app="$WORK/AppDir"
    mkdir -p "$app/usr/lib"
    cp -a "$SRC" "$app/usr/lib/nameforge"
    cat > "$app/AppRun" <<'RUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/lib/nameforge/NameReforge" "$@"
RUN
    chmod +x "$app/AppRun"
    sed 's|@EXEC@|NameReforge|' "$DESKTOP" > "$app/nameforge.desktop"
    cp "$ICON" "$app/nameforge.png"; cp "$ICON" "$app/.DirIcon"
    # --appimage-extract-and-run: serve dove FUSE non c'è (container, CI)
    ARCH=x86_64 appimagetool --appimage-extract-and-run "$app" "$OUT/NameReforge-$VERSION-linux-x86_64.AppImage"
}

for f in "${FORMATS[@]}"; do
    case "$f" in
        deb) fpm_build deb "${DEB_DEPS[@]}" ;;
        rpm) fpm_build rpm "${RPM_DEPS[@]}" ;;
        appimage) appimage_build ;;
        *) echo "formato sconosciuto: $f" >&2; exit 1 ;;
    esac
done
ls -la "$OUT"/NameReforge-"$VERSION"-linux-x86_64.*
