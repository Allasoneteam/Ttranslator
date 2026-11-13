#!/bin/sh
# Ttranslator for macOS (1.1): Ttranslator.app and its archive, ready to run. On a Mac: Xcode or its Command Line
# Tools (clang++, codesign, ditto, plutil), Go 1.24+, python3, curl. Test builds for now: a release on GitHub only
# after the author's "yes". GitHub Actions makes both archives (source/ci/macos.sh).
#   Ttranslator-<version>-macos-x64.zip (Intel) or Ttranslator-<version>-macos-arm64.zip (Apple Silicon), and
#   SHA256SUMS-macos-<arch>.txt
# The archive holds one folder, Ttranslator/: Ttranslator.app, README.txt, LICENSE.txt and THIRD-PARTY.txt (author's
# decision: a zip, like the one for Windows). Inside the app — only read; the data are in
# ~/Library/Application Support/Ttranslator (source/launcher/macos.go):
#   Contents/Info.plist                        source/macos/Info.plist with the version (appVersion)
#   Contents/MacOS/Ttranslator                 the launcher (Go)
#   Contents/MacOS/ttranslator-window          the own window (source/window: Cocoa and WKWebView)
#   Contents/Resources/Ttranslator.icns        the icon (source/launcher/make_icon.go)
#   Contents/Resources/ui/                     index.html, tests.txt
#   Contents/Resources/engine/darwin-<arch>/   the official llama.cpp engine, unpacked as the program itself does it
#                                              (<version>/llama-<version>/…, the links between its libraries kept), and
#                                              engine.json — so the first start downloads only a model
# The whole app gets an ad-hoc signature (codesign --sign -): there is no Apple developer signature (author's decision
# of 01.11.2026; README.txt explains the first start). sherpa-onnx and the voices are not inside (author's decision of
# 21.10.2026): the program downloads them with the first voice.
#
#   sh source/release-macos.sh x64|arm64 [out-dir]        (out-dir: dist/ in the program folder)
#
# ENGINE_CACHE: where the engine archives are kept (default: <out-dir>/cache). The engine archive is the one of main.go
# (enginePackageFor: name, size, SHA-256 — read through the test TestDumpReleaseInfo) from github.com.
set -eu
case "${1:-}" in
  x64) GOARCH=amd64; CARCH=x86_64 ;;
  arm64) GOARCH=arm64; CARCH=arm64 ;;
  *) echo "usage: sh source/release-macos.sh x64|arm64 [out-dir]"; exit 2 ;;
esac
ARCH=$1
cd "$(dirname "$0")/.."                       # the program folder
TOP=$(pwd)
mkdir -p "${2:-dist}"
OUT=$(cd "${2:-dist}" && pwd)
CACHE=${ENGINE_CACHE:-$OUT/cache}
mkdir -p "$CACHE"
STAGE=$(mktemp -d)
trap 'rm -rf "$STAGE"' EXIT

# the version and the engine archive, from main.go
rm -rf source/launcher/ui_fallback; mkdir -p source/launcher/ui_fallback
cp ui/index.html ui/tests.txt source/launcher/ui_fallback/
(cd source/launcher && TDOC_DUMP_RELEASE="$STAGE/release.json" go test -count=1 -run '^TestDumpReleaseInfo$' . > /dev/null) \
  || { echo "ERROR: go test -run TestDumpReleaseInfo"; exit 1; }
field() { python3 -c 'import json, sys; d = json.load(open(sys.argv[1]))
for k in sys.argv[2:]: d = d[k]
print(d)' "$STAGE/release.json" "$@"; }
VERSION=$(field version)
ENGINE_VERSION=$(field engine_version)
PLATFORM=darwin-$GOARCH
ASSET=$(field engines "$PLATFORM" asset)
sha256() { shasum -a 256 "$1" | cut -d' ' -f1; }
ENGINE=$CACHE/$ASSET
if [ ! -f "$ENGINE" ] || [ "$(sha256 "$ENGINE")" != "$(field engines "$PLATFORM" sha256)" ]; then
  curl -fsSL -o "$ENGINE.part" "$(field engines "$PLATFORM" url)" || { echo "ERROR: download of $ASSET"; exit 1; }
  if [ "$(wc -c < "$ENGINE.part" | tr -d ' ')" != "$(field engines "$PLATFORM" size)" ] \
     || [ "$(sha256 "$ENGINE.part")" != "$(field engines "$PLATFORM" sha256)" ]; then
    echo "ERROR: $ASSET: size or SHA-256 differs from main.go"; exit 1
  fi
  mv "$ENGINE.part" "$ENGINE"
fi

D=$STAGE/Ttranslator
APP=$D/Ttranslator.app
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources/ui"
sed "s/@VERSION@/$VERSION/g" source/macos/Info.plist > "$APP/Contents/Info.plist"
plutil -lint "$APP/Contents/Info.plist" > /dev/null
printf 'APPL????' > "$APP/Contents/PkgInfo"
(cd source/launcher && CGO_ENABLED=0 GOOS=darwin GOARCH=$GOARCH go build -trimpath -ldflags "-s -w" -o "$APP/Contents/MacOS/Ttranslator" .) \
  || { echo "ERROR: the launcher"; exit 1; }
ARCH=$CARCH OUT="$APP/Contents/MacOS" sh source/window/build.sh macos > "$STAGE/window.log" 2>&1 \
  || { cat "$STAGE/window.log"; echo "ERROR: the window program"; exit 1; }
cp source/launcher/Ttranslator.icns "$APP/Contents/Resources/"
cp ui/index.html ui/tests.txt "$APP/Contents/Resources/ui/"
E=$APP/Contents/Resources/engine/$PLATFORM
mkdir -p "$E/$ENGINE_VERSION"
tar -xzf "$ENGINE" -C "$E/$ENGINE_VERSION"
server=$(cd "$E" && find "$ENGINE_VERSION" -type f -name llama-server | head -1)
[ -n "$server" ] || { echo "ERROR: no llama-server in $ASSET"; exit 1; }
printf '{\n  "version": "%s",\n  "server": "%s"\n}' "$ENGINE_VERSION" "$server" > "$E/engine.json"

# next to the app: the instructions, the licence, the licences of what is inside
cp README.txt LICENSE.txt "$D/"
LLAMA_LICENSE=$(find "$E/$ENGINE_VERSION" -name LICENSE | head -1)
[ -s "$LLAMA_LICENSE" ] || { echo "ERROR: no LICENSE in the llama.cpp archive"; exit 1; }
python3 - "$D/THIRD-PARTY.txt" "$TOP" "$LLAMA_LICENSE" <<'PY'
import os, sys
out, top, llama = sys.argv[1:4]
def read(p): return open(p, encoding='utf-8').read().strip()
text = [
    "Ttranslator.app includes these components (their licences below) and downloads others only when you ask.",
    "",
    "1. llama.cpp — the engine in Ttranslator.app/Contents/Resources/engine (MIT licence):",
    "", read(llama), "",
    "2. webview — compiled into Ttranslator.app/Contents/MacOS/ttranslator-window (MIT licence):",
    "", read(os.path.join(top, "source/window/webview/LICENSE")), "",
    "3. The Go standard library — compiled into Ttranslator.app/Contents/MacOS/Ttranslator (BSD-style licence,",
    "   https://go.dev/LICENSE).",
    "",
    "Downloaded only when you ask for them (not in this archive):",
    "- models: Gemma 4 (Google, Apache 2.0); your own .gguf files have their own licences;",
    "- sherpa-onnx for reading aloud (Apache 2.0, with espeak-ng inside, GPL-3.0);",
    "- Piper voices: the licence of each voice is shown in the model menu and in README.txt.",
]
open(out, "w", encoding="utf-8").write("\n".join(text) + "\n")
PY

# the ad-hoc signature of the whole app — the launcher, the window program and what Contents/Resources holds are
# sealed by it — and its check
codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"

ZIP=Ttranslator-$VERSION-macos-$ARCH.zip
rm -f "$OUT/$ZIP"
(cd "$STAGE" && ditto -c -k --norsrc --noextattr --noqtn --keepParent Ttranslator "$OUT/$ZIP")
(cd "$OUT" && shasum -a 256 "$ZIP" > "SHA256SUMS-macos-$ARCH.txt" && cat "SHA256SUMS-macos-$ARCH.txt")
ls -l "$OUT/$ZIP"
