<!-- The text of the release on GitHub for the version in source/launcher/main.go (appVersion): the release job of
.github/workflows/ci.yml puts it into the draft release made by a push to main. Rewrite it for each version. -->
**Ttranslator 1.2** comes to **Android**: the free, open-source **offline translator** now runs on Windows, Linux, macOS and Android phones and tablets — a local language model on your own device: no cloud, no account, no telemetry. And it translates three more languages: **Italian, Portuguese (Brazil) and Arabic**.

## Downloads

| System | File |
|---|---|
| Windows 10/11, x86-64 | `Ttranslator-1.2-windows-x64.zip` |
| Linux, x86-64 (glibc 2.34+: Ubuntu 22.04+, Debian 12+, Fedora 36+, Arch, CachyOS, openSUSE…) | `Ttranslator-1.2-linux-x64.tar.gz` |
| macOS 13.3 or newer, Apple Silicon (M1 and newer) | `Ttranslator-1.2-macos-arm64.zip` |
| macOS 13.3 or newer, Intel | `Ttranslator-1.2-macos-x64.zip` |
| Android 9 or newer, 64-bit ARM (8 GB of memory or more is best) | `Ttranslator-1.2-android-arm64.apk` |

SHA-256 checksums are in `SHA256SUMS.txt`. Which Mac: Apple menu → About This Mac — “Chip Apple M…” is Apple Silicon, “Processor … Intel” is Intel.

## What’s new in 1.2

- **Ttranslator for Android**: the same program as on a computer, for phones and tablets with Android 9 or newer. The model runs on the device itself (Gemma 4 E2B · Q4_0, 3.35 GB; with 12 GB of memory or more also E4B · Q4_0); reading aloud works too.
- **Translate from any app** on Android: select text → **Ttranslator** in the menu of the selection (or **Share** → Ttranslator) — the text is translated at once.
- On Android a **notification** shows while a model or a voice downloads and while a translation runs, so you can switch to another app; the downloads resume where they stopped.
- **A narrow window and a phone screen**: one column, the panels open in place of the translation window, the less frequent buttons are in the menu **⋮**.
- **New translation languages**: Italian, Portuguese (Brazil) and Arabic — twelve in all. **New voices**: Italian Paola (the voice that reads Latin) and Riccardo, Brazilian Faber; Arabic has no voice yet.
- Updating from 1.0 or 1.1 keeps your models, voices, glossaries and settings.

## Getting started on Android

1. Open `Ttranslator-1.2-android-arm64.apk` on the phone or tablet and allow installing apps from this source (the browser or the file manager). Google Play Protect may say it does not know the developer: **More details → Install anyway**.
2. Start Ttranslator and press **Download** to get the model once (3.35 GB; better over Wi-Fi), or **Skip** and choose a model later. After that the app works offline.
3. The APK is signed with the project's own key. Its certificate's SHA-256 fingerprint: `E3:50:90:EC:9E:C7:60:64:84:D4:9B:AF:AF:6B:AE:EC:03:38:0D:70:04:81:99:0E:72:E1:30:40:01:68:0C:C8`. Future versions are signed with the same key and install over this one as updates, keeping the models and data. Uninstalling the app deletes its models, voices, saved translations and glossaries — export what you need first.

**Windows, Linux and Mac:** unpack the archive (Windows, Linux) or drag `Ttranslator.app` into Applications (Mac) — details in [README.md](https://github.com/Allasoneteam/Ttranslator#getting-started). To update, close the program and unpack the new archive over the old folder, or replace the app on a Mac.

## What it does

- Translation between **12 languages** — English, Russian, German, French, Spanish, Italian, Portuguese (Brazil), Greek, Arabic, Simplified Chinese, Latin, Swedish — with several variants in different styles, back translation and “why like this?”; editing in the same language; your own glossary; LaTeX formulas kept intact.
- **Ask the model** about translations, terms and grammar; **reading aloud** with Piper voices; a built-in **test** to compare models on your device.
- **Interface in five languages**: English, Russian, German, Spanish and Chinese.

## Privacy

Your texts never leave the device: the engine listens only on 127.0.0.1 and requires a random key (on Android the program inside the app requires a key of its own too, so other apps cannot read your translations). The network is used only to download the engine, models and voices from official sources, with the size and SHA-256 checked, and only after you confirm each download.

## License

MIT, © 2026 Allasoneteam and Ttranslator authors. Third-party components: llama.cpp (MIT), Gemma 4 models (Google, Apache 2.0), sherpa-onnx (Apache 2.0, with espeak-ng, GPL-3.0) and Piper voices (license of each voice shown in the program), webview (MIT), Microsoft Edge WebView2 on Windows; in the Android app also onnxruntime (MIT) and the Go runtime (BSD). Details: `THIRD-PARTY.txt` in the archives; in the Android app — About → “Licences of the programs inside the app”, with the exact sources of espeak-ng.

The full guide is inside the program (Help, in every interface language) and in `README.txt` (installation in five languages, the full guide in Russian). Questions and feedback: Ttranslator@proton.me.

Special thanks to Ivan Gonoskov and Claude Opus 5.5 (Anthropic).
