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
- Internet only once, to download the engine and a model (and voices, if you want them).

## Getting started

1. Unpack the release archive into any folder (nothing is installed into the system; the folder is portable).
2. Start `Ttranslator.exe` (Windows) or `ttranslator-linux` (Linux).
3. On the first start the program shows what it will download, from where and to which folder: the
   [llama.cpp](https://github.com/ggml-org/llama.cpp) engine and a Gemma 4 model. After that it works offline.

The app window is the program's own window (maximized at start) on the web engine of the system — Microsoft Edge
WebView2 on Windows, WebKitGTK 4.1 on Linux; if it cannot open, an Edge/Chrome window without tabs opens instead.
The interface can also run in a tab of your browser.

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
