#!/bin/bash
# The step "android" of GitHub Actions (.github/workflows/ci.yml): bash android/ci.sh <out-dir>
# Builds the test APK (android/build.sh) and checks it in the Android emulator (android/test/emulator_test.py):
# Android 16 (API 36) fully, Android 10 (API 29, the oldest version the question is about) — the core. Everything in
# <out-dir> becomes the artifact "android-results" of the run: the APK, screenshots of the phone screen, logs.
# The emulator needs KVM: GitHub's Linux runners have it. Locally: ANDROID_HOME and an x86_64 machine with /dev/kvm.
# Environment: APIS — the emulators to run ("36 29" by default; "" — only build), ANDROID_WORK — the work folder.
set -uo pipefail
OUT=${1:?usage: android/ci.sh <out-dir>}
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(dirname "$HERE")
mkdir -p "$OUT"
OUT=$(cd "$OUT" && pwd)
export ANDROID_WORK=${ANDROID_WORK:-${RUNNER_TEMP:-$HERE}/android-work}
W=$ANDROID_WORK
mkdir -p "$W"
APIS=${APIS-36 29}
SDK=${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}
[ -n "$SDK" ] || { echo "::error::no Android SDK (ANDROID_HOME)"; exit 1; }
export ANDROID_HOME=$SDK
SDKMANAGER=$SDK/cmdline-tools/latest/bin/sdkmanager
AVDMANAGER=$SDK/cmdline-tools/latest/bin/avdmanager
export PATH=$SDK/platform-tools:$SDK/emulator:$PATH
status=0
note() { echo "== $*"; }
fail() { echo "::error::$*"; status=1; }

# JDK 17+ for Gradle and the Android Gradle Plugin (the runner's default may be older or newer: 17 is the safe one)
if [ -n "${JAVA_HOME_17_X64:-}" ]; then export JAVA_HOME=$JAVA_HOME_17_X64 PATH=$JAVA_HOME_17_X64/bin:$PATH; fi
java -version 2>&1 | head -1

# ---------------------------------------------------------------- the APK
note "building the APK"
if ! bash "$HERE/build.sh" "$OUT" 2>&1 | tee "$OUT/build.log"; then
  grep -E '^ERROR:' "$OUT/build.log" | while IFS= read -r l; do echo "::error::$l"; done
  cp "$W/gradle.log" "$W"/llama-x86_64.*.log "$OUT/" 2>/dev/null
  exit 1
fi
cp "$W/gradle.log" "$OUT/" 2>/dev/null
APK=$(ls "$OUT"/Ttranslator-*-android-test.apk)
[ -z "$APIS" ] && exit 0
# space for the emulators: the build folders are not needed any more
rm -rf "$W/llama-x86_64" "$W/launcher" "$W/unpacked" "$HERE/app/build/intermediates"
df -h / "$W" | sed 's/^/   /'

# ---------------------------------------------------------------- tools of the check
note "python modules of the check (as the tests of source/tests: numpy, gguf, playwright)"
python3 -m venv "$W/venv" && "$W/venv/bin/pip" install -q numpy gguf playwright || fail "pip install failed"
PY=$W/venv/bin/python
# the tiny model of the tests (random weights: gibberish, enough for the plumbing)
"$PY" "$REPO/source/tests/make_tiny_gguf.py" "$W/tiny-test.gguf" 1 6 || fail "no tiny model"

if [ -e /dev/kvm ]; then
  echo 'KERNEL=="kvm", GROUP="kvm", MODE="0666", OPTIONS+="static_node=kvm"' | sudo tee /etc/udev/rules.d/99-kvm4all.rules >/dev/null
  sudo udevadm control --reload-rules && sudo udevadm trigger --name-match=kvm
else
  echo "::warning::no /dev/kvm: the emulator will be very slow or will not start"
fi
yes | "$SDKMANAGER" --licenses >/dev/null 2>&1 || true
"$SDKMANAGER" --install emulator platform-tools >/dev/null || fail "sdkmanager: emulator"

run_emulator() { # api, extra arguments of the check
  local api=$1; shift
  local img="system-images;android-$api;google_apis;x86_64" avd=tt$api dir=$OUT/emulator-api$api
  mkdir -p "$dir"
  note "emulator: Android API $api ($img)"
  "$SDKMANAGER" --install "$img" >/dev/null || { fail "no system image $img"; return; }
  echo no | "$AVDMANAGER" create avd -n $avd -k "$img" --force >/dev/null || { fail "avdmanager"; return; }
  # a phone: 1080 × 2400 at 420 dpi (as many phones), 4 GB of memory
  cat >> "$HOME/.android/avd/$avd.avd/config.ini" <<EOF
hw.lcd.width=1080
hw.lcd.height=2400
hw.lcd.density=420
hw.ramSize=4096
hw.keyboard=yes
disk.dataPartition.size=6G
EOF
  emulator -avd $avd -no-window -no-audio -no-boot-anim -no-snapshot -gpu swiftshader_indirect -cores 4 -memory 4096 \
    -camera-back none -camera-front none > "$dir/emulator.log" 2>&1 &
  local epid=$!
  adb wait-for-device
  if ! timeout 600 bash -c 'until [ "$(adb shell getprop sys.boot_completed 2>/dev/null | tr -d "\r")" = 1 ]; do sleep 3; done'; then
    fail "API $api: the emulator did not boot"; tail -20 "$dir/emulator.log"; kill $epid; return
  fi
  adb shell settings put global window_animation_scale 0; adb shell settings put global transition_animation_scale 0
  adb shell settings put global animator_duration_scale 0; adb shell input keyevent 82
  sleep 5
  if ! "$PY" "$HERE/test/emulator_test.py" "$APK" "$dir" "$W/tiny-test.gguf" "$@" 2>&1 | tee "$dir/test.log"; then
    grep -E '^FAIL' "$dir/results.txt" 2>/dev/null | head -20 | while IFS= read -r l; do echo "::error::API $api: $l"; done
    status=1
  fi
  adb emu kill >/dev/null 2>&1; sleep 5; kill $epid 2>/dev/null; wait $epid 2>/dev/null
  # space for the next emulator
  rm -rf "$HOME/.android/avd/$avd.avd" "$SDK/system-images/android-$api"
}

for api in $APIS; do
  if [ "$api" = 36 ]; then run_emulator $api; else run_emulator $api --quick; fi
done
exit $status
