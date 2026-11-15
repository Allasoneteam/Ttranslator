# Ttranslator

A free, open-source **offline translator** that runs a local language model on your own computer — no cloud, no
account, no telemetry. It shows several translation variants in different styles, edits text in the same language,
follows your own glossary, answers questions about a translation and can read texts aloud.

> **Version 1.2** for **Windows, Linux, macOS and Android** — [download](#download). The interface is in English,
> Russian, German, Spanish and Chinese; the program has its full guide (Help) in each of them.
> [README.txt](README.txt) has the installation in these five languages and the full guide in Russian; the
> installation is also [below](#installation-in-other-languages) in Russian, German, Spanish and Chinese.

## Features

- **12 languages:** Russian, English, German, French, Spanish, Italian, Portuguese (Brazil), Greek, Arabic, Simplified
  Chinese, Latin, Swedish.
- **Several variants at once:** neutral first, then the styles you choose (scientific, business, casual, concise or
  your own description), with optional context; another variant, back translation and “why like this?” for each.
- **Editing in the same language:** a corrected version with the changes highlighted, rephrasings and remarks.
- **Your glossary:** term tables (TSV, editable in Excel) whose terms are passed to the model when they occur.
- **LaTeX formulas** (`$…$`, `$$…$$`) are never translated or damaged.
- **Ask the model:** a chat about translations, terms and grammar; mini lessons and exercises with checking.
- **Reading aloud:** Piper voices for Russian, English, German, French, Spanish, Italian, Portuguese (Brazil),
  Chinese and Swedish (a female and a male one for English, German, French, Spanish, Italian and Swedish) through the
  sherpa-onnx program, downloaded on demand; Latin is read by the Italian voice Paola with the church or the classical
  pronunciation (your choice; the voice is downloaded once), the stress marked by the rules of Latin.
- **Saved translations** in plain files, import and export (TSV, TXT).
- A built-in **test** that checks a model on your computer and writes a report: a quick one (two Latin sayings,
  *Audentes fortuna iuvat* and *Cogito, ergo sum*, into the interface language and back — about a minute) and a full
  one with phrase pairs in any two of the twelve languages; each task shows the source text, the model translation
  and the reference.
- **Settings** for the chat (temperature; short, normal or detailed answers) and the speed of reading aloud.
- **Interface in five languages:** English (on the first start), Russian, German, Spanish and Chinese.
- **Android:** the same program on a phone or a tablet — translate text selected in any app (“Ttranslator” in the
  menu of the selection, or Share), a layout for the phone screen, a notification while a model downloads or a
  translation runs.

## Requirements

- Windows 10/11 or Linux, x86-64; macOS 13.3 or newer on Apple Silicon or Intel; a processor is enough (no graphics
  card needed); 8 GB of memory.
- Android 9 or newer on a 64-bit ARM processor (arm64-v8a — nearly every phone and tablet of the last years); 8 GB of
  memory or more is best (Gemma 4 E2B; from 12 GB also E4B).
- About 4–9 GB of disk space for a model (on Android 3.35 GB for E2B, 5.2 GB for E4B).
- Internet only once, to download a model (and voices, if you want them); the release archives and the Android app
  already contain the engine.

## Download

| System | Download |
|---|---|
| **Windows** 10/11, x64 | [⬇ Download for Windows](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-windows-x64.zip) |
| **Linux**, x86-64 | [⬇ Download for Linux](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-linux-x64.tar.gz) |
| **macOS** 13.3+, Apple Silicon (M1 and newer) | [⬇ Download for Mac (Apple Silicon)](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-macos-arm64.zip) |
| **macOS** 13.3+, Intel | [⬇ Download for Mac (Intel)](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-macos-x64.zip) |
| **Android** 9+, 64-bit ARM | [⬇ Download for Android (APK)](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-android-arm64.apk) |

Which Mac: Apple menu → About This Mac — “Chip Apple M…” is Apple Silicon, “Processor … Intel” is Intel. Checksums:
[SHA256SUMS.txt](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/SHA256SUMS.txt). All versions and what is new in each:
[Releases](https://github.com/Allasoneteam/Ttranslator/releases). The archives contain the program and the engine;
the model (3.35 GB) is downloaded on the first start, after your confirmation. Installation: Windows — below,
[Linux](#linux), [macOS](#macos), [Android](#android).

## Getting started

1. Unpack the release archive (`Ttranslator-<version>-windows-x64.zip` or `…-linux-x64.tar.gz`; for a Mac see
   [macOS](#macos)) into any folder:
   nothing is installed into the system, the folder `Ttranslator` is portable. The
   [llama.cpp](https://github.com/ggml-org/llama.cpp) engine is already inside.
2. Start `Ttranslator.exe` (Windows) or `ttranslator-linux` (Linux). The welcome window lets you choose the interface
   language (English at first), the window type and whether to load the model at start.
3. On the first start the program shows what it will download, from where and to which folder: a Gemma 4 model (and
   the engine too, if the folder has none — when built from source). After that it works offline. Or press **Skip**:
   the window opens at once without a model, and you choose and download one later in the model menu.

Windows may show “Windows protected your PC”, because the program is not signed: click **More info** → **Run
anyway**. Unpack the archive into a folder you can write to (the desktop, Documents — not Program Files).

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
   its icon; run it again after moving the folder.

If something goes wrong: an empty (white) app window happens with NVIDIA graphics — the program switches WebKitGTK to
its older renderer there by itself; if it is still empty, start with `env WEBKIT_DISABLE_COMPOSITING_MODE=1
./ttranslator-linux` or choose “Browser tab” in the settings. No sound in the app window: install the GStreamer
plugins from the table. GLIBC/GLIBCXX errors of the engine: the system is older (Ubuntu 20.04, Debian 11,
openSUSE Leap 15, RHEL/AlmaLinux/Rocky 9) — build llama.cpp yourself and set `engine_path` in `config.json`.
NixOS needs `programs.nix-ld`. ARM and 32-bit Linux are not supported yet.

### macOS

macOS 13.3 Ventura or newer: `Ttranslator-<version>-macos-arm64.zip` for Apple Silicon (the engine computes on the
graphics cores, Metal) or `…-macos-x64.zip` for Intel (on the processor). Reading aloud works on all these versions
(sherpa-onnx v1.13.8 on the Mac).

1. Double-click the archive (Safari usually unpacks it by itself) and drag `Ttranslator.app` into Applications.
2. The app has no Apple developer signature, only an ad-hoc one, so macOS asks once: on macOS 15 Sequoia and newer
   double-click the app, click **Done**, then **System Settings → Privacy & Security → Open Anyway**; on macOS 13–14
   Control-click the app → **Open** → **Open**.
3. The window opens with the welcome window; press **Download** (the model) or **Skip**, as on the other systems.

The app itself is read only: models, voices, saved translations, glossaries, logs and settings are in
`~/Library/Application Support/Ttranslator` (Settings → **Open the data folder**). To update, replace the app in
Applications; to uninstall, move it to the Trash and delete that folder (and the window's data in
`~/Library/WebKit/io.github.allasoneteam.ttranslator` and `~/Library/Caches/io.github.allasoneteam.ttranslator`). If the app still does not open,
`xattr -dr com.apple.quarantine /Applications/Ttranslator.app` in Terminal helps.

### Android

Android 9 or newer, a 64-bit ARM processor; 8 GB of memory or more is best. The app is not in Google Play: it is
installed from its file, `Ttranslator-<version>-android-arm64.apk` on the release page.

1. Open the APK on the phone or tablet (from the browser's downloads or a file manager). Android asks to allow
   installing apps from this source (the browser or the file manager) — allow it, then **Install**. Google Play Protect
   may say it does not know the developer: **More details → Install anyway** (or “Install without scanning”).
2. Start Ttranslator and press **Download** in the welcome window: the model Gemma 4 E2B · Q4_0 (3.35 GB) is
   downloaded once — over Wi-Fi if you can. While it downloads (and while a translation runs) a notification
   “Ttranslator” is shown, so you can switch to another app. After that the app works offline. With 12 GB of memory
   or more the model menu also offers E4B · Q4_0 (5.2 GB: better, slower).
3. **Translate from any app:** select text → **Ttranslator** in the menu of the selection (or **Share** →
   Ttranslator): the text comes into the field and is translated at once. The buttons that do not fit at the top are in
   the menu **⋮**; **Back** closes menus and panels.

Every Ttranslator APK is signed with the project's own key; its certificate's SHA-256 fingerprint is

    E3:50:90:EC:9E:C7:60:64:84:D4:9B:AF:AF:6B:AE:EC:03:38:0D:70:04:81:99:0E:72:E1:30:40:01:68:0C:C8

(`android/signing-cert-sha256.txt`; check it, for example, with `apksigner verify --print-certs`). An update must
carry the same certificate — Android refuses anything else.

- **Update:** open the APK of the new version → **Update**: models, voices, settings, saved translations and glossaries
  stay. The app does not update itself: new versions are on the [Releases](https://github.com/Allasoneteam/Ttranslator/releases) page.
- **Uninstall:** long-press the icon → **Uninstall** (or Settings → Apps → Ttranslator → Uninstall). The models,
  voices, saved translations and glossaries are deleted with the app — export what you need first (the menus of
  “Saved” and of the glossary). If Android offers to keep the app's data and you agree, they stay and come back when
  you install Ttranslator again.
- **Files:** on Android 11 and newer the program folder is `Android/data/io.github.allasoneteam.ttranslator/files`
  (models, voices, `data`, `config.json`), visible from a computer over USB. On Android 9 and 10 it is in the app's
  internal storage.

### Updating, uninstalling and moving to another computer

Everything the program downloads and remembers is in its folder (on a Mac — in
`~/Library/Application Support/Ttranslator`): `models` (with the voices in `models/voices`), `engine` (llama.cpp and
sherpa-onnx, one folder per system), `data` (saved translations, glossaries, test reports, logs) and `config.json`. None of these are in the release archive, so an update keeps them (only `ui/tests.txt`, the
phrases of the full test, is replaced).

- **Update on Windows:** close the program, unpack the new archive where the `Ttranslator` folder is (“Extract all”
  → the folder that contains `Ttranslator`) and confirm “Replace the files in the destination”. If you renamed the
  folder, copy the contents of the new `Ttranslator` folder into yours, replacing files.
- **Update on Linux:** close the program and unpack the new archive into the same place:
  `cd ~ && tar -xzf ~/Downloads/Ttranslator-<version>-linux-x64.tar.gz`. The menu shortcut keeps working.
- **Uninstall on Windows:** close the program and delete its folder. Nothing else is left: the program installs
  nothing into the system and writes nothing to the registry.
- **Uninstall on Linux:** close the program and delete its folder; if you made the shortcut, also
  `~/.local/share/applications/ttranslator.desktop` and `~/.local/share/icons/hicolor/256x256/apps/ttranslator.png`;
  the data of the app window is in `~/.local/share/ttranslator` and `~/.cache/ttranslator`.
- **Another computer:** with the same system, copy the whole folder; with another system, unpack that system's
  archive and copy `models`, `data` and `config.json` into it.
Voices copied without the speech program work too: the model menu then offers to download only sherpa-onnx (20–30
MB), and a sherpa-onnx folder copied into `engine/<system>` by hand is found by itself.

## Support and thanks

The creators will be glad of any support via GitHub Sponsors: [github.com/Allasoneteam](https://github.com/Allasoneteam)
and [github.com/sponsors/Allasoneteam](https://github.com/sponsors/Allasoneteam). Questions, suggestions and feedback:
Ttranslator@proton.me.

Special thanks to Ivan Gonoskov and Claude Opus 5.5 (Anthropic).

## Translations

The interface texts are in `ui/index.html` (`I18N`, `HELP`, `ABOUT` and others: the key is the Russian text) and
the launcher's messages in `source/launcher/i18n.go`. The Spanish and Chinese translations are new in 1.0 and have
not yet been reviewed by native speakers — corrections are welcome.

## Privacy

- No telemetry, no accounts, no analytics.
- Your texts never leave the computer: the engine listens only on `127.0.0.1` and requires a random key. On Android
  the program inside the app requires a key of its own too, so other apps of the phone cannot read your translations.
- The network is used only to download the engine, models and voices — from official sources, with the size and
  SHA-256 checked, and only after you confirm each download.

## Building from source

- The launcher is written in Go using **only the standard library** (Go 1.24+):
  `sh source/build.sh` builds `Ttranslator.exe` and `ttranslator-linux` next to `README.txt`.
- The app window (`source/window`, C++ on the [webview](https://github.com/webview/webview) library) is built by the
  same script when its tools are installed (Ubuntu/Debian):
  `g++ pkg-config libgtk-3-dev libwebkit2gtk-4.1-dev g++-mingw-w64-x86-64`.
- The interface is a single file, `ui/index.html`, without external resources.
- macOS (on a Mac with Xcode or its Command Line Tools): `sh source/release-macos.sh x64|arm64` builds
  `Ttranslator.app` (the launcher, the app window on Cocoa and WKWebView, the engine inside, an ad-hoc signature) and
  its zip archive.

- Android (`android/`, see [android/README.md](android/README.md)): the same launcher, built for Android, the
  official llama.cpp build for Android and sherpa-onnx inside an APK; the app is a small Java shell with a WebView
  around `ui/index.html`. `android/build.sh` builds the APK (Android SDK and NDK, Gradle); GitHub Actions builds it
  and checks it in the Android emulator on every change (`android/ci.sh`) and signs the release APK with the
  project's key (kept in the repository's secrets, never in the repository).

Release archives: `sh source/release.sh [out-dir]` after the build — the programs, the interface, the guides, the
sources, the licences (`THIRD-PARTY.txt`) and the engine unpacked; SHA-256 in `SHA256SUMS.txt`. GitHub Actions makes
them on every change as test builds (artifacts of the run), the macOS archives too (`source/ci/macos.sh` on
the Macs of GitHub Actions).

## Tests

`bash source/tests/run_all.sh` runs all automated suites on Linux (Go unit tests, interface tests in Chromium with
a tiny stand-in model, the app window under a virtual screen). See [source/tests/README.md](source/tests/README.md).

## Repository layout

| Path | What |
|---|---|
| `ui/index.html` | the whole interface (settings for prompts, languages and styles are at its top) |
| `ui/tests.txt` | phrase pairs for the built-in test (`EN:` / `RU:` / `LA:` … lines) |
| `source/launcher` | the launcher: downloads and runs the engine, serves the interface, files of the user |
| `source/window` | the app window program (webview) |
| `source/macos`, `source/release-macos.sh` | `Info.plist` and the build of `Ttranslator.app` (macOS) |
| `android` | the Android app: its Java shell, the build (`build.sh`), the check in the emulator (`test/`), licences |
| `source/ci` | the build and checks on the Macs of GitHub Actions |
| `source/tests` | automated tests |
| `source/docs` | architecture, development, roadmap and changelog (in Russian) |
| `README.txt` | installation in five languages and the full user guide in Russian |

## License

MIT, © 2026 Allasoneteam and Ttranslator authors — see [LICENSE](LICENSE) (the program folder carries the licence as
`LICENSE.txt`).

Third-party components:

- [llama.cpp](https://github.com/ggml-org/llama.cpp) (MIT) — the engine, in the release archives (and in
  `Ttranslator.app`); downloaded on the first start when built from source.
- Gemma 4 models (Google, Apache 2.0) — downloaded after confirmation; your own `.gguf` files work too.
- [sherpa-onnx](https://github.com/k2-fsa/sherpa-onnx) (Apache 2.0, with espeak-ng inside, GPL-3.0) and Piper voices
  (the licence of each voice is shown in the program; some are for non-commercial use) — downloaded on demand from the
  sherpa-onnx releases.
- [webview](https://github.com/webview/webview) 0.12.0 (MIT) — compiled into the app window program.
- In the Android app: llama.cpp (MIT), sherpa-onnx (Apache 2.0) with espeak-ng (GPL-3.0; the app links the exact
  sources) and onnxruntime (MIT), the Go runtime (BSD) — the full licence texts are inside the APK (About →
  “Licences of the programs inside the app”, `android/THIRD-PARTY.txt`).
- Microsoft Edge WebView2 SDK header (BSD-style licence, `source/window/webview2/LICENSE.txt`) — for the Windows
  build of the app window; the WebView2 Runtime itself is part of Windows.

## Installation in other languages

<details>
<summary>Русский</summary>

Скачать: [Windows](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-windows-x64.zip) · [Linux](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-linux-x64.tar.gz) ·
[Mac — Apple Silicon](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-macos-arm64.zip) · [Mac — Intel](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-macos-x64.zip)
· [Android (APK)](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-android-arm64.apk)
(все версии — [Releases](https://github.com/Allasoneteam/Ttranslator/releases)).

1. Распакуйте архив `Ttranslator-<версия>-windows-x64.zip` (Windows) или `…-linux-x64.tar.gz` (Linux) в любую папку,
   куда можно писать (не в Program Files): получится переносная папка `Ttranslator`, в систему ничего не
   устанавливается. Движок llama.cpp уже внутри.
2. Запустите `Ttranslator.exe` (Windows) или `./ttranslator-linux` (Linux). При первом запуске интерфейс английский:
   выберите «Русский» в списке «Interface language» в окне приветствия.
3. Нажмите «Скачать»: программа покажет, что, откуда и в какую папку скачает (модель Gemma 4, 3,35 ГБ), и дальше
   работает без интернета. Или «Пропустить» — модель можно выбрать потом в меню моделей.

Mac: `Ttranslator-<версия>-macos-arm64.zip` (Apple Silicon) или `…-macos-x64.zip` (Intel), macOS 13.3 и
новее; перетащите `Ttranslator.app` в «Программы»; при первом запуске macOS спросит разрешения: в macOS 15 и новее —
«Системные настройки → Конфиденциальность и безопасность → Всё равно открыть», в macOS 13–14 — щелчок с Control →
«Открыть». Данные — в `~/Library/Application Support/Ttranslator` («Настройки» → «Открыть папку данных»).

Windows может показать «Система Windows защитила ваш компьютер» (программа не подписана): «Подробнее» → «Выполнить в
любом случае». Linux: пакеты для окна и звука — в таблице раздела [Linux](#linux) выше; `./ttranslator-linux
--shortcut` добавляет программу в меню приложений.

Обновление: закройте программу и распакуйте новый архив туда же, где лежит папка `Ttranslator`, с заменой файлов —
модели, голоса, переводы, словари и настройки останутся. Удаление: закройте программу и удалите её папку (в Linux —
ещё ярлык и данные окна, см. [выше](#updating-uninstalling-and-moving-to-another-computer)). Подробная инструкция — в
[README.txt](README.txt).

Android (9 и новее, 64-битный процессор ARM; памяти — лучше от 8 ГБ): откройте файл
`Ttranslator-<версия>-android-arm64.apk` на телефоне или планшете и разрешите установку из этого источника; Google
Play Защита может предупредить о неизвестном разработчике — «Всё равно установить». Обновление — APK новой версии →
«Обновить» (модели и данные остаются; все версии подписаны одним ключом, отпечаток — в разделе [Android](#android)).
Удаление — долгое нажатие на значок → «Удалить»: модели, голоса, сохранённое и словари удаляются вместе с приложением
(если Android не предложит сохранить данные приложения).
</details>

<details>
<summary>Deutsch</summary>

Herunterladen: [Windows](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-windows-x64.zip) · [Linux](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-linux-x64.tar.gz) ·
[Mac – Apple Silicon](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-macos-arm64.zip) · [Mac – Intel](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-macos-x64.zip)
· [Android (APK)](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-android-arm64.apk)
(alle Versionen: [Releases](https://github.com/Allasoneteam/Ttranslator/releases)).

1. Entpacken Sie das Archiv `Ttranslator-<Version>-windows-x64.zip` (Windows) oder `…-linux-x64.tar.gz` (Linux) in
   einen Ordner, in den Sie schreiben dürfen (nicht nach „Programme“): Es entsteht der portable Ordner `Ttranslator`,
   im System wird nichts installiert. Die Engine llama.cpp ist schon enthalten.
2. Starten Sie `Ttranslator.exe` (Windows) oder `./ttranslator-linux` (Linux). Beim ersten Start ist die Oberfläche
   englisch: Wählen Sie im Begrüßungsfenster in der Liste „Interface language“ „Deutsch“.
3. Klicken Sie auf „Herunterladen“: Das Programm zeigt, was es woher in welchen Ordner lädt (ein Gemma-4-Modell,
   3,35 GB), und arbeitet danach ohne Internet. Oder „Überspringen“ — das Modell wählen Sie später im Modellmenü.

Mac: `Ttranslator-<Version>-macos-arm64.zip` (Apple Silicon) oder `…-macos-x64.zip` (Intel), macOS 13.3
und neuer; ziehen Sie `Ttranslator.app` in „Programme“; beim ersten Start fragt macOS nach: unter macOS 15 und neuer
„Systemeinstellungen → Datenschutz & Sicherheit → Dennoch öffnen“, unter macOS 13–14 mit gedrückter Control-Taste
klicken → „Öffnen“. Die Daten liegen in `~/Library/Application Support/Ttranslator` („Einstellungen“ → „Datenordner
öffnen“).

Windows zeigt eventuell „Der Computer wurde durch Windows geschützt“ (das Programm ist nicht signiert): „Weitere
Informationen“ → „Trotzdem ausführen“. Linux: die Pakete für Fenster und Ton stehen in der Tabelle im Abschnitt
[Linux](#linux) oben; `./ttranslator-linux --shortcut` legt das Programm ins Anwendungsmenü.

Aktualisieren: Schließen Sie das Programm und entpacken Sie das neue Archiv dorthin, wo der Ordner `Ttranslator`
liegt, und ersetzen Sie die Dateien — Modelle, Stimmen, Übersetzungen, Glossare und Einstellungen bleiben erhalten.
Deinstallieren: Schließen Sie das Programm und löschen Sie seinen Ordner (unter Linux auch die Verknüpfung und die
Fensterdaten, siehe [oben](#updating-uninstalling-and-moving-to-another-computer)). Mehr in [README.txt](README.txt).

Android (9 oder neuer, 64-Bit-ARM-Prozessor; am besten 8 GB Arbeitsspeicher oder mehr): Öffnen Sie die Datei
`Ttranslator-<Version>-android-arm64.apk` auf dem Telefon oder Tablet und erlauben Sie die Installation aus dieser
Quelle; Google Play Protect warnt womöglich vor einem unbekannten Entwickler – „Trotzdem installieren“. Aktualisieren:
APK der neuen Version → „Aktualisieren“ (Modelle und Daten bleiben; alle Versionen sind mit einem Schlüssel signiert,
Fingerabdruck im Abschnitt [Android](#android)). Deinstallieren: Symbol lange drücken → „Deinstallieren“ – Modelle,
Stimmen, Gespeichertes und Glossare werden mit der App gelöscht (wenn Android nicht anbietet, die App-Daten zu
behalten).
</details>

<details>
<summary>Español</summary>

Descargar: [Windows](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-windows-x64.zip) · [Linux](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-linux-x64.tar.gz) ·
[Mac — Apple Silicon](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-macos-arm64.zip) · [Mac — Intel](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-macos-x64.zip)
· [Android (APK)](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-android-arm64.apk)
(todas las versiones: [Releases](https://github.com/Allasoneteam/Ttranslator/releases)).

1. Descomprima el archivo `Ttranslator-<versión>-windows-x64.zip` (Windows) o `…-linux-x64.tar.gz` (Linux) en una
   carpeta en la que pueda escribir (no en Archivos de programa): obtendrá la carpeta portátil `Ttranslator`; no se
   instala nada en el sistema. El motor llama.cpp ya está dentro.
2. Inicie `Ttranslator.exe` (Windows) o `./ttranslator-linux` (Linux). En el primer inicio la interfaz está en inglés:
   elija «Español» en la lista «Interface language» de la ventana de bienvenida.
3. Pulse «Descargar»: el programa muestra qué descarga, de dónde y a qué carpeta (un modelo Gemma 4, 3,35 GB), y
   después funciona sin internet. O «Omitir»: el modelo se elige más tarde en el menú de modelos.

Mac: `Ttranslator-<versión>-macos-arm64.zip` (Apple Silicon) o `…-macos-x64.zip` (Intel), macOS 13.3 o
posterior; arrastre `Ttranslator.app` a Aplicaciones; en el primer inicio macOS pide permiso: en macOS 15 y
posteriores, «Ajustes del Sistema → Privacidad y seguridad → Abrir igualmente»; en macOS 13–14, clic con Control →
«Abrir». Los datos están en `~/Library/Application Support/Ttranslator` («Ajustes» → «Abrir la carpeta de datos»).

Windows puede mostrar «Windows protegió su PC» (el programa no está firmado): «Más información» → «Ejecutar de todas
formas». Linux: los paquetes para la ventana y el sonido están en la tabla de la sección [Linux](#linux) de arriba;
`./ttranslator-linux --shortcut` añade el programa al menú de aplicaciones.

Actualizar: cierre el programa y descomprima el nuevo archivo donde está la carpeta `Ttranslator`, reemplazando los
archivos; los modelos, las voces, las traducciones, los glosarios y los ajustes se conservan. Desinstalar: cierre el
programa y elimine su carpeta (en Linux, también el acceso directo y los datos de la ventana, véase
[arriba](#updating-uninstalling-and-moving-to-another-computer)). Más información en [README.txt](README.txt).

Android (9 o posterior, procesador ARM de 64 bits; mejor con 8 GB de memoria o más): abra el archivo
`Ttranslator-<versión>-android-arm64.apk` en el teléfono o la tableta y permita la instalación desde este origen;
Google Play Protect puede avisar de un desarrollador desconocido: «Instalar de todos modos». Actualizar: el APK de la
nueva versión → «Actualizar» (los modelos y los datos se conservan; todas las versiones están firmadas con la misma
clave, huella en la sección [Android](#android)). Desinstalar: mantenga pulsado el icono → «Desinstalar»: los modelos,
las voces, lo guardado y los glosarios se borran con la aplicación (si Android no ofrece conservar los datos de la
aplicación).
</details>

<details>
<summary>中文</summary>

下载：[Windows](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-windows-x64.zip) · [Linux](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-linux-x64.tar.gz) ·
[Mac（Apple 芯片）](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-macos-arm64.zip) · [Mac（Intel）](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-macos-x64.zip)
· [Android（APK）](https://github.com/Allasoneteam/Ttranslator/releases/download/v1.2/Ttranslator-1.2-android-arm64.apk)
（所有版本：[Releases](https://github.com/Allasoneteam/Ttranslator/releases)）。

1. 把压缩包 `Ttranslator-<版本>-windows-x64.zip`（Windows）或 `…-linux-x64.tar.gz`（Linux）解压到您有写入权限的文件夹
   （不要放进 Program Files）：得到可随意移动的 `Ttranslator` 文件夹，不会向系统安装任何东西。llama.cpp 引擎已包含在内。
2. 运行 `Ttranslator.exe`（Windows）或 `./ttranslator-linux`（Linux）。首次启动时界面为英语：在欢迎窗口的
   “Interface language” 列表中选择 “中文”。
3. 点击“下载”：程序会显示要下载什么、从哪里下载、保存到哪个文件夹（一个 Gemma 4 模型，3.35 GB），之后无需联网即可使用。
   也可以点击“跳过”，之后再在模型菜单中选择模型。

Mac：`Ttranslator-<版本>-macos-arm64.zip`（Apple 芯片）或 `…-macos-x64.zip`（Intel），需要 macOS 13.3 或更高版本；
把 `Ttranslator.app` 拖到“应用程序”；首次启动时 macOS 会请求许可：macOS 15 及更高版本为“系统设置 → 隐私与安全性 → 仍要打开”，
macOS 13–14 为按住 Control 点击 →“打开”。数据位于 `~/Library/Application Support/Ttranslator`（“设置”→“打开数据文件夹”）。

Windows 可能会显示“Windows 已保护你的电脑”（程序没有签名）：点击“更多信息”→“仍要运行”。Linux：窗口和声音所需的软件包见上方
[Linux](#linux) 一节中的表格；`./ttranslator-linux --shortcut` 会把程序添加到应用程序菜单。

更新：关闭程序，把新的压缩包解压到 `Ttranslator` 文件夹所在的位置并替换文件——模型、语音、翻译、术语表和设置都会保留。卸载：关闭程序并删除
程序文件夹（在 Linux 上还要删除快捷方式和窗口数据，见[上文](#updating-uninstalling-and-moving-to-another-computer)）。详见 [README.txt](README.txt)。

Android（Android 9 或更高版本，64 位 ARM 处理器；内存最好在 8 GB 以上）：在手机或平板上打开文件
`Ttranslator-<版本>-android-arm64.apk`，并允许从此来源安装；Google Play 保护机制可能会提示开发者未知——选择“仍然安装”。
更新：打开新版本的 APK →“更新”（模型和数据会保留；所有版本使用同一个密钥签名，指纹见 [Android](#android) 一节）。
卸载：长按图标 →“卸载”——模型、语音、已保存内容和术语表会随应用一起删除（除非 Android 提示保留应用数据）。
</details>
