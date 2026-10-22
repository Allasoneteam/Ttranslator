#!/usr/bin/env bash
# All automated tests of the translator, on Linux (Claude's cloud workspace or any Linux machine).
#
#   bash source/tests/run_all.sh [work-dir]
#
# Needs: Go 1.24+, Python 3 with playwright + its Chromium, numpy and gguf (pip install playwright numpy gguf),
# internet access to github.com once (the official llama.cpp engine archive, sherpa-onnx, three Piper voices and
# espeak-ng-data for reading aloud are cached in the work dir). The app window (source/window) is built and tested if these are there
# (Ubuntu/Debian): g++ pkg-config libgtk-3-dev libwebkit2gtk-4.1-dev xvfb xdotool imagemagick openbox x11-utils, and for the Windows
# build g++-mingw-w64-x86-64; without them those suites are skipped.
# Real models are not needed: a tiny stand-in model with random weights checks the plumbing (its output is
# gibberish); translation quality is checked on the user's computer with the «Тест» button.
set -u
T=$(cd "$(dirname "$0")" && pwd)                 # .../source/tests
SRC=$(dirname "$T")                              # .../source (launcher/ is here)
if [ -d "$SRC/../ui" ]; then APP=$(cd "$SRC/.." && pwd); else APP=$SRC; fi   # program folder: ui/, start.sh
UI=$APP/ui
W=${1:-${TMPDIR:-/tmp}/tdoc-tests}
mkdir -p "$W/mirror" "$W/shots"
ENGINE=llama-b11435-bin-ubuntu-x64.tar.gz
ENGINE_SHA=ee617d7af304985e268fbc33bdd8fe44110f1dc2f599ecb27bdf08890e6e6e4c
TTS=sherpa-onnx-v1.13.7-linux-x64-shared.tar.bz2
TTS_SHA=95b9f4358e2d5522a0bd987c3ee91128e31f8abf4340927cab32e438300f3c24
MIRROR=18080
SUMMARY=""; FAILED=0; PIDS=""

say() { printf '\n=== %s\n' "$*"; }
cleanup() {
  for p in 18771 18772 18773 18774 18775 18776 18777 18778 18780 18781 18782 18783 18785; do curl -s -m 1 -o /dev/null -X POST -H "Origin: http://127.0.0.1:$p" "http://127.0.0.1:$p/api/quit"; done
  [ -n "$PIDS" ] && kill $PIDS 2>/dev/null
}
trap cleanup EXIT

# a launcher in a fresh folder; the SSE client keeps it alive between browser sessions (not with "nokeep": the
# test itself checks that the program exits when its last window closes). XENV: more environment variables.
start_launcher() {   # root port [saved.tsv of version 0.5 to put into data/ before the start] [nokeep]
  rm -rf "$1"; mkdir -p "$1/ui"
  cp "$W/ttranslator" "$1/"; cp "$UI/index.html" "$UI/tests.txt" "$1/ui/"
  if [ -n "${3:-}" ]; then mkdir -p "$1/data"; cp "$3" "$1/data/saved.tsv"; fi
  (cd "$1" && exec env TDOC_ENGINE_URL="http://127.0.0.1:$MIRROR/$ENGINE" TDOC_TEST_MODELS="$W/models.json" ${XENV:-} \
     ./ttranslator --no-window --port "$2" >> "$W/launcher.log" 2>&1) &
  PIDS="$PIDS $!"
  for i in $(seq 1 50); do curl -sf -o /dev/null "http://127.0.0.1:$2/api/ping" && break; sleep 0.2; done
  [ "${4:-}" = nokeep ] || (curl -s -N "http://127.0.0.1:$2/api/events" > /dev/null &)
}
make_ready() {       # port: first-run downloads, then wait for the engine
  curl -s -o /dev/null -X POST -H "Origin: http://127.0.0.1:$1" "http://127.0.0.1:$1/api/setup"
  for i in $(seq 1 240); do
    p=$(curl -s "http://127.0.0.1:$1/api/state" | python3 -c "import json,sys; print(json.load(sys.stdin)['phase'])" 2>/dev/null)
    [ "$p" = ready ] && return 0; sleep 0.5
  done
  echo "launcher on port $1 did not become ready (phase: $p)"; return 1
}
run() {              # name command...
  local name=$1; shift
  say "$name"
  local out; out=$("$@" 2>&1); echo "$out" | tail -n 60
  if echo "$out" | grep -qE '^FAIL |Traceback|FAILS: [1-9]|ERROR:'; then
    FAILED=$((FAILED + 1)); SUMMARY="$SUMMARY\n  FAIL  $name"
  else SUMMARY="$SUMMARY\n  ok    $name"; fi
}

say "launcher: vet, unit tests, Linux build"
rm -rf "$SRC/launcher/ui_fallback"; mkdir -p "$SRC/launcher/ui_fallback"
cp "$UI/index.html" "$UI/tests.txt" "$SRC/launcher/ui_fallback/"
(cd "$SRC/launcher" && go vet ./... && GOOS=windows go vet ./... && go test ./... \
   && CGO_ENABLED=0 go build -trimpath -o "$W/ttranslator" . \
   && CGO_ENABLED=0 GOOS=windows GOARCH=amd64 go build -trimpath -o "$W/ttranslator.exe" .) || { echo "ERROR: build failed"; exit 1; }

say "fixtures: stand-in models, official engine archive, local mirror"
python3 -c "import gguf, numpy, playwright, pefile, PIL" 2>/dev/null || pip install --break-system-packages -q gguf numpy playwright pefile pillow
python3 "$T/make_tiny_gguf.py" "$W/mirror/tiny-q4.gguf" 1 6 && python3 "$T/make_tiny_gguf.py" "$W/mirror/tiny-q8.gguf" 2 3 \
  || { echo "ERROR: stand-in models"; exit 1; }
if ! echo "$ENGINE_SHA  $W/mirror/$ENGINE" | sha256sum -c --status 2>/dev/null; then
  curl -fsSL -o "$W/mirror/$ENGINE" "https://github.com/ggml-org/llama.cpp/releases/download/b11435/$ENGINE" \
    && echo "$ENGINE_SHA  $W/mirror/$ENGINE" | sha256sum -c --status || { echo "ERROR: engine archive"; exit 1; }
fi
# reading aloud: the official sherpa-onnx program for Linux, three real Piper voices and espeak-ng-data (cached)
fetch_cached() {     # file sha256 url
  if ! echo "$2  $W/mirror/$1" | sha256sum -c --status 2>/dev/null; then
    curl -fsSL -o "$W/mirror/$1" "$3" && echo "$2  $W/mirror/$1" | sha256sum -c --status || { echo "ERROR: $1"; exit 1; }
  fi
}
fetch_cached "$TTS" "$TTS_SHA" "https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.13.7/$TTS"
fetch_cached vits-piper-en_US-ljspeech-medium.tar.bz2 3dfb4b759d8be032a4903a9538d128b0fda2a06ab1de6cbc2d93a97e2dd83dba \
  https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-en_US-ljspeech-medium.tar.bz2
fetch_cached vits-piper-ru_RU-dmitri-medium.tar.bz2 c86d0803737de13d441923ff3b3f309482fab8d7af3ec85949942809eb9a3660 \
  https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-ru_RU-dmitri-medium.tar.bz2
# v0.9.3: the Chinese voice (a lexicon instead of espeak-ng-data) and espeak-ng-data for a voice made of parts
fetch_cached vits-piper-zh_CN-chaowen-medium.tar.bz2 1b69bdcf10bb6331c7f8a7591940febeb175c6bb86caa3802d96531f8e4ad211 \
  https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/vits-piper-zh_CN-chaowen-medium.tar.bz2
fetch_cached espeak-ng-data.tar.bz2 4135ccf82e1f40613491c0874d4945ae9e9c7840933d8e25a6f9e003d9ebf533 \
  https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/espeak-ng-data.tar.bz2
# the parts of a test voice: the model and tokens.txt of the LJSpeech archive as separate files (as the Spanish
# es_ES-mls_9972-low comes from Hugging Face)
if [ ! -s "$W/mirror/es-test-model.onnx" ] || [ ! -s "$W/mirror/es-test-tokens.txt" ]; then
  rm -rf "$W/parts-tmp"; mkdir -p "$W/parts-tmp"
  tar -xjf "$W/mirror/vits-piper-en_US-ljspeech-medium.tar.bz2" -C "$W/parts-tmp" \
    vits-piper-en_US-ljspeech-medium/en_US-ljspeech-medium.onnx vits-piper-en_US-ljspeech-medium/tokens.txt \
    && cp "$W/parts-tmp/vits-piper-en_US-ljspeech-medium/en_US-ljspeech-medium.onnx" "$W/mirror/es-test-model.onnx" \
    && cp "$W/parts-tmp/vits-piper-en_US-ljspeech-medium/tokens.txt" "$W/mirror/es-test-tokens.txt" || { echo "ERROR: test voice parts"; exit 1; }
  rm -rf "$W/parts-tmp"
fi
python3 - "$W" <<'PY'
import hashlib, json, os, sys
w = sys.argv[1]
def spec(id_, name, f):
    b = open(os.path.join(w, 'mirror', f), 'rb').read()
    return {'id': id_, 'name': name, 'note': 'stand-in', 'file': f, 'url': 'http://127.0.0.1:18080/' + f,
            'page': '127.0.0.1:18080', 'size': len(b), 'sha256': hashlib.sha256(b).hexdigest()}
json.dump([spec('q4', 'Hy-MT2-1.8B · Q4_K_M (test)', 'tiny-q4.gguf'), spec('q8', 'Hy-MT2-1.8B · Q8_0 (test)', 'tiny-q8.gguf')],
          open(os.path.join(w, 'models.json'), 'w'), ensure_ascii=False, indent=1)
# voices for the reading-aloud test: two real ones (the licences here are test data) and one missing on the mirror
def voice(id_, lang, name, gender, lic, nc, v, f=None):
    f = f or 'vits-piper-%s.tar.bz2' % v
    p = os.path.join(w, 'mirror', f)
    b = open(p, 'rb').read() if os.path.exists(p) else b''
    return {'id': id_, 'lang': lang, 'name': name, 'gender': gender, 'license': lic, 'nc': nc, 'dir': 'vits-piper-' + v,
            'model': v + '.onnx', 'sid': 0, 'url': 'http://127.0.0.1:18080/' + f, 'page': 'https://rhasspy.github.io/piper-samples/#' + v,
            'size': len(b) or 1000, 'sha256': hashlib.sha256(b).hexdigest() if b else '0' * 64}
json.dump([voice('en-lj', 'en', 'LJSpeech', 'female', 'public domain', False, 'en_US-ljspeech-medium'),
           voice('ru-dm', 'ru', 'Dmitri', 'male', 'CC BY-NC-SA 4.0', True, 'ru_RU-dmitri-medium'),
           voice('de-x', 'de', 'Broken', 'female', 'CC0', False, 'de_DE-missing-low')],
          open(os.path.join(w, 'voices.json'), 'w'), ensure_ascii=False, indent=1)
# v0.9.3: a voice made of parts (model, tokens.txt, espeak-ng-data archive) and the real Chinese voice with a lexicon
def part(f, name):
    b = open(os.path.join(w, 'mirror', f), 'rb').read()
    return {'url': 'http://127.0.0.1:18080/' + f, 'file': name, 'size': len(b), 'sha256': hashlib.sha256(b).hexdigest()}
parts = [part('es-test-model.onnx', 'es_ES-test-low.onnx'), part('es-test-tokens.txt', 'tokens.txt'), part('espeak-ng-data.tar.bz2', 'espeak-ng-data.tar.bz2')]
es = {'id': 'es-parts', 'lang': 'es', 'name': 'Parts', 'gender': 'female', 'license': 'CC BY 4.0', 'nc': False,
      'dir': 'vits-piper-es_ES-test-low', 'model': 'es_ES-test-low.onnx', 'sid': 0, 'url': parts[0]['url'],
      'page': 'https://rhasspy.github.io/piper-samples/#es_ES-mls_9972-low', 'size': sum(p['size'] for p in parts),
      'sha256': parts[0]['sha256'], 'parts': parts}
zh = voice('zh-cw', 'zh', 'Chaowen', 'male', 'CC0', False, 'zh_CN-chaowen-medium')
zh.update({'lexicon': 'lexicon.txt', 'rules': ['phone.fst', 'date.fst', 'number.fst']})
json.dump([es, zh], open(os.path.join(w, 'voices093.json'), 'w'), ensure_ascii=False, indent=1)
PY
python3 "$T/mirror_server.py" "$W/mirror" $MIRROR 8000000 > "$W/mirror.log" 2>&1 &
PIDS="$PIDS $!"
# wait until the mirror really accepts connections (a fixed pause raced with a slow Python start)
for i in $(seq 1 100); do (exec 3<>"/dev/tcp/127.0.0.1/$MIRROR") 2>/dev/null && break; sleep 0.1; done

# texts of the window in English and German (no launcher needed)
run "interface translations: every text in English and German" python3 "$T/i18n_check.py" "$UI/index.html"
# the program's icon inside the Windows build, up to date with the drawing
run "icon of Ttranslator.exe" python3 "$T/icon_check.py" "$W/ttranslator.exe" "$SRC/launcher" "$UI/index.html" "$W"

# v0.2 flows (fresh folder: the test runs the first start itself)
start_launcher "$W/r1" 18771
run "e2e v0.2: translation, editing, saved, test, model menu" python3 "$T/e2e_v02.py" "$W" http://127.0.0.1:18771/ "$W/r1"
run "prompts v0.2 (canned replies)" python3 "$T/prompts_v02.py" "$W" http://127.0.0.1:18771/

# v0.3 features
start_launcher "$W/r2" 18772
run "e2e v0.3: languages, 1000 characters, chat, unload/load" python3 "$T/e2e_v03.py" "$W" http://127.0.0.1:18772/ "$W/r2"
cp "$W/mirror/tiny-q8.gguf" "$W/r2/models/my-custom-model.gguf"
run "prompts v0.3 and chat requests (canned replies)" python3 "$T/prompts_v03.py" "$W" http://127.0.0.1:18772/

# v0.4 features
start_launcher "$W/r3" 18773
make_ready 18773
run "e2e v0.4: glossary, «?» questions" python3 "$T/e2e_v04.py" "$W" http://127.0.0.1:18773/ "$W/r3"
cp "$W/mirror/tiny-q8.gguf" "$W/r3/models/my-custom-model.gguf"
run "prompts v0.4: glossary in prompts, questions (canned replies)" python3 "$T/prompts_v04.py" "$W" http://127.0.0.1:18773/ "$W/r3"

# v0.5 features: «Случайно», "Please load a model.", the window staying open without a model, ↔, Exit.
# The e2e suite ends by closing this launcher with the Exit button, so it runs last.
start_launcher "$W/r5" 18774
make_ready 18774
cp "$W/mirror/tiny-q8.gguf" "$W/r5/models/my-custom-model.gguf"
run "prompts v0.5: «Случайно», Please load a model (canned replies)" python3 "$T/prompts_v05.py" "$W" http://127.0.0.1:18774/
run "e2e v0.5: ↔, window stays without a model, banner, Exit" python3 "$T/e2e_v05.py" "$W" http://127.0.0.1:18774/ "$W/r5"

# v0.5.1 features: files of saved translations; the launcher starts with a saved.tsv of version 0.5 in data/
python3 - "$W/saved-0.5.tsv" <<'PY'
import sys
rows = [
    ('m1', '2026-10-09T12:02:23+02:00', 'en', 'ru', 'Научный · Gemma 4 E2B', 'We present a closed-form solution.', 'Мы представляем решение в замкнутой форме.', ''),
    ('m2', '2026-10-09T12:05:00+02:00', 'ru', 'ru', 'Исправленный', 'Это ещё тестовый текст.', 'Это ещё проверочный текст.', ''),
    ('m3', '2026-10-10T09:00:00+02:00', 'de', 'ru', 'Нейтральный', 'Der Laser ist stark.', 'Лазер мощный.', 'оптика'),
]
head = 'id\tвремя\tс\tна\tстиль\tисходный текст\tперевод\tконтекст'
open(sys.argv[1], 'w', encoding='utf-8-sig', newline='').write('\r\n'.join([head] + ['\t'.join(r) for r in rows]) + '\r\n')
PY
start_launcher "$W/r6" 18775 "$W/saved-0.5.tsv"
make_ready 18775
run "e2e v0.5.1: files of saved translations, search, «В поле», import/export, icon" python3 "$T/e2e_v051.py" "$W" http://127.0.0.1:18775/ "$W/r6"

# v0.6 features: interface languages, settings, help, About; the test starts at the first-start screen (no
# make_ready) and ends by closing this launcher with Exit from the settings
start_launcher "$W/r7" 18776
run "e2e v0.6: interface languages, settings, help, About, theme, font, Exit" python3 "$T/e2e_v06.py" "$W" http://127.0.0.1:18776/ "$W/r7"

# v0.6.1: header, languages of a new window, closing the window; no keep-alive stream here: the test closes its
# windows and checks that the program unloads the model and exits by itself
start_launcher "$W/r8" 18777 "" nokeep
make_ready 18777
run "e2e v0.6.1: header, languages of a new window, closing the window" python3 "$T/e2e_v061.py" "$W" http://127.0.0.1:18777/ "$W/r8"

# v0.7: the welcome window, start options, from/to/file before downloads, «Свой вариант»; the test starts at the
# first-start screen, restarts the launcher three times itself (same engine address and test models), ends with Exit
start_launcher "$W/r9" 18778
run "e2e v0.7: welcome window, start options, download confirmation, own version" python3 "$T/e2e_v07.py" "$W" http://127.0.0.1:18778/ "$W/r9" "http://127.0.0.1:$MIRROR/$ENGINE" "$W/models.json"

# v0.8: LaTeX formulas are not translated and not damaged (canned replies; a chat-family file and Hy-MT2 stand-in).
# Port 18780: 18779 belongs to downloads.sh
start_launcher "$W/r10" 18780
make_ready 18780
cp "$W/mirror/tiny-q8.gguf" "$W/r10/models/my-custom-model.gguf"
run "prompts v0.8: LaTeX formulas (canned replies)" python3 "$T/prompts_v08.py" "$W" http://127.0.0.1:18780/ "$W/r10"

# v0.9: examples in the empty fields, the test panel, «Учебный пример» (canned replies)
start_launcher "$W/r11" 18781
make_ready 18781
cp "$W/mirror/tiny-q8.gguf" "$W/r11/models/my-custom-model.gguf"
run "prompts v0.9: examples, «Учебный пример» (canned replies)" python3 "$T/prompts_v09.py" "$W" http://127.0.0.1:18781/
run "prompts v0.9.1: «Учебный пример» — level, topic, exercise, check (canned replies)" python3 "$T/prompts_v091.py" "$W" http://127.0.0.1:18781/
run "prompts v0.9.2: «Учебный пример» — strict request, check before showing, kinds; About (canned replies)" python3 "$T/prompts_v092.py" "$W" http://127.0.0.1:18781/

# v0.9: reading aloud with the real sherpa-onnx program and Piper voices served by the mirror
XENV="TDOC_TTS_URL=http://127.0.0.1:$MIRROR/$TTS TDOC_TEST_VOICES=$W/voices.json" start_launcher "$W/r12" 18782
make_ready 18782
run "e2e v0.9: reading aloud (sherpa-onnx, Piper voices)" python3 "$T/e2e_v09.py" "$W" http://127.0.0.1:18782/ "$W/r12"

# v0.9.3: a voice made of parts (as the Spanish one), the Chinese voice with a lexicon, the welcome window (moving it,
# «Выйти» — the suite ends by closing this launcher). Port 18785: 18783 and 18784 belong to the app window suites
XENV="TDOC_TTS_URL=http://127.0.0.1:$MIRROR/$TTS TDOC_TEST_VOICES=$W/voices093.json" start_launcher "$W/r13" 18785
make_ready 18785
run "e2e v0.9.3: voices of parts and with a lexicon (Spanish, Chinese), welcome window: move, Exit" python3 "$T/e2e_v093.py" "$W" http://127.0.0.1:18785/ "$W/r13"

# v0.9.1–0.9.3: the app window (ttranslator-window, source/window): the Windows program builds and needs only system
# DLLs; the Linux program on WebKitGTK under a virtual screen (with openbox, if there is one: the maximized start) —
# the launcher with it, then its functions for the page
if command -v x86_64-w64-mingw32-g++ >/dev/null; then
  run "window program for Windows: builds, only system DLLs" sh -c '
    OUT="$1" sh "$2/window/build.sh" windows > "$1/window-build-win.log" 2>&1 || { echo "ERROR: build"; tail -20 "$1/window-build-win.log"; exit; }
    dlls=$(x86_64-w64-mingw32-objdump -p "$1/ttranslator-window.exe" | sed -n "s/.*DLL Name: //p" | tr "A-Z" "a-z" | sort | tr "\n" " ")
    want="advapi32.dll comdlg32.dll kernel32.dll msvcrt.dll ole32.dll shell32.dll shlwapi.dll user32.dll "
    if [ "$dlls" = "$want" ]; then echo "OK   imports: $dlls"; else echo "FAIL imports: $dlls"; fi' sh "$W" "$SRC"
else SUMMARY="$SUMMARY\n  skip  window program for Windows (no g++-mingw-w64-x86-64)"; fi
if pkg-config --exists gtk+-3.0 webkit2gtk-4.1 2>/dev/null && command -v xvfb-run >/dev/null; then
  if OUT="$W" sh "$SRC/window/build.sh" linux > "$W/window-build.log" 2>&1; then
    run "e2e v0.9.1–0.9.3: app window — start in front, maximized, close, Exit, fallback (WebKitGTK, virtual screen)" \
      xvfb-run -a -s "-screen 0 1280x860x24" python3 "$T/e2e_window.py" "$W" "$W/ttranslator" "$W/ttranslator-window-linux" "http://127.0.0.1:$MIRROR/$ENGINE" "$W/models.json" 18783
    if command -v xdotool >/dev/null; then
      run "window program: functions for the page (WebKitGTK, virtual screen)" \
        xvfb-run -a -s "-screen 0 1280x860x24" python3 "$T/window_functions.py" "$W" "$W/ttranslator-window-linux" 18784
    else SUMMARY="$SUMMARY\n  skip  window program functions (no xdotool)"; fi
  else echo "ERROR: window build"; tail -20 "$W/window-build.log"; FAILED=$((FAILED + 1)); SUMMARY="$SUMMARY\n  FAIL  window program for Linux: build"; fi
else SUMMARY="$SUMMARY\n  skip  app window (no libwebkit2gtk-4.1-dev or xvfb-run)"; fi

# fallback start without the launcher
R4=$W/r4; rm -rf "$R4"; mkdir -p "$R4/ui" "$R4/models"
cp -r "$W/r1/engine" "$R4/"; cp "$APP/start.sh" "$R4/"; chmod +x "$R4/start.sh"
cp "$UI/index.html" "$UI/tests.txt" "$R4/ui/"; cp "$W/mirror/tiny-q8.gguf" "$R4/models/gemma-4-E2B_q4_0-it.gguf"
(cd "$R4" && exec ./start.sh > "$W/start_sh.log" 2>&1) &
BASIC=$!; PIDS="$PIDS $BASIC"
for i in $(seq 1 60); do curl -sf -o /dev/null http://127.0.0.1:8766/health && break; sleep 0.5; done
run "fallback start (start.sh)" python3 "$T/basic_mode.py" http://127.0.0.1:8766/
kill $BASIC 2>/dev/null

run "downloads: hand-unpacked engine, cancel and resume, checksum" bash "$T/downloads.sh" "$W" "$W/ttranslator" "$UI"

say "summary (work folder: $W, screenshots in $W/shots)"
printf "$SUMMARY\n"
[ $FAILED -eq 0 ] && echo "ALL SUITES PASSED" || echo "FAILED SUITES: $FAILED"
exit $FAILED
