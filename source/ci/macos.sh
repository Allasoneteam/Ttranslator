#!/usr/bin/env bash
# macOS (1.1) in GitHub Actions — the macos job of .github/workflows/ci.yml runs it on macos-15-intel (x64) and
# macos-15 (arm64). It builds Ttranslator.app and its archive for one architecture and checks them on the runner's Mac
# without a real model:
#   - the unit tests of the launcher on macOS;
#   - source/release-macos.sh: the app (launcher, window program, engine inside, ad-hoc signature) and the zip;
#   - codesign --verify --deep --strict, Info.plist, the minimum macOS of every program inside (macho_minos.py);
#   - the app unpacked from the zip and opened as a user opens it (open, LaunchServices), the data in
#     ~/Library/Application Support/Ttranslator: a tiny test model (make_tiny_gguf.py) is loaded by the engine of the
#     app, /api/state answers, a translation goes through the engine (the answer is gibberish: the chain matters), the
#     own window opens and shows the page (screenshot), a voice — sherpa-onnx and one Piper voice, downloaded by the
#     program itself from GitHub — reads a phrase into a WAV file, «Выход» closes everything;
#   - macOS protection: the zip marked as downloaded (quarantine), unpacked with the mark on every file (as Archive
#     Utility does), the start allowed as the user allows it; the app must then start the engine and the window.
# Everything for the run's artifacts goes into <out-dir> (archive, SHA256SUMS, screenshots, WAV, logs, results);
# MACZIP=<archive> goes into $GITHUB_ENV, so that the archive is uploaded as itself.
#   bash source/ci/macos.sh x64|arm64 <out-dir>
set -u
ARCH=${1:?x64 or arm64}
mkdir -p "${2:?out-dir}"
OUT=$(cd "$2" && pwd)
cd "$(dirname "$0")/../.."
TOP=$(pwd)
W=${RUNNER_TEMP:-${TMPDIR:-/tmp}}/ttmac-$ARCH
rm -rf "$W"; mkdir -p "$W"
RES=$OUT/results-$ARCH.txt; : > "$RES"
DATA="$HOME/Library/Application Support/Ttranslator"
PORT=8765
U=http://127.0.0.1:$PORT

say() { printf '\n=== %s\n' "$*"; }
ok() { echo "OK   $*" | tee -a "$RES"; }
fail() { echo "FAIL $*" | tee -a "$RES"; echo "::error::$ARCH: $*"; }
check() { if [ "$1" = 0 ]; then ok "$2"; else fail "$2"; fi; }   # status message
summary() {
  say "results ($ARCH)"; cat "$RES"
  n=$(grep -c '^FAIL' "$RES")
  if [ "$n" = 0 ]; then echo "ALL MAC CHECKS PASSED"; else echo "FAILED MAC CHECKS: $n"; fi
  [ "$n" = 0 ]
}
state() { curl -s -m 10 "$U/api/state"; }
# a value from /api/state: a Python expression over s (the state as a dict)
st() { state | python3 -c 'import json, sys
try: s = json.load(sys.stdin)
except Exception: print(""); sys.exit()
print(eval(sys.argv[1]))' "$1" 2>/dev/null; }
wait_until() {       # seconds python-expression: waits until st(expression) prints True
  local i
  for i in $(seq 1 "$1"); do
    [ "$(st "$2")" = True ] && return 0
    sleep 1
  done
  return 1
}
# a running program, by the path in its command line (the process name of ttranslator-window is cut to 16 letters)
running() { pgrep -f "/$1"'( |$)' > /dev/null; }
shot() { screencapture -x "$OUT/$1.png" 2>/dev/null && echo "screenshot: $1.png"; }
quit_app() {         # «Выход»: the launcher stops the engine, closes the window and exits
  curl -s -m 10 -o /dev/null -X POST -H "Origin: $U" "$U/api/quit"
  local i
  for i in $(seq 1 20); do
    running Ttranslator || running ttranslator-window || running llama-server || return 0
    sleep 1
  done
  return 1
}
save_logs() { mkdir -p "$OUT/logs-$1"; cp "$DATA"/data/logs/*.log "$OUT/logs-$1/" 2>/dev/null; curl -s -m 10 "$U/api/state" > "$OUT/logs-$1/state.json"; }
limit() { perl -e 'alarm shift; exec @ARGV' "$@"; }   # seconds command...: macOS has no timeout(1)

say "the Mac of the runner"
{ sw_vers; uname -m; sysctl -n machdep.cpu.brand_string; echo "memory: $(( $(sysctl -n hw.memsize) / 1073741824 )) GB"
  xcodebuild -version 2>/dev/null | head -1; clang++ --version | head -1; go version; python3 --version
  echo "Gatekeeper: $(spctl --status 2>&1)"; echo "SIP: $(csrutil status 2>&1)"; } | tee "$OUT/mac-$ARCH.txt"
MACOS=$(sw_vers -productVersion)

say "unit tests of the launcher on macOS"
(cd source/launcher && rm -rf ui_fallback && mkdir ui_fallback && cp ../../ui/index.html ../../ui/tests.txt ui_fallback/ \
  && go vet ./... && go test -count=1 ./...) > "$OUT/unit-tests-$ARCH.log" 2>&1
r=$?; tail -5 "$OUT/unit-tests-$ARCH.log"; [ $r = 0 ] || tail -40 "$OUT/unit-tests-$ARCH.log"
check $r "unit tests of the launcher on macOS $MACOS"

say "Ttranslator.app and the archive (source/release-macos.sh)"
if ! ENGINE_CACHE="$W/cache" sh source/release-macos.sh "$ARCH" "$OUT" > "$OUT/build-$ARCH.log" 2>&1; then
  tail -40 "$OUT/build-$ARCH.log"; fail "build of Ttranslator.app and the archive"; summary; exit 1
fi
tail -3 "$OUT/build-$ARCH.log"
ZIP=$(cd "$OUT" && ls Ttranslator-*-macos-"$ARCH".zip | head -1)
ok "build: $ZIP ($(( $(stat -f %z "$OUT/$ZIP") / 1048576 )) MB)"
[ -n "${GITHUB_ENV:-}" ] && echo "MACZIP=$ZIP" >> "$GITHUB_ENV"
rm -rf "$OUT/cache"

say "the archive: contents, signature, minimum macOS"
ditto -x -k "$OUT/$ZIP" "$W/plain"
APP=$W/plain/Ttranslator/Ttranslator.app
ls "$W/plain/Ttranslator"
for f in README.txt LICENSE.txt THIRD-PARTY.txt Ttranslator.app/Contents/Info.plist Ttranslator.app/Contents/MacOS/Ttranslator \
         Ttranslator.app/Contents/MacOS/ttranslator-window Ttranslator.app/Contents/Resources/Ttranslator.icns \
         Ttranslator.app/Contents/Resources/ui/index.html Ttranslator.app/Contents/Resources/ui/tests.txt; do
  [ -s "$W/plain/Ttranslator/$f" ] || { fail "the archive has no $f"; }
done
E=$(ls -d "$APP"/Contents/Resources/engine/darwin-*)
server=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["server"])' "$E/engine.json")
[ -x "$E/$server" ]; check $? "the engine inside the app: $(basename "$E")/$server"
links=$(find "$E" -type l | wc -l | tr -d ' ')
[ "$links" -gt 5 ] && [ -e "$(dirname "$E/$server")/libllama.dylib" ]; check $? "the links between the engine's libraries are kept ($links)"
codesign --verify --deep --strict --verbose=2 "$APP" > "$OUT/codesign-$ARCH.txt" 2>&1
r=$?; cat "$OUT/codesign-$ARCH.txt"; check $r "codesign --verify --deep --strict"
codesign -dv --verbose=2 "$APP" >> "$OUT/codesign-$ARCH.txt" 2>&1
grep -q 'Signature=adhoc' "$OUT/codesign-$ARCH.txt"; check $? "ad-hoc signature of the app"
plutil -p "$APP/Contents/Info.plist" > "$OUT/Info-$ARCH.plist.txt"
plist() { plutil -extract "$1" raw -o - "$APP/Contents/Info.plist" 2>/dev/null; }
[ "$(plist LSMinimumSystemVersion)" = 13.3 ] && [ "$(plist LSUIElement)" = true ] && [ "$(plist CFBundleExecutable)" = Ttranslator ] \
  && [ "$(plist CFBundleShortVersionString)" = "$(echo "$ZIP" | sed 's/^Ttranslator-//; s/-macos-.*//')" ]
check $? "Info.plist: LSMinimumSystemVersion $(plist LSMinimumSystemVersion), LSUIElement $(plist LSUIElement), version $(plist CFBundleShortVersionString)"
python3 -I .claude/tools/macho_minos.py "$APP" | tee "$OUT/minos-$ARCH.txt"
python3 - "$OUT/minos-$ARCH.txt" <<'PY'
import re, sys
bad = [l for l in open(sys.argv[1]) if (m := re.search(r'minos (\d+)\.(\d+)', l)) and (int(m[1]), int(m[2])) > (13, 3)]
sys.exit(1 if bad else 0)
PY
check $? "every program inside runs on macOS 13.3 or newer (minos)"

# The Intel Mac also builds the app for Apple Silicon (Go and clang build for both): a check of that build — signature,
# architecture, minimum macOS — that does not depend on an arm64 machine of GitHub (on 02.11.2026 the jobs of macos-15
# waited 15 minutes for one and were cancelled). It is not started here; the arm64 job starts and checks its own build.
if [ "$ARCH" = x64 ]; then
  say "the app for Apple Silicon, built on the Intel Mac (not started)"
  X=$OUT/arm64-built-on-intel
  if ENGINE_CACHE="$W/cache-arm64" sh source/release-macos.sh arm64 "$X" > "$X.log" 2>&1; then
    rm -rf "$X/cache-arm64" "$W/x-arm64"; ditto -x -k "$X"/Ttranslator-*-macos-arm64.zip "$W/x-arm64"
    XAPP=$W/x-arm64/Ttranslator/Ttranslator.app
    codesign --verify --deep --strict "$XAPP" 2>/dev/null \
      && lipo -archs "$XAPP/Contents/MacOS/Ttranslator" | grep -qx arm64 \
      && lipo -archs "$XAPP/Contents/MacOS/ttranslator-window" | grep -qx arm64 \
      && [ -x "$XAPP/Contents/Resources/engine/darwin-arm64/$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["server"])' "$XAPP/Contents/Resources/engine/darwin-arm64/engine.json")" ] \
      && ! python3 -I .claude/tools/macho_minos.py "$XAPP" | grep -Eq 'minos (1[4-9]|[2-9][0-9])\.|minos 13\.([4-9]|[1-9][0-9])'
    check $? "the arm64 app builds on the Intel Mac: signature, arm64 programs, the engine for Metal, minos ≤ 13.3 ($(ls "$X" | grep -m1 zip))"
  else
    tail -20 "$X.log"; fail "the arm64 app does not build on the Intel Mac"
  fi
fi

say "the data folder and a tiny test model"
pip install -q numpy gguf > /dev/null 2>&1
rm -rf "$DATA"; mkdir -p "$DATA/models"
python3 source/tests/make_tiny_gguf.py "$DATA/models/tiny-test.gguf" 1 6 > /dev/null
printf '{"ui_language": "ru", "active_model": "file:tiny-test.gguf", "ui_port": %s}\n' "$PORT" > "$DATA/config.json"
[ -s "$DATA/models/tiny-test.gguf" ]; check $? "tiny test model in ~/Library/Application Support/Ttranslator/models"

say "the app opened as a user opens it (open)"
open "$APP" || echo "open: exit code $?"
for i in $(seq 1 60); do curl -sf -m 2 -o /dev/null "$U/api/ping" && break; sleep 1; done
curl -sf -m 5 "$U/api/ping"; check $? "the launcher answers (/api/ping)"
[ "$(st 's["platform"]')" = darwin ] && [ "$(st 's["data_root"]')" = "$DATA" ]
check $? "/api/state: platform darwin, data folder $(st 's["data_root"]')"
wait_until 240 's["phase"] == "ready"'; check $? "the engine of the app loads the model (phase $(st 's["phase"]'))"
grep -q "starting engine: .*Ttranslator.app/Contents/Resources/engine/darwin-" "$DATA/data/logs/launcher.log"; check $? "the engine runs from inside the app"
st 's["engine_info"]'
reply=$(curl -s -m 120 -H 'Content-Type: application/json' -d '{"messages":[{"role":"user","content":"Translate into English: Привет, мир"}],"max_tokens":16,"temperature":0}' "$U/v1/chat/completions")
echo "$reply" | head -c 400; echo
echo "$reply" | python3 -c 'import json, sys; d = json.load(sys.stdin); sys.exit(0 if d["choices"][0]["message"] is not None else 1)'
check $? "a translation request goes through the launcher to the engine and back"
wait_until 60 's["window"]["pages"] >= 1 and s["window"]["error"] == ""'
check $? "the own window opened and shows the page (pages $(st 's["window"]["pages"]'), error '$(st 's["window"]["error"]')')"
running ttranslator-window; check $? "the window program runs"
sleep 5; shot "window-$ARCH"
cat > "$W/windows.swift" <<'SWIFT'
import AppKit
import CoreGraphics
let list = CGWindowListCopyWindowInfo([.optionOnScreenOnly, .excludeDesktopElements], kCGNullWindowID) as? [[String: Any]] ?? []
for w in list where (w[kCGWindowLayer as String] as? Int ?? 1) == 0 {
  let b = w[kCGWindowBounds as String] as? [String: Any] ?? [:]
  print("window\t\(w[kCGWindowOwnerName as String] ?? "")\t\(b["X"] ?? 0) \(b["Y"] ?? 0) \(b["Width"] ?? 0) \(b["Height"] ?? 0)")
}
if let s = NSScreen.main { print("screen\t\(Int(s.frame.width)) \(Int(s.frame.height))\tvisible \(Int(s.visibleFrame.width)) \(Int(s.visibleFrame.height))") }
SWIFT
swift "$W/windows.swift" > "$OUT/windows-$ARCH.txt" 2>&1; cat "$OUT/windows-$ARCH.txt"
python3 - "$OUT/windows-$ARCH.txt" <<'PY'
import sys
lines = [l.rstrip('\n').split('\t') for l in open(sys.argv[1])]
wins = [l for l in lines if l[0] == 'window']
scr = [l for l in lines if l[0] == 'screen']
if not wins or not scr: sys.exit(1)
front = wins[0]
w, h = (float(x) for x in front[2].split()[2:4])
vw, vh = (float(x) for x in scr[0][2].split()[1:3])
print('front window:', front[1], w, h, '— visible screen:', vw, vh)
sys.exit(0 if front[1] in ('Ttranslator', 'ttranslator-window') and w >= vw - 2 and h >= vh - 40 else 1)
PY
check $? "the window is in front and fills the screen (start_maximized)"

say "a voice: sherpa-onnx and the voice LJSpeech, downloaded by the program from GitHub"
curl -s -m 10 -H 'Content-Type: application/json' -d '{"id": "en-ljspeech"}' "$U/api/voice"; echo
wait_until 600 's["tts"]["engine"]["present"] and not s["tts"]["download"]["active"] and any(v["id"] == "en-ljspeech" and v["present"] for v in s["tts"]["voices"])'
check $? "sherpa-onnx $(st 's["tts"]["engine"]["version"]') and the voice downloaded and unpacked (error: '$(st 's["tts"]["download"]["error"]')')"
code=$(curl -s -m 90 -o "$OUT/voice-$ARCH.wav" -w '%{http_code}' -H 'Content-Type: application/json' \
  -d '{"lang": "en", "text": "Hello! Ttranslator reads this sentence aloud on a Mac.", "speed": 1}' "$U/api/tts")
if [ "$code" = 200 ] && [ "$(head -c 4 "$OUT/voice-$ARCH.wav")" = RIFF ]; then
  ok "the voice reads a phrase into a WAV file ($(( $(stat -f %z "$OUT/voice-$ARCH.wav") / 1024 )) KB, macOS $MACOS)"
else
  echo "answer $code: $(head -c 600 "$OUT/voice-$ARCH.wav")"; mv "$OUT/voice-$ARCH.wav" "$OUT/voice-error-$ARCH.txt"
  fail "the voice did not read the phrase on macOS $MACOS"
fi
# «Открыть папку данных» (settings, model menu): Finder shows the data folder
curl -s -m 10 -o /dev/null -X POST -H "Origin: $U" -H 'Content-Type: application/json' -d '{"what": "root"}' "$U/api/open"
sleep 3; swift "$W/windows.swift" > "$W/windows-after-open.txt" 2>&1
grep -q "^window	Finder	" "$W/windows-after-open.txt"; check $? "«Открыть папку данных» opens the data folder in Finder"
shot "data-folder-$ARCH"
save_logs "plain-$ARCH"
quit_app; check $? "«Выход»: the launcher, the engine and the window program have ended"
# where WKWebView keeps the data of the page (README.txt: uninstalling)
ls -d "$HOME"/Library/WebKit/*ttranslator* "$HOME"/Library/Caches/*ttranslator* 2>/dev/null | tee "$OUT/webkit-data-$ARCH.txt"

say "the voice program and the minimum macOS of its libraries (for the report: not a check)"
TTSJSON=$(ls "$DATA"/engine/darwin-*/tts.json 2>/dev/null | head -1)
if [ -n "$TTSJSON" ]; then
  TTSEXE=$(dirname "$TTSJSON")/$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["exe"])' "$TTSJSON")
  TTSDIR=$(dirname "$(dirname "$TTSEXE")")
  python3 -I .claude/tools/macho_minos.py "$TTSDIR" | tee "$OUT/minos-sherpa-$ARCH.txt"
  # what the onnxruntime of sherpa-onnx takes from macOS that macOS 13 does not have: CoreML classes and std::pmr of
  # libc++ (strong imports — the library does not load without them); their availability, from the SDK
  dyld_info -imports "$TTSDIR/lib/libonnxruntime.dylib" 2>/dev/null | grep -E "MLComputePlan|MLOptimizationHints|pmr" \
    | tee "$OUT/onnxruntime-imports-$ARCH.txt"
  SDK=$(xcrun --show-sdk-path 2>/dev/null)
  grep -h -B3 -E "^@interface (MLComputePlan|MLOptimizationHints)\b" "$SDK"/System/Library/Frameworks/CoreML.framework/Headers/*.h 2>/dev/null \
    | grep -E "@interface|API_AVAILABLE" | tee -a "$OUT/onnxruntime-imports-$ARCH.txt"
  grep -h -E "AVAILABILITY_HAS_PMR|// LLVM 16|VERSION_MIN_REQUIRED__ < 140000" "$SDK"/usr/include/c++/v1/__configuration/availability.h \
    2>/dev/null | head -6 | tee -a "$OUT/onnxruntime-imports-$ARCH.txt"
  # what dyld does with a library built for a newer macOS than the running one: the same library with its minimum
  # version set to 99.0 (vtool), signed again
  rm -rf "$W/sherpa-newer"; cp -R "$TTSDIR" "$W/sherpa-newer"
  ORT=$W/sherpa-newer/lib/libonnxruntime.dylib
  if vtool -set-build-version macos 99.0 99.0 -replace -output "$ORT.new" "$ORT" > /dev/null 2>&1; then
    mv "$ORT.new" "$ORT"; codesign --force --sign - "$ORT" > /dev/null 2>&1
    echo "libonnxruntime.dylib with minos 99.0 on macOS $MACOS:" | tee "$OUT/dyld-newer-$ARCH.txt"
    "$W/sherpa-newer/bin/$(basename "$TTSEXE")" --help 2>&1 | head -5 | tee -a "$OUT/dyld-newer-$ARCH.txt"
  fi
  # a candidate for the author (not used by the program): sherpa-onnx v1.13.8, the last release before 2.0 (which
  # removed espeak-ng), whose onnxruntime is built for macOS 11 / 10.15 — does it read the same voice?
  C=sherpa-onnx-v1.13.8-osx-universal2-shared
  if curl -fsSL -o "$W/$C.tar.bz2" "https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.13.8/$C.tar.bz2" \
     && [ "$(shasum -a 256 "$W/$C.tar.bz2" | cut -d' ' -f1)" = 2249f97f10df7d828af1b0d10e3d1eeaa2198b60b9a999a7ed853c150181ccfd ]; then
    tar -xjf "$W/$C.tar.bz2" -C "$W"
    python3 -I .claude/tools/macho_minos.py "$W/$C/lib" | tee "$OUT/minos-sherpa-1.13.8-$ARCH.txt"
    V=$DATA/models/voices/vits-piper-en_US-ljspeech-medium
    (cd "$DATA/models/voices" && "$W/$C/bin/sherpa-onnx-offline-tts" --vits-model="$(basename "$V")/en_US-ljspeech-medium.onnx" \
       --vits-tokens="$(basename "$V")/tokens.txt" --vits-data-dir="$(basename "$V")/espeak-ng-data" --num-threads=2 \
       --output-filename="$OUT/voice-sherpa-1.13.8-$ARCH.wav" -- "Hello! The same voice with sherpa-onnx one point thirteen point eight.") \
       > "$OUT/sherpa-1.13.8-$ARCH.log" 2>&1
    if [ "$(head -c 4 "$OUT/voice-sherpa-1.13.8-$ARCH.wav" 2>/dev/null)" = RIFF ]; then
      echo "INFO sherpa-onnx v1.13.8 reads the voice on macOS $MACOS too (voice-sherpa-1.13.8-$ARCH.wav)" | tee -a "$RES"
    else
      echo "INFO sherpa-onnx v1.13.8 did not read the voice: $(tail -3 "$OUT/sherpa-1.13.8-$ARCH.log")" | tee -a "$RES"
    fi
  fi
fi

say "macOS protection: the archive downloaded (quarantine), unpacked, the start allowed"
mkdir -p "$W/dl" "$W/q"
cp "$OUT/$ZIP" "$W/dl/"
QV="0081;$(printf '%x' "$(date +%s)");Safari;$(uuidgen)"
xattr -w com.apple.quarantine "$QV" "$W/dl/$ZIP"
ditto -x -k "$W/dl/$ZIP" "$W/q"
QAPP=$W/q/Ttranslator/Ttranslator.app
QENG=$(ls -d "$QAPP"/Contents/Resources/engine/darwin-*)/$server
if ! xattr -p com.apple.quarantine "$QENG" > /dev/null 2>&1; then
  echo "ditto did not carry the mark over: putting it on every file, as Archive Utility does"
  xattr -r -w com.apple.quarantine "$QV" "$W/q/Ttranslator"
fi
{ echo "the mark on the engine: $(xattr -p com.apple.quarantine "$QENG" 2>&1)"
  echo "spctl --assess (before the user allows it):"; limit 30 spctl --assess --type execute -vv "$QAPP" 2>&1
  # the user allows the start: «Открыть» / «Всё равно открыть» — macOS marks the app as allowed by the user
  echo "allowing it: $(xattr -w com.apple.quarantine "00c1;${QV#*;}" "$QAPP" 2>&1) $(limit 30 sudo spctl --add --label Ttranslator "$QAPP" 2>&1)"
  echo "spctl --assess (allowed):"; limit 30 spctl --assess --type execute -vv "$QAPP" 2>&1
} | tee "$OUT/quarantine-$ARCH.txt"
rm -f "$DATA/data/logs/launcher.log"
# this time without the welcome window: the screenshot shows the main window
printf '{"ui_language": "ru", "active_model": "file:tiny-test.gguf", "ui_port": %s, "show_welcome": false}\n' "$PORT" > "$DATA/config.json"
open "$QAPP" || echo "open: exit code $?"
for i in $(seq 1 60); do curl -sf -m 2 -o /dev/null "$U/api/ping" && break; sleep 1; done
if curl -sf -m 5 -o /dev/null "$U/api/ping"; then
  ok "the app from the downloaded archive starts once allowed"
  wait_until 240 's["phase"] == "ready"'; check $? "…and starts its engine (phase $(st 's["phase"]'))"
  wait_until 60 's["window"]["pages"] >= 1 and s["window"]["error"] == ""'; check $? "…and its window (pages $(st 's["window"]["pages"]'))"
  sleep 2; shot "window-quarantine-$ARCH"
  grep -E "quarantine|Translocation" "$DATA/data/logs/launcher.log" | tee -a "$OUT/quarantine-$ARCH.txt"
  echo "the mark on the engine now: $(xattr -p com.apple.quarantine "$QENG" 2>&1)" | tee -a "$OUT/quarantine-$ARCH.txt"
  save_logs "quarantine-$ARCH"
  quit_app; check $? "«Выход» (the app from the downloaded archive)"
else
  shot "quarantine-blocked-$ARCH"
  fail "the app from the downloaded archive did not start once allowed"
fi
log show --last 10m --style compact --predicate 'process == "syspolicyd" OR subsystem == "com.apple.syspolicy"' 2>/dev/null \
  | tail -80 > "$OUT/syspolicy-$ARCH.log"

summary
