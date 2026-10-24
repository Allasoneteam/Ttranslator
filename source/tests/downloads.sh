#!/usr/bin/env bash
# Download logic through the API: engine unpacked by hand, cancel and resume, checksum mismatch.
# Usage: downloads.sh <work> <ttranslator-binary> <ui-dir>   (work holds mirror/ and models.json from run_all.sh)
W=$1; BIN=$2; UI=$3; ROOT=$W/r-downloads; PORT=18779; BASE=http://127.0.0.1:$PORT
ENGINE=llama-b11435-bin-ubuntu-x64.tar.gz
fails=0
check() { if [ "$1" = 0 ]; then echo "OK   $2"; else echo "FAIL $2"; fails=$((fails+1)); fi; }
phase() { curl -s $BASE/api/state | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['phase'], d['download']['phase'], d['download']['error'])"; }
post() { curl -s -o /dev/null -X POST -H "Origin: $BASE" -H "Content-Type: application/json" -d "${2:-{\}}" $BASE$1; }
start() {
  (cd $ROOT && exec env TDOC_TEST_MODELS=$1 ./ttranslator --no-window --port $PORT >> $W/downloads.log 2>&1) &
  LPID=$!
  for i in $(seq 1 50); do curl -sf -o /dev/null $BASE/api/ping && break; sleep 0.2; done
  (curl -s -N $BASE/api/events > /dev/null &)
}
stop() { post /api/quit; wait $LPID 2>/dev/null; }

rm -rf $ROOT && mkdir -p $ROOT/engine/linux-amd64 $ROOT/ui && cp $BIN $ROOT/ttranslator && cp $UI/index.html $UI/tests.txt $ROOT/ui/
# the messages below are checked in Russian; a new installation is English since 1.0 (as start_launcher in run_all.sh)
printf '{"ui_language": "ru"}\n' > $ROOT/config.json
# 1. engine unpacked by hand (no engine.json): found and remembered
tar -C $ROOT/engine/linux-amd64 -xzf $W/mirror/$ENGINE
# slow copy of the models for cancel/resume, and a list with a wrong checksum
python3 $(dirname "$0")/mirror_server.py $W/mirror 18081 400000 > /dev/null 2>&1 &
SLOW=$!
python3 - "$W" <<'PY'
import json, sys
w = sys.argv[1]
ms = json.load(open(w + '/models.json'))
for m in ms: m['url'] = m['url'].replace('18080', '18081')
json.dump(ms, open(w + '/models_slow.json', 'w'))
bad = json.loads(json.dumps(ms)); bad[0]['sha256'] = '0' * 64
json.dump(bad, open(w + '/models_bad.json', 'w'))
PY
sleep 0.5
start $W/models_slow.json
[ "$(phase | cut -d' ' -f1)" = setup ]; check $? "setup screen with a hand-unpacked engine"
grep -q '"version": "manual"' $ROOT/engine/linux-amd64/engine.json; check $? "hand-unpacked engine remembered in engine.json"
# 2. cancel in the middle, then resume from the same place
post /api/setup; sleep 3; post /api/cancel; sleep 1
part=$(stat -c %s $ROOT/models/tiny-q4.gguf.part 2>/dev/null || echo 0)
[ "$part" -gt 0 ]; check $? "partial file kept after cancel ($part bytes)"
post /api/setup
for i in $(seq 1 120); do p=$(phase); case "$p" in ready*) break;; esac; sleep 0.5; done
[ "${p%% *}" = ready ]; check $? "resumed download finished: $p"
grep -q "Range\|resum" $W/downloads.log 2>/dev/null; true
stop
# 3. checksum mismatch is reported and the file is not used
rm -f $ROOT/models/*
start $W/models_bad.json
post /api/setup
for i in $(seq 1 120); do p=$(phase); case "$p" in *контрольн*|ready*) break;; esac; sleep 0.5; done
case "$p" in *контрольн*) r=0;; *) r=1;; esac; check $r "checksum mismatch reported: $p"
[ ! -f $ROOT/models/tiny-q4.gguf ]; check $? "bad file not installed"
stop
kill $SLOW 2>/dev/null
echo "FAILS: $fails"
