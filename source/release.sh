#!/bin/sh
# Archives of Ttranslator for Windows and Linux, ready to run: unpack anywhere and start Ttranslator.exe
# (ttranslator-linux). Test builds for now: a release on GitHub only after the author's "yes".
#   Ttranslator-<version>-windows-x64.zip, Ttranslator-<version>-linux-x64.tar.gz, SHA256SUMS.txt
# Each holds one folder, Ttranslator/: the programs, ui/, README.txt (installation in English, Russian, German,
# Spanish and Chinese, then the full guide in Russian), README.md (English), LICENSE.txt,
# THIRD-PARTY.txt (the licences of what is compiled in or shipped), start.bat or start.sh, source/ (as in the program
# folder; README.txt describes it) and the llama.cpp engine already unpacked (engine/<os>-amd64/<version>/ with
# engine.json, as the program itself puts it) — so the first start downloads only a model. sherpa-onnx and the voices
# are not inside (author's decision of 21.10.2026): the program downloads them with the first voice.
#
#   sh source/release.sh [out-dir]          (after sh source/build.sh; out-dir: dist/ in the program folder)
#
# BIN_DIR: where the four built programs are (default: the program folder); ENGINE_CACHE: where the engine archives
# are kept (default: <out-dir>/cache; run_all.sh passes its mirror folder). The engine archives are the ones of
# main.go (enginePackageFor: name, size, SHA-256 — read through the test TestDumpReleaseInfo) from github.com.
# Needs: go, python3, curl, zip, unzip, tar, sha256sum.
set -eu
cd "$(dirname "$0")/.."                       # the program folder
APP=$(pwd)
mkdir -p "${1:-dist}"
OUT=$(cd "${1:-dist}" && pwd)
BIN=${BIN_DIR:-$APP}
CACHE=${ENGINE_CACHE:-$OUT/cache}
mkdir -p "$CACHE"
for f in Ttranslator.exe ttranslator-linux ttranslator-window.exe ttranslator-window-linux; do
  [ -s "$BIN/$f" ] || { echo "ERROR: $BIN/$f is missing — build first (sh source/build.sh)"; exit 1; }
done
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

# the version and the engine archives, from main.go
rm -rf source/launcher/ui_fallback; mkdir -p source/launcher/ui_fallback
cp ui/index.html ui/tests.txt source/launcher/ui_fallback/
(cd source/launcher && TDOC_DUMP_RELEASE="$STAGE/release.json" go test -count=1 -run '^TestDumpReleaseInfo$' . > /dev/null) \
  || { echo "ERROR: go test -run TestDumpReleaseInfo"; exit 1; }
field() { python3 -c 'import json, sys; d = json.load(open(sys.argv[1]))
for k in sys.argv[2:]: d = d[k]
print(d)' "$STAGE/release.json" "$@"; }
VERSION=$(field version)
ENGINE_VERSION=$(field engine_version)

fetch() {   # platform → path of the engine archive (pinned size and SHA-256)
  asset=$(field engines "$1" asset); size=$(field engines "$1" size); sha=$(field engines "$1" sha256)
  if ! echo "$sha  $CACHE/$asset" | sha256sum -c --status 2>/dev/null; then
    curl -fsSL -o "$CACHE/$asset.part" "$(field engines "$1" url)" || { echo "ERROR: download of $asset" >&2; exit 1; }
    if [ "$(wc -c < "$CACHE/$asset.part" | tr -d ' ')" != "$size" ] || ! echo "$sha  $CACHE/$asset.part" | sha256sum -c --status; then
      echo "ERROR: $asset: size or SHA-256 differs from main.go" >&2; exit 1
    fi
    mv "$CACHE/$asset.part" "$CACHE/$asset"
  fi
  echo "$CACHE/$asset"
}
WIN_ENGINE=$(fetch windows-amd64)
LINUX_ENGINE=$(fetch linux-amd64)

# the licence of llama.cpp, from its Linux archive (the Windows one has no LICENSE file)
mkdir -p "$STAGE/lic"
tar -xzf "$LINUX_ENGINE" -C "$STAGE/lic" --wildcards '*/LICENSE'
LLAMA_LICENSE=$(find "$STAGE/lic" -name LICENSE | head -1)
[ -s "$LLAMA_LICENSE" ] || { echo "ERROR: no LICENSE in the llama.cpp archive"; exit 1; }

common() {   # folder: what both archives hold
  mkdir -p "$1/ui"
  cp ui/index.html ui/tests.txt "$1/ui/"
  cp README.txt README.md LICENSE.txt "$1/"
  tar -cf - --exclude='source/launcher/ui_fallback' --exclude='__pycache__' --exclude='*.part' source | tar -xf - -C "$1"
  python3 - "$1/THIRD-PARTY.txt" "$APP" "$LLAMA_LICENSE" <<'PY'
import os, sys
out, app, llama = sys.argv[1:4]
def read(p): return open(p, encoding='utf-8').read().strip()
text = [
    "Ttranslator includes these components (their licences below) and downloads others only when you ask.",
    "",
    "1. llama.cpp — the engine in the folder engine (MIT licence):",
    "", read(llama), "",
    "2. webview — compiled into ttranslator-window (MIT licence):",
    "", read(os.path.join(app, "source/window/webview/LICENSE")), "",
    "3. Microsoft Edge WebView2 SDK header — compiled into ttranslator-window.exe:",
    "", read(os.path.join(app, "source/window/webview2/LICENSE.txt")), "",
    "4. The Go standard library — compiled into Ttranslator.exe and ttranslator-linux (BSD-style licence,",
    "   https://go.dev/LICENSE).",
    "",
    "Downloaded only when you ask for them (not in this archive):",
    "- models: Gemma 4 (Google, Apache 2.0); your own .gguf files have their own licences;",
    "- sherpa-onnx for reading aloud (Apache 2.0, with espeak-ng inside, GPL-3.0);",
    "- Piper voices: the licence of each voice is shown in the model menu and in README.txt.",
]
open(out, "w", encoding="utf-8", newline="\r\n").write("\n".join(text) + "\n")
PY
}

engine_into() {   # folder platform archive server-name: unpacked as the program does it, and engine.json
  dest="$1/engine/$2"; mkdir -p "$dest/$ENGINE_VERSION"
  case "$3" in
    *.zip) unzip -q "$3" -d "$dest/$ENGINE_VERSION" ;;
    *) tar -xzf "$3" -C "$dest/$ENGINE_VERSION" ;;
  esac
  server=$(cd "$dest" && find "$ENGINE_VERSION" -type f -name "$4" | head -1)
  [ -n "$server" ] || { echo "ERROR: no $4 in $3"; exit 1; }
  printf '{\n  "version": "%s",\n  "server": "%s"\n}' "$ENGINE_VERSION" "$server" > "$dest/engine.json"
}

# Windows
W="$STAGE/windows/Ttranslator"; mkdir -p "$W"
cp "$BIN/Ttranslator.exe" "$BIN/ttranslator-window.exe" start.bat "$W/"
common "$W"
engine_into "$W" windows-amd64 "$WIN_ENGINE" llama-server.exe
WZIP="Ttranslator-$VERSION-windows-x64.zip"
rm -f "$OUT/$WZIP"
(cd "$STAGE/windows" && zip -q -r -X "$OUT/$WZIP" Ttranslator)

# Linux
L="$STAGE/linux/Ttranslator"; mkdir -p "$L"
cp "$BIN/ttranslator-linux" "$BIN/ttranslator-window-linux" start.sh "$L/"
chmod 755 "$L/ttranslator-linux" "$L/ttranslator-window-linux" "$L/start.sh"
common "$L"
engine_into "$L" linux-amd64 "$LINUX_ENGINE" llama-server
chmod 755 "$L/engine/linux-amd64/$server"
LTGZ="Ttranslator-$VERSION-linux-x64.tar.gz"
rm -f "$OUT/$LTGZ"
(cd "$STAGE/linux" && tar --owner=0 --group=0 -czf "$OUT/$LTGZ" Ttranslator)

(cd "$OUT" && sha256sum "$WZIP" "$LTGZ" > SHA256SUMS.txt && cat SHA256SUMS.txt)
ls -l "$OUT/$WZIP" "$OUT/$LTGZ"
