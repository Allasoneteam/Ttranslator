#!/bin/sh
# Builds the own window of Ttranslator (ttranslator-window) into the program folder:
#   ttranslator-window.exe    Windows (cross-compiled with MinGW-w64, linked statically: no extra DLLs)
#   ttranslator-window-linux  Linux (needs GTK 3 and WebKitGTK 4.1 on the computer where it runs)
#   ttranslator-window        macOS 13.3 or newer (Cocoa and WKWebView; it goes into Ttranslator.app/Contents/MacOS)
# Needs on Ubuntu/Debian: g++ pkg-config libgtk-3-dev libwebkit2gtk-4.1-dev g++-mingw-w64-x86-64; on a Mac: Xcode or
# its Command Line Tools (clang++).
#   sh build.sh            Linux and Windows;   sh build.sh linux   or   sh build.sh windows   one of them
#   sh build.sh macos      on a Mac; ARCH=x86_64 or ARCH=arm64 (default: the Mac's own)
set -e
cd "$(dirname "$0")"
OUT=${OUT:-../..}
what=${1:-all}
if [ "$what" = all ] || [ "$what" = linux ]; then
  # the C++ library stays shared: a static one would need a newer C library (glibc) than many computers have
  g++ -std=c++14 -O2 -s -Wall -Wno-unused-parameter ttranslator-window.cc \
    $(pkg-config --cflags --libs gtk+-3.0 webkit2gtk-4.1) -o "$OUT/ttranslator-window-linux"
  echo "built $OUT/ttranslator-window-linux"
fi
if [ "$what" = all ] || [ "$what" = windows ]; then
  tmp=$(mktemp -d)
  x86_64-w64-mingw32-windres ttranslator-window.rc -O coff -o "$tmp/rsrc.o"
  x86_64-w64-mingw32-g++ -std=c++14 -O2 -s -Wall -Wno-unused-parameter -DWEBVIEW_EDGE -Iwebview2 \
    ttranslator-window.cc "$tmp/rsrc.o" -mwindows -static \
    -ladvapi32 -lole32 -lshell32 -lshlwapi -luser32 -lversion -lcomdlg32 -luuid \
    -o "$OUT/ttranslator-window.exe"
  rm -rf "$tmp"
  echo "built $OUT/ttranslator-window.exe"
fi
if [ "$what" = macos ]; then
  # 13.3: the official llama.cpp builds for macOS need it too (minos of their files)
  clang++ -std=c++14 -O2 -Wall -Wno-unused-parameter -arch "${ARCH:-$(uname -m)}" -mmacosx-version-min=13.3 \
    ttranslator-window.cc -framework Cocoa -framework WebKit -framework UniformTypeIdentifiers \
    -o "$OUT/ttranslator-window"
  echo "built $OUT/ttranslator-window"
fi
