# Ttranslator

A free, open-source **offline translator** that runs a local language model on your own computer — no cloud, no
account, no telemetry. It shows several translation variants in different styles, edits text in the same language,
follows your own glossary, answers questions about a translation and can read texts aloud.

> **Status:** pre-release (0.9.x). The repository is private until version 1.0. The user guide is in Russian
> ([README.txt](README.txt)); the interface is available in Russian, English and German.

## Features

- **9 languages:** Russian, English, German, French, Spanish, Greek, Simplified Chinese, Latin, Swedish.
- **Several variants at once:** neutral first, then the styles you choose (scientific, business, casual, concise or
  your own description), with optional context; another variant, back translation and “why like this?” for each.
- **Editing in the same language:** a corrected version with the changes highlighted, rephrasings and remarks.
- **Your glossary:** term tables (TSV, editable in Excel) whose terms are passed to the model when they occur.
- **LaTeX formulas** (`$…$`, `$$…$$`) are never translated or damaged.
- **Ask the model:** a chat about translations, terms and grammar; mini lessons and exercises with checking.
- **Reading aloud:** Piper voices for Russian, English, German, Spanish, Chinese and Swedish through the sherpa-onnx
  program, downloaded on demand.
- **Saved translations** in plain files, import and export (TSV, TXT).
- A built-in **test** (“Тест”) that checks a model on your computer and writes a report.

## Requirements

- Windows 10/11 or Linux, x86-64; a processor is enough (no graphics card needed); 8 GB of memory.
- About 4–9 GB of disk space for a model.
- Internet only once, to download a model (and voices, if you want them); the release archives already contain the
  engine.

## Getting started

1. Unpack the release archive (`Ttranslator-<version>-windows-x64.zip` or `…-linux-x64.tar.gz`) into any folder:
   nothing is installed into the system, the folder `Ttranslator` is portable. The
   [llama.cpp](https://github.com/ggml-org/llama.cpp) engine is already inside.
2. Start `Ttranslator.exe` (Windows) or `ttranslator-linux` (Linux).
3. On the first start the program shows what it will download, from where and to which folder: a Gemma 4 model (and
   the engine too, if the folder has none — when built from source). After that it works offline. Or press **Skip**:
   the window opens at once without a model, and you choose and download one later in the model menu.

The app window is the program's own window (maximized at start) on the web engine of the system — Microsoft Edge
WebView2 on Windows, WebKitGTK 4.1 on Linux; if it cannot open, an Edge/Chrome window without tabs opens instead.
The interface can also run in a tab of your browser.

### Linux

Any 64-bit x86 Linux from about 2022 on works: CachyOS, Arch, Manjaro, EndeavourOS, Ubuntu 22.04+, Debian 12+,
Linux Mint 21+, Fedora 36+, openSUSE Tumbleweed and Leap 16, and systems based on them (the engine needs glibc 2.34
and libstdc++ of GCC 12 or newer).

1. Packages for the app window and its sound (once; most systems have some of them already):

   | System | Command |
   |---|---|
   | CachyOS, Arch, Manjaro, EndeavourOS | `sudo pacman -S --needed webkit2gtk-4.1 gst-plugins-base gst-plugins-good` |
   | Ubuntu, Debian, Linux Mint, Pop!_OS, Zorin OS, elementary OS, MX Linux | `sudo apt install libwebkit2gtk-4.1-0 gstreamer1.0-plugins-good libgomp1` |
   | Fedora | `sudo dnf install webkit2gtk4.1 gstreamer1-plugins-good libgomp` |
   | openSUSE Tumbleweed, Leap 16 | `sudo zypper install libwebkit2gtk-4_1-0 gstreamer-plugins-good libgomp1` |

   Without them the program still works, in a Chrome/Chromium window or a tab of the default browser.
2. Unpack and start (in a folder you can write to):

   ```sh
   cd ~
   tar -xzf ~/Downloads/Ttranslator-<version>-linux-x64.tar.gz
   cd ~/Ttranslator
   ./ttranslator-linux
   ```

   Closing the terminal closes the program too — the menu shortcut avoids the terminal:
3. `./ttranslator-linux --shortcut` puts Ttranslator into the menu of applications (KDE Plasma, GNOME, Xfce…) with
   its icon; run it again after moving the folder. To uninstall, delete the folder and, if you made the shortcut,
   `~/.local/share/applications/ttranslator.desktop` and `~/.local/share/icons/hicolor/256x256/apps/ttranslator.png`.

If something goes wrong: an empty (white) app window happens with NVIDIA graphics — the program switches WebKitGTK to
its older renderer there by itself; if it is still empty, start with `env WEBKIT_DISABLE_COMPOSITING_MODE=1
./ttranslator-linux` or choose “Browser tab” in the settings. No sound in the app window: install the GStreamer
plugins from the table. GLIBC/GLIBCXX errors of the engine: the system is older (Ubuntu 20.04, Debian 11,
openSUSE Leap 15, RHEL/AlmaLinux/Rocky 9) — build llama.cpp yourself and set `engine_path` in `config.json`.
NixOS needs `programs.nix-ld`. ARM and 32-bit Linux are not supported yet.

### Updating and moving to another computer

Everything the program downloads and remembers is in its folder: `models` (with the voices in `models/voices`),
`engine` (llama.cpp and sherpa-onnx, one folder per system), `data` (saved translations, glossaries, test reports,
logs) and `config.json`. To update, unpack the new archive where the `Ttranslator` folder is, replacing files — none
of these are in the archive (only `ui/tests.txt` is replaced). To move to another computer with the same system, copy
the whole folder; to another system, unpack that system's archive and copy `models`, `data` and `config.json` into it.
Voices copied without the speech program work too: the model menu then offers to download only sherpa-onnx (20–30
MB), and a sherpa-onnx folder copied into `engine/<system>` by hand is found by itself.

## Privacy

- No telemetry, no accounts, no analytics.
- Your texts never leave the computer: the engine listens only on `127.0.0.1` and requires a random key.
- The network is used only to download the engine, models and voices — from official sources, with the size and
  SHA-256 checked, and only after you confirm each download.

## Building from source

- The launcher is written in Go using **only the standard library** (Go 1.24+):
  `sh source/build.sh` builds `Ttranslator.exe` and `ttranslator-linux` next to `README.txt`.
- The app window (`source/window`, C++ on the [webview](https://github.com/webview/webview) library) is built by the
  same script when its tools are installed (Ubuntu/Debian):
  `g++ pkg-config libgtk-3-dev libwebkit2gtk-4.1-dev g++-mingw-w64-x86-64`.
- The interface is a single file, `ui/index.html`, without external resources.

Release archives: `sh source/release.sh [out-dir]` after the build — the programs, the interface, the guides, the
sources, the licences (`THIRD-PARTY.txt`) and the engine unpacked; SHA-256 in `SHA256SUMS.txt`. GitHub Actions makes
them on every change as test builds (artifacts of the run).

## Tests

`bash source/tests/run_all.sh` runs all automated suites on Linux (Go unit tests, interface tests in Chromium with
a tiny stand-in model, the app window under a virtual screen). See [source/tests/README.md](source/tests/README.md).

## Repository layout

| Path | What |
|---|---|
| `ui/index.html` | the whole interface (settings for prompts, languages and styles are at its top) |
| `ui/tests.txt` | phrases for the built-in test |
| `source/launcher` | the launcher: downloads and runs the engine, serves the interface, files of the user |
| `source/window` | the app window program (webview) |
| `source/tests` | automated tests |
| `source/docs` | architecture, development, roadmap and changelog (in Russian) |
| `README.txt` | the user guide (in Russian) |

## License

MIT, © 2026 Allasoneteam and Ttranslator authors — see [LICENSE](LICENSE) (the program folder carries the licence as
`LICENSE.txt`).

Third-party components:

- [llama.cpp](https://github.com/ggml-org/llama.cpp) (MIT) — the engine, downloaded on the first start.
- Gemma 4 models (Google, Apache 2.0) — downloaded after confirmation; your own `.gguf` files work too.
- [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) (Apache 2.0, with espeak-ng inside, GPL-3.0) and Piper voices
  (the licence of each voice is shown in the program; some are for non-commercial use) — downloaded on demand from the
  sherpa-onnx releases.
- [webview](https://github.com/webview/webview) 0.12.0 (MIT) — compiled into the app window program.
- Microsoft Edge WebView2 SDK header (BSD-style licence, `source/window/webview2/LICENSE.txt`) — for the Windows
  build of the app window; the WebView2 Runtime itself is part of Windows.
