#!/bin/sh
# Rebuilds Ttranslator.exe (Windows) and ttranslator-linux in the parent folder, and the own window
# (ttranslator-window.exe, ttranslator-window-linux; source/window) if its build tools are there.
# Needs Go 1.24 or newer; no external modules. The icon of Ttranslator.exe comes from
# launcher/rsrc_windows_amd64.syso (after changing the drawing: cd launcher && go run make_icon.go).
# The own window needs (Ubuntu/Debian): g++ pkg-config libgtk-3-dev libwebkit2gtk-4.1-dev g++-mingw-w64-x86-64.
set -e
cd "$(dirname "$0")"
rm -rf launcher/ui_fallback
mkdir -p launcher/ui_fallback
cp ../ui/index.html ../ui/tests.txt launcher/ui_fallback/
cd launcher
CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -trimpath -ldflags "-s -w -H windowsgui" -o ../../Ttranslator.exe .
CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -trimpath -ldflags "-s -w" -o ../../ttranslator-linux .
echo "built ../Ttranslator.exe and ../ttranslator-linux"
cd ..
if command -v x86_64-w64-mingw32-g++ >/dev/null; then sh window/build.sh windows; else echo "skipped ttranslator-window.exe: no g++-mingw-w64-x86-64"; fi
if pkg-config --exists gtk+-3.0 webkit2gtk-4.1 2>/dev/null; then sh window/build.sh linux; else echo "skipped ttranslator-window-linux: no libwebkit2gtk-4.1-dev"; fi
