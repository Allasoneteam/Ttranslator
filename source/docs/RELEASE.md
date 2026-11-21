<!-- The text of the release on GitHub for the version in source/launcher/main.go (appVersion): the release job of
.github/workflows/ci.yml puts it into the draft release made by a push to main. Rewrite it for each version. -->
**Ttranslator 1.3** translates **documents**: pictures, scans and PDFs, Word and LibreOffice files — page by page, with the translation next to the original. The free, open-source **offline translator** runs on Windows, Linux, macOS and Android — a local language model on your own device: no cloud, no account, no telemetry. And it now translates **Japanese, Korean and Hindi**, with new voices for them.

## Downloads

| System | File |
|---|---|
| Windows 10/11, x86-64 | `Ttranslator-1.3-windows-x64.zip` |
| Linux, x86-64 (glibc 2.34+: Ubuntu 22.04+, Debian 12+, Fedora 36+, Arch, CachyOS, openSUSE…) | `Ttranslator-1.3-linux-x64.tar.gz` |
| macOS 13.3 or newer, Apple Silicon (M1 and newer) | `Ttranslator-1.3-macos-arm64.zip` |
| macOS 13.3 or newer, Intel | `Ttranslator-1.3-macos-x64.zip` |
| Android 9 or newer, 64-bit ARM (8 GB of memory or more is best) | `Ttranslator-1.3-android-arm64.apk` |

SHA-256 checksums are in `SHA256SUMS.txt`. Which Mac: Apple menu → About This Mac — “Chip Apple M…” is Apple Silicon, “Processor … Intel” is Intel.

## What’s new in 1.3

- **Documents**: the **File** button (or drag and drop, or Ctrl+V for a picture) opens a picture — a scan, a photo of a page, a screenshot —, a **PDF**, a **Word or LibreOffice document** (.docx, .odt) or a text file (.txt, .tex). Each page shows its picture, its text and the translation side by side; **Save .txt** saves the translation, with the original if you wish.
- **Scans and photos are read by the Gemma 4 model itself** (E2B or E4B). For this it needs one more file of the model, about 0.56 GB, which the program offers to download the first time; it is loaded only while pictures are read. On a computer a page takes one to three minutes.
- **PDFs with text** (most papers) open at once, without the model, with the PDF.js library inside the program; only scanned pages are recognized. In Word and LibreOffice files the text comes by paragraphs, with tables, numbered lists and footnotes; their **formulas become LaTeX** and are kept out of the translation, as everywhere in Ttranslator.
- **New translation languages**: Japanese, Korean and Hindi — 15 in all.
- **The Supertonic 3 voice**: one download (about 130 MB) reads 13 languages — all but Chinese and Latin — with ten voices to choose from; for the first time there are voices for Greek, Arabic, Japanese, Korean and Hindi. The Chinese and Latin voices come right under it in the menu.
- While the model works — recognizing a page, thinking up or checking a lesson — a purple icon spins, and a page shows the time it has taken so far.
- Updating from 1.0–1.2 keeps your models, voices, glossaries and settings.

## Getting started on Android

1. Open `Ttranslator-1.3-android-arm64.apk` on the phone or tablet and allow installing apps from this source (the browser or the file manager). Google Play Protect may say it does not know the developer: **More details → Install anyway**.
2. Start Ttranslator and press **Download** to get the model once (3.35 GB; better over Wi-Fi), or **Skip** and choose a model later. After that the app works offline.
3. The APK is signed with the project's own key. Its certificate's SHA-256 fingerprint: `E3:50:90:EC:9E:C7:60:64:84:D4:9B:AF:AF:6B:AE:EC:03:38:0D:70:04:81:99:0E:72:E1:30:40:01:68:0C:C8`. It installs over 1.2 as an update, keeping the models and data. Uninstalling the app deletes its models, voices, saved translations and glossaries — export what you need first.

**Windows, Linux and Mac:** unpack the archive (Windows, Linux) or drag `Ttranslator.app` into Applications (Mac) — details in [README.md](https://github.com/Allasoneteam/Ttranslator#getting-started). To update, close the program and unpack the new archive over the old folder, or replace the app on a Mac.

## What it does

- Translation between **15 languages** — English, Russian, German, French, Spanish, Italian, Portuguese (Brazil), Greek, Arabic, Japanese, Korean, Hindi, Simplified Chinese, Latin, Swedish — with several variants in different styles, back translation and “why like this?”; editing in the same language; your own glossary; LaTeX formulas kept intact.
- **Documents** page by page: pictures and scans, PDFs, Word and LibreOffice files, text files.
- **Ask the model** about translations, terms and grammar; **reading aloud** with Supertonic and Piper voices; a built-in **test** to compare models on your device.
- **Interface in five languages**: English, Russian, German, Spanish and Chinese.

## Privacy

Your texts and documents never leave the device: the engine listens only on 127.0.0.1 and requires a random key (on Android the program inside the app requires a key of its own too, so other apps cannot read your translations). The network is used only to download the engine, models, the picture files of the models and voices from official sources, with the size and SHA-256 checked, and only after you confirm each download.

## License

MIT, © 2026 Allasoneteam and Ttranslator authors. Third-party components: llama.cpp (MIT), Gemma 4 models and their picture files (Google, ggml-org; Apache 2.0), PDF.js (Mozilla, Apache 2.0, with the JBIG2 decoder of PDFium — BSD-3-Clause, OpenJPEG — BSD-2-Clause, qcms — MIT), sherpa-onnx (Apache 2.0, with espeak-ng, GPL-3.0), the Supertonic 3 voice (OpenRAIL-M) and Piper voices (the license of each voice is shown in the program), webview (MIT), Microsoft Edge WebView2 on Windows; in the Android app also onnxruntime (MIT) and the Go runtime (BSD). Details: `THIRD-PARTY.txt` in the archives; in the Android app — About → “Licences of the programs inside the app”, with the exact sources of espeak-ng.

The full guide is inside the program (Help, in every interface language) and in `README.txt` (installation in five languages, the full guide in Russian). Questions and feedback: Ttranslator@proton.me.

Special thanks to Ivan Gonoskov and Claude Opus 5.5 (Anthropic).
