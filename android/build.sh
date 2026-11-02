#!/bin/bash
# Ttranslator for Android (feasibility prototype): builds the test APK.
#   bash android/build.sh [out-dir]          (default: android/work/out)
# Needs: the Android SDK (ANDROID_HOME, with cmdline-tools), JDK 17+, Go 1.24+, git, curl, python3, cmake, ninja.
# Environment: ABIS — "arm64-v8a x86_64" (default; arm64-v8a: phones, x86_64: the emulator of the CI),
# ANDROID_WORK — the work folder (default android/work; downloads are cached in it).
#
# What goes into the APK (app/src/main/jniLibs/<abi>/, all as lib*.so — Android starts an app's programs only from its
# library folder):
#   libttranslator.so              the launcher (source/launcher, unchanged), Go with cgo (NDK): DNS works only so
#   libllama-server.so + libs      llama-server of llama.cpp b11435: arm64 — the official release for Android
#                                  (llama-<tag>-bin-android-arm64.tar.gz); x86_64 — built here from the same tag (no
#                                  official build for it; only for the emulator)
#   libsherpa-onnx-offline-tts.so  the reading-aloud program: android/native/tts-cli.c over the C API of the official
#   + libsherpa-onnx-c-api.so,     sherpa-onnx v1.13.7 libraries for Android (sherpa-onnx-<ver>-android.tar.bz2: they
#     libonnxruntime.so            have no such program)
# Every download is pinned: version, size and SHA-256 (git: the commit).
set -euo pipefail

# ---------------------------------------------------------------- pinned versions
LLAMA_TAG=b11435
LLAMA_COMMIT=43fe9c64281ef735046adc025e9e7559a1f659a5
LLAMA_ANDROID=llama-$LLAMA_TAG-bin-android-arm64.tar.gz
LLAMA_ANDROID_SIZE=73924873
LLAMA_ANDROID_SHA=7b4788215bb8c77c5f7c989f935655bb82bcccf9280529e342dfb60187efdefe
SHERPA_TAG=v1.13.7
SHERPA_COMMIT=917bed95c8e5c7c18aa4d69fea42e9ef8ef0a60e
SHERPA_ANDROID=sherpa-onnx-$SHERPA_TAG-android.tar.bz2
SHERPA_ANDROID_SIZE=45287000
SHERPA_ANDROID_SHA=7208b26f5109777d1c3c22a45f04665419d6f3ea81f6811a2dfd5ff2d7622e6e
SHERPA_HEADER_SIZE=167345
SHERPA_HEADER_SHA=426db2c6acfb51e02143aece67c45779fae699d961c7c26ccf6f1388fdeaa2df
GRADLE_VERSION=9.8.2
GRADLE_SIZE=151620138
GRADLE_SHA=21bd5da2de49b642904077f38c0efdc7778e92b3ed0889392dca61b97e389607
# the NDK of the official llama.cpp build for Android (its release workflow); API 28 as there
NDK_VERSION=29.0.14206865
API=28
PLATFORM=android-36
BUILD_TOOLS=36.0.0

HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(dirname "$HERE")
W=${ANDROID_WORK:-$HERE/work}
OUT=${1:-$W/out}
CACHE=$W/cache
ABIS=${ABIS:-arm64-v8a x86_64}
mkdir -p "$W" "$OUT" "$CACHE"
OUT=$(cd "$OUT" && pwd)

say() { echo "== $*"; }
die() { echo "ERROR: $*" >&2; exit 1; }

# the launcher and these files must use the same versions of the engine and of sherpa-onnx
grep -q "engineVersion = \"$LLAMA_TAG\"" "$REPO/source/launcher/main.go" || die "the launcher's engineVersion is not $LLAMA_TAG: update android/build.sh"
grep -q "ttsVersion   = \"$SHERPA_TAG\"" "$REPO/source/launcher/tts.go" || die "the launcher's ttsVersion is not $SHERPA_TAG: update android/build.sh"
APP_VERSION=$(sed -n 's/^\tappVersion = "\(.*\)"$/\1/p' "$REPO/source/launcher/main.go")
[ -n "$APP_VERSION" ] || die "no appVersion in source/launcher/main.go"

# ---------------------------------------------------------------- tools
SDK=${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}
[ -n "$SDK" ] && [ -d "$SDK" ] || die "no Android SDK: set ANDROID_HOME"
SDKMANAGER=$SDK/cmdline-tools/latest/bin/sdkmanager
[ -x "$SDKMANAGER" ] || SDKMANAGER=$(command -v sdkmanager || true)
sdk_install() { # package, folder that shows it is there
  [ -e "$SDK/$2" ] && return 0
  [ -n "$SDKMANAGER" ] || die "no sdkmanager to install $1"
  say "installing $1"
  yes | "$SDKMANAGER" --sdk_root="$SDK" --licenses >/dev/null 2>&1 || true
  "$SDKMANAGER" --sdk_root="$SDK" --install "$1" >/dev/null
}
sdk_install "ndk;$NDK_VERSION" "ndk/$NDK_VERSION"
sdk_install "platforms;$PLATFORM" "platforms/$PLATFORM"
sdk_install "build-tools;$BUILD_TOOLS" "build-tools/$BUILD_TOOLS"
NDK=$SDK/ndk/$NDK_VERSION
TC=$NDK/toolchains/llvm/prebuilt/linux-x86_64/bin
[ -x "$TC/llvm-strip" ] || die "no NDK toolchain in $TC"
command -v go >/dev/null || die "no go"
command -v java >/dev/null || die "no java (JDK 17+)"
command -v cmake >/dev/null || die "no cmake"
# ninja: from the system or from the SDK's cmake; else make
GEN=Ninja
if ! command -v ninja >/dev/null; then
  n=$(ls -d "$SDK"/cmake/*/bin 2>/dev/null | tail -1)
  if [ -n "$n" ] && [ -x "$n/ninja" ]; then PATH=$n:$PATH; else GEN="Unix Makefiles"; fi
fi

# fetch URL FILE SIZE SHA256: download into the cache (once), check size and checksum
fetch() {
  local url=$1 f=$CACHE/$2 size=$3 sha=$4
  if [ -f "$f" ] && [ "$(stat -c %s "$f")" = "$size" ] && echo "$sha  $f" | sha256sum -c --status; then return 0; fi
  say "downloading $url"
  curl -fsSL --retry 4 --retry-delay 5 -o "$f.part" "$url" || die "download failed: $url"
  [ "$(stat -c %s "$f.part")" = "$size" ] || die "wrong size of $2: $(stat -c %s "$f.part") instead of $size"
  echo "$sha  $f.part" | sha256sum -c --status || die "wrong SHA-256 of $2"
  mv "$f.part" "$f"
}

# ---------------------------------------------------------------- downloads
fetch "https://github.com/ggml-org/llama.cpp/releases/download/$LLAMA_TAG/$LLAMA_ANDROID" "$LLAMA_ANDROID" $LLAMA_ANDROID_SIZE $LLAMA_ANDROID_SHA
fetch "https://github.com/k2-fsa/sherpa-onnx/releases/download/$SHERPA_TAG/$SHERPA_ANDROID" "$SHERPA_ANDROID" $SHERPA_ANDROID_SIZE $SHERPA_ANDROID_SHA
mkdir -p "$CACHE/sherpa-include"
fetch "https://raw.githubusercontent.com/k2-fsa/sherpa-onnx/$SHERPA_COMMIT/sherpa-onnx/c-api/c-api.h" "sherpa-include/c-api.h" $SHERPA_HEADER_SIZE $SHERPA_HEADER_SHA
fetch "https://services.gradle.org/distributions/gradle-$GRADLE_VERSION-bin.zip" "gradle-$GRADLE_VERSION-bin.zip" $GRADLE_SIZE $GRADLE_SHA

# unpacked copies (each archive into a new folder of its own)
rm -rf "$W/unpacked"; mkdir -p "$W/unpacked/llama" "$W/unpacked/sherpa"
tar xzf "$CACHE/$LLAMA_ANDROID" -C "$W/unpacked/llama"
tar xjf "$CACHE/$SHERPA_ANDROID" -C "$W/unpacked/sherpa"
LLAMA_ARM64=$W/unpacked/llama/llama-$LLAMA_TAG
SHERPA_LIBS=$W/unpacked/sherpa/jniLibs
[ -f "$LLAMA_ARM64/llama-server" ] || die "no llama-server in $LLAMA_ANDROID"
if [ ! -x "$CACHE/gradle-$GRADLE_VERSION/bin/gradle" ]; then
  rm -rf "$CACHE/gradle-$GRADLE_VERSION"; unzip -q "$CACHE/gradle-$GRADLE_VERSION-bin.zip" -d "$CACHE"
fi
GRADLE=$CACHE/gradle-$GRADLE_VERSION/bin/gradle

# ---------------------------------------------------------------- llama-server for x86_64 (the emulator), from the same tag
build_llama_x86_64() {
  local src=$CACHE/llama.cpp-$LLAMA_TAG b=$W/llama-x86_64
  if [ ! -f "$src/.ok" ]; then
    say "llama.cpp $LLAMA_TAG: source"
    rm -rf "$src"; mkdir -p "$src"
    git -C "$src" init -q
    git -C "$src" fetch -q --depth 1 https://github.com/ggml-org/llama.cpp "refs/tags/$LLAMA_TAG"
    git -C "$src" checkout -q FETCH_HEAD
    [ "$(git -C "$src" rev-parse HEAD)" = "$LLAMA_COMMIT" ] || die "llama.cpp $LLAMA_TAG is not commit $LLAMA_COMMIT"
    touch "$src/.ok"
  fi
  if [ ! -f "$b/bin/llama-server" ]; then
    say "llama.cpp $LLAMA_TAG: building llama-server for Android x86_64 (as the official arm64 build: backends as libraries)"
    # as the official android-arm64 job of llama.cpp, but one CPU backend (SSE4.2-level code runs on any emulator) and
    # without the web UI of llama-server (the launcher starts it with --no-ui) and without HTTPS
    cmake -S "$src" -B "$b" -G "$GEN" -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" -DANDROID_ABI=x86_64 -DANDROID_PLATFORM=android-$API \
      -DCMAKE_INSTALL_RPATH='$ORIGIN' -DCMAKE_BUILD_WITH_INSTALL_RPATH=ON \
      -DGGML_BACKEND_DL=ON -DGGML_NATIVE=OFF -DGGML_OPENMP=OFF \
      -DLLAMA_OPENSSL=OFF -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF \
      -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_APP=OFF > "$W/llama-x86_64.configure.log" 2>&1 \
      || { tail -30 "$W/llama-x86_64.configure.log"; die "cmake configure failed"; }
    cmake --build "$b" --target llama-server ggml-cpu -j "$(nproc)" > "$W/llama-x86_64.build.log" 2>&1 \
      || { tail -30 "$W/llama-x86_64.build.log"; die "llama.cpp build failed"; }
  fi
  LLAMA_X86_64=$b/bin
}

# ---------------------------------------------------------------- the launcher (Go, cgo with the NDK)
build_launcher() { # abi goarch clang-triple
  local abi=$1 goarch=$2 cc=$TC/$3$API-clang src=$W/launcher
  rm -rf "$src"; mkdir -p "$src/ui_fallback"
  for f in "$REPO"/source/launcher/*.go; do
    case "$f" in *_test.go|*/make_icon.go) ;; *) cp "$f" "$src/";; esac
  done
  cp "$REPO/source/launcher/go.mod" "$REPO/source/launcher/Ttranslator.png" "$src/"
  # the copy of the interface inside the program, as source/build.sh makes it (the program folder has no ui/ here)
  cp "$REPO/ui/index.html" "$REPO/ui/tests.txt" "$src/ui_fallback/"
  say "launcher for $abi (GOOS=android GOARCH=$goarch, cgo: Android's DNS resolver)"
  (cd "$src" && CGO_ENABLED=1 GOOS=android GOARCH=$goarch CC=$cc go build -trimpath -ldflags "-s -w" -o "$JNI/$abi/libttranslator.so" .)
}

# ---------------------------------------------------------------- jniLibs
JNI=$HERE/app/src/main/jniLibs
rm -rf "$JNI"
for abi in $ABIS; do
  mkdir -p "$JNI/$abi"
  case $abi in
    arm64-v8a) goarch=arm64; triple=aarch64-linux-android; llama=$LLAMA_ARM64 ;;
    x86_64) goarch=amd64; triple=x86_64-linux-android; build_llama_x86_64; llama=$LLAMA_X86_64 ;;
    *) die "unknown ABI $abi" ;;
  esac
  build_launcher "$abi" $goarch $triple
  # the engine: the program and the libraries it needs (NEEDED of llama-server), and the CPU backends it loads
  cp "$llama/llama-server" "$JNI/$abi/libllama-server.so"
  for f in libllama-server-impl.so libllama-common.so libmtmd.so libllama.so libggml.so libggml-base.so; do
    cp "$llama/$f" "$JNI/$abi/"
  done
  cp "$llama"/libggml-cpu*.so "$JNI/$abi/"
  # reading aloud
  cp "$SHERPA_LIBS/$abi/libsherpa-onnx-c-api.so" "$SHERPA_LIBS/$abi/libonnxruntime.so" "$JNI/$abi/"
  say "reading-aloud program for $abi"
  "$TC/$triple$API-clang" -O2 -Wall -Wextra -Werror -I"$CACHE/sherpa-include" -o "$JNI/$abi/libsherpa-onnx-offline-tts.so" \
    "$HERE/native/tts-cli.c" -L"$JNI/$abi" -lsherpa-onnx-c-api -Wl,-rpath,'$ORIGIN'
  # the official files keep their debug information (llama.cpp: about 250 MB): stripped they are about 30 MB
  for f in "$JNI/$abi"/*.so; do
    [ "$(basename "$f")" = libttranslator.so ] || "$TC/llvm-strip" "$f"
  done
  # every library a program needs is there (or is a library of Android)
  for f in "$JNI/$abi"/*.so; do
    for n in $("$TC/llvm-readelf" -d "$f" | sed -n 's/.*(NEEDED).*\[\(.*\)\]/\1/p'); do
      case $n in libc.so|libm.so|libdl.so|liblog.so|libandroid.so) ;; *) [ -f "$JNI/$abi/$n" ] || die "$abi/$(basename "$f") needs $n";; esac
    done
  done
  du -sh "$JNI/$abi" | sed "s|$JNI/||"
done

# ---------------------------------------------------------------- licences (assets of the APK)
ASSETS=$HERE/app/src/main/assets
rm -rf "$ASSETS"; mkdir -p "$ASSETS"
cp "$REPO/LICENSE.txt" "$ASSETS/LICENSE.txt"
{ cat "$HERE/THIRD-PARTY.txt"; echo; echo "---- llama.cpp ($LLAMA_TAG) — LICENSE"; echo; cat "$LLAMA_ARM64/LICENSE"; } > "$ASSETS/THIRD-PARTY.txt"

# ---------------------------------------------------------------- the APK
VERSION_CODE=${GITHUB_RUN_NUMBER:-$(git -C "$REPO" rev-list --count HEAD 2>/dev/null || echo 1)}
say "APK (Gradle $GRADLE_VERSION, version $APP_VERSION-android-test, code $VERSION_CODE)"
export ANDROID_HOME=$SDK
"$GRADLE" -p "$HERE" --no-daemon --console=plain --warning-mode=summary -PttVersion="$APP_VERSION" -PttVersionCode="$VERSION_CODE" \
  assembleDebug > "$W/gradle.log" 2>&1 || { tail -40 "$W/gradle.log"; die "gradle failed"; }
APK=$HERE/app/build/outputs/apk/debug/app-debug.apk
[ -f "$APK" ] || die "no APK"
NAME=Ttranslator-$APP_VERSION-android-test.apk
cp "$APK" "$OUT/$NAME"
(cd "$OUT" && sha256sum "$NAME" > "$NAME.sha256")
say "built $OUT/$NAME ($(du -h "$OUT/$NAME" | cut -f1))"
