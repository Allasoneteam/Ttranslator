#!/bin/sh
# Tools for the tests in a fresh Linux cloud session of Claude (Ubuntu/Debian): the app window (WebKitGTK), a virtual
# screen with a window manager, the Windows cross-build and the Python modules of the tests. Safe to run again.
#   bash .claude/cloud_setup.sh
# Go 1.24+ and Chromium for playwright are usually there already (do not run "playwright install": another build
# would not be found).
set -e
SUDO=; [ "$(id -u)" = 0 ] || SUDO=sudo
pkgs="g++ pkg-config libgtk-3-dev libwebkit2gtk-4.1-dev g++-mingw-w64-x86-64 xvfb xauth xdotool imagemagick openbox x11-utils desktop-file-utils"
$SUDO apt-get update -qq
$SUDO env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $pkgs > /dev/null
pip install --break-system-packages -q playwright numpy gguf pefile pillow 2>/dev/null \
  || pip install -q playwright numpy gguf pefile pillow
python3 -c "import playwright, numpy, gguf, pefile, PIL" && echo "python modules: ok"
go version
echo "cloud setup: done — now: bash source/tests/run_all.sh <work-dir> (about 10-20 minutes)"
