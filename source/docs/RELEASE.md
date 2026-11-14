<!-- The text of the release on GitHub for the version in source/launcher/main.go (appVersion): the release job of
.github/workflows/ci.yml puts it into the draft release made by a push to main. Rewrite it for each version. -->
**Ttranslator 1.1** comes to the **Mac**: the free, open-source **offline translator** now runs on Windows, Linux and macOS (Apple Silicon and Intel) — a local language model on your own computer: no cloud, no account, no telemetry.

## Downloads

| System | File |
|---|---|
| Windows 10/11, x86-64 | `Ttranslator-1.1-windows-x64.zip` |
| Linux, x86-64 (glibc 2.34+: Ubuntu 22.04+, Debian 12+, Fedora 36+, Arch, CachyOS, openSUSE…) | `Ttranslator-1.1-linux-x64.tar.gz` |
| macOS 13.3 or newer, Apple Silicon (M1 and newer) | `Ttranslator-1.1-macos-arm64.zip` |
| macOS 13.3 or newer, Intel | `Ttranslator-1.1-macos-x64.zip` |

SHA-256 checksums are in `SHA256SUMS.txt`. Which Mac: Apple menu → About This Mac — “Chip Apple M…” is Apple Silicon, “Processor … Intel” is Intel. Android is in the works.

## What’s new in 1.1

- **Ttranslator for Mac**: `Ttranslator.app` for macOS 13.3 or newer, on Macs with Apple silicon (the model runs on the graphics cores, Metal) and with Intel processors. The llama.cpp engine is inside the app.
- On a Mac, settings, models, voices and saved translations live in `~/Library/Application Support/Ttranslator` — the **Open the data folder** button is in Settings and in the model menu. The app itself is never written to, so updating is just replacing it.
- The app window on the Mac: the menu in the interface language, ⌘C/⌘V, the macOS Save and Open dialogs, ⌘+Enter to translate.
- **Reading aloud** works on the Mac too.
- **New voices** on every system: French — Siwis (female) and Pierre (male); male voices for English (Ryan, non-commercial use only), German (Thorsten), Spanish (Davefx) and Swedish (NST). Download them in the model menu.
- Updating from 1.0 keeps your models, voices, glossaries and settings.

## Getting started on a Mac

1. Double-click the downloaded zip (Safari usually unpacks it by itself) and drag `Ttranslator.app` into Applications.
2. The app has no Apple developer signature, so macOS asks once. On macOS 15 Sequoia and newer: double-click the app, click **Done**, then Apple menu → **System Settings → Privacy & Security → Open Anyway**. On macOS 13–14: Control-click the app → **Open** → **Open**.
3. Press **Download** to get the Gemma 4 E2B model once (3.35 GB; you see where it comes from and where it goes), or **Skip** and choose a model later. After that the program works offline.

**Windows and Linux:** unpack the archive into a folder you can write to and start `Ttranslator.exe` or `./ttranslator-linux` — details in [README.md](https://github.com/Allasoneteam/Ttranslator#getting-started). To update from 1.0, close the program and unpack the new archive over the old folder.

## What it does

- Translation between **9 languages** — English, Russian, German, French, Spanish, Greek, Simplified Chinese, Latin, Swedish — with several variants in different styles, back translation and “why like this?”; editing in the same language; your own glossary; LaTeX formulas kept intact.
- **Ask the model** about translations, terms and grammar; **reading aloud** with Piper voices; a built-in **test** to compare models on your computer.
- **Interface in five languages**: English, Russian, German, Spanish and Chinese.

## Privacy

Your texts never leave the computer: the engine listens only on 127.0.0.1 and requires a random key. The network is used only to download the engine, models and voices from official sources, with the size and SHA-256 checked, and only after you confirm each download.

## License

MIT, © 2026 Allasoneteam and Ttranslator authors. Third-party components: llama.cpp (MIT), Gemma 4 models (Google, Apache 2.0), sherpa-onnx (Apache 2.0, with espeak-ng, GPL-3.0) and Piper voices (license of each voice shown in the program), webview (MIT), Microsoft Edge WebView2 on Windows. Details: `THIRD-PARTY.txt` in the archives.

The full guide is inside the program (Help, in every interface language) and in `README.txt` (installation in five languages, the full guide in Russian). Questions and feedback: Ttranslator@proton.me.

Special thanks to Ivan Gonoskov and Claude Opus 5.5 (Anthropic).
