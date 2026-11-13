# Окно приложения Ttranslator (ttranslator-window)

Маленькая программа, которая показывает интерфейс Ttranslator в обычном окне системы — без браузера. Внутри окна —
веб-движок самой системы: Microsoft Edge WebView2 в Windows, WebKitGTK 4.1 в Linux, WKWebView в macOS (1.1).
Программа запуска (Go, только стандартная библиотека) запускает её, если в «Настройках» выбран вид окна
«Окно приложения» (`launch_mode: "window"`, по умолчанию с 0.9.2), а если окно не открылось — открывает окно
Edge/Chrome и показывает причину в «Настройках». Подробно: `source/launcher/window.go`, `source/docs/ARCHITECTURE.md`.

## Файлы

| Файл | Что |
|---|---|
| `ttranslator-window.cc` | вся программа (C++14) |
| `ttranslator-window.rc`, `.manifest` | Windows: значок (тот же, что у Ttranslator.exe), сведения о версии (программа окна 1.1; правообладатели — Allasoneteam and Ttranslator authors), манифест |
| `build.sh` | сборка: `sh build.sh` (Linux и Windows), `sh build.sh linux`, `sh build.sh windows`, на Mac — `sh build.sh macos` (`ARCH=x86_64` или `arm64`); `OUT=папка` — куда класть |
| `webview/webview.h` | библиотека [webview](https://github.com/webview/webview) **0.12.0** (MIT, `webview/LICENSE`), с одной правкой — см. ниже |
| `webview2/WebView2.h` | заголовок Microsoft WebView2 SDK **1.0.1150.38** (лицензия — `webview2/LICENSE.txt`), из [webview_go](https://github.com/webview/webview_go) |
| `webview2/EventToken.h` | заменитель заголовка Windows SDK: в MinGW-w64 его нет (Ubuntu 22.04) или он называется `eventtoken.h`; тот же, что `compatibility/mingw/include/EventToken.h` библиотеки webview (MIT) |

Исходные файлы библиотек (для сверки): `webview.h` из выпуска 0.12.0 (коммит 3ab4b5d) — SHA-256
`b1ff6e11431d031e5f7917e5301f4bcdf3910a2763a0720abfd291994eee7f7b`; `WebView2.h` —
`557d5c751148732242b6ced2dbf99d35bed4c4cb471fa50ccf2069a342244cf4`.

## Правка в webview.h

В Windows библиотека хранит данные WebView2 (хранилище страницы, кэш) в `%APPDATA%\<имя программы>`. Ttranslator —
переносимая папка, поэтому в `embed()` добавлено чтение переменной окружения `TTRANSLATOR_WEBVIEW_DATA`: программа
окна ставит её из своего аргумента `--data` (программа запуска передаёт `data\webview`). Правка помечена комментарием
«Ttranslator patch». При обновлении библиотеки её нужно перенести.

## Сборка

Нужно (Ubuntu/Debian): `g++ pkg-config libgtk-3-dev libwebkit2gtk-4.1-dev g++-mingw-w64-x86-64`.

- Windows: кросс-сборка MinGW-w64, всё статически — программе нужны только системные DLL (проверка в
  `run_all.sh`). Собственный загрузчик WebView2 библиотеки webview: `WebView2Loader.dll` не нужен.
- Linux: библиотека C++ — общая (иначе нужна более новая glibc); собранная на Ubuntu 22.04 (так в CI) программа
  работает на Ubuntu 22.04, Debian 12 и новее. На компьютере нужен пакет `libwebkit2gtk-4.1-0` (обычно уже стоит).
- macOS: на Mac, `clang++` из Xcode или Command Line Tools, `-mmacosx-version-min=13.3` (столько же требуют официальные
  сборки llama.cpp), фреймворки Cocoa, WebKit, UniformTypeIdentifiers. Программа лежит в
  `Ttranslator.app/Contents/MacOS/ttranslator-window` (`source/release-macos.sh`).

## Как работает

`ttranslator-window URL [--title TEXT] [--size WxH] [--maximized] [--data DIR] [--icon FILE.png] [--lang CODE]`

- URL — только адрес программы запуска (`http://127.0.0.1:ПОРТ/…` или `http://localhost:ПОРТ/…`).
- `--maximized` — окно на весь экран (Windows: `ShowWindow(SW_MAXIMIZE)`, Linux: `gtk_window_maximize`, macOS: `zoom:` — окно во весь экран без отдельного полноэкранного режима); размер `--size` — тот, что после «Восстановить» (в macOS — после зелёной кнопки). Программа запуска передаёт его, если `start_maximized` (по умолчанию).
- `--lang` — только macOS: язык строки меню (en, ru, de, es, zh — язык интерфейса; названия — те, что у самой macOS).
- При запуске окно выходит на передний план (`bring_to_front`, с 0.9.3). Windows не даёт программе, которую запустила фоновая программа, вывести окно вперёд — без этого окно открывалось за окном папки, из которой запущен Ttranslator.exe. Программа запуска (её запустил Проводник) отдаёт своё право (`AllowSetForegroundWindow(pid)`), и окно вызывает `SetForegroundWindow`; если Windows всё же отказала, а впереди окно Проводника (`explorer.exe`: папка или рабочий стол), ввод двух потоков на мгновение объединяется (`AttachThreadInput`) — обычный обход. Поверх другой программы, в которую пользователь перешёл, пока окно открывалось, окно не встаёт. Linux: `gtk_window_present`. macOS: `makeKeyAndOrderFront`, `orderFrontRegardless` и `activateIgnoringOtherApps`. `_WIN32_WINNT` = Windows 10: старые заголовки MinGW (Ubuntu 22.04) иначе прячут `QueryFullProcessImageNameW`.
- Когда окно создано, программа пишет `ready` в stdout. Коды выхода: 0 — окно закрыли, 2 — неверные аргументы,
  3 — нет веб-движка системы (в Windows — нет WebView2 Runtime; в Linux — нет экрана или WebKitGTK).
- Окно показывает только страницы программы запуска: переходы на другие сайты и ссылки, открывающие новое окно,
  уходят в браузер по умолчанию (Windows: NavigationStarting и NewWindowRequested; Linux: decide-policy; macOS:
  WKNavigationDelegate — переход без целевой рамки, то есть в новое окно, тоже уходит наружу).
- Функции для страницы (возвращают Promise): `ttwOpenExternal(url)` — открыть адрес http, https или mailto снаружи;
  `ttwSaveFile(имя, текст, расширение, заголовок, название типа)` — окно «Сохранить как» системы (Windows:
  GetSaveFileNameW; Linux: GtkFileChooserNative; macOS: NSSavePanel, папка «Загрузки»), текст пишется в файл как есть (UTF-8); ответ `{path}` или
  `{cancelled: true}`; `ttwClose()` — закрыть окно. Признак для страницы — `window.TTW = { version: 1 }`.
- Linux: данные страницы (хранилище, кэш) WebKitGTK хранит в `~/.local/share/ttranslator` и `~/.cache/ttranslator`
  (имя программы для системы — `ttranslator`).
- Открыть файл (импорт словаря и сохранённых, `<input type="file">`): в macOS — окно «Открыть» (NSOpenPanel) из
  библиотеки webview, в Linux и Windows — окно веб-движка.

## Проверки

`source/tests/e2e_window.py` (программа запуска со своим окном: запуск, закрытие, «Выход», запасной путь) и
`source/tests/window_functions.py` (функции для страницы) — под виртуальным экраном (`xvfb-run`, `xdotool`).
Окно Windows проверяет автор на своём компьютере; в облачной среде — только сборка и запуск под Wine без WebView2
(код выхода 3).

## macOS (1.1)

Часть для Cocoa написана на C++ через Objective-C runtime (`objc_msgSend`), как сама библиотека webview: режим
Objective-C компилятору не нужен. Окно «Сохранить» — NSSavePanel; ссылки наружу — NSWorkspace; запрет переходов —
свой WKNavigationDelegate; на весь экран — `zoom:`. Ttranslator.app сам — «агент» (`LSUIElement`: у программы запуска
нет ни окна, ни значка в Dock), а программа окна делает себя обычным приложением: значок в Dock и строка меню. В
строке меню — «Ttranslator» (О программе, Скрыть, Завершить ⌘Q), «Правка» (Отменить, Повторить, Вырезать, Скопировать,
Вставить, Выбрать все) и «Окно» (Свернуть, Изменить масштаб, Закрыть ⌘W): без меню «Правка» в окне WKWebView не
работают ⌘C, ⌘V, ⌘X, ⌘A и ⌘Z. Данные страницы (хранилище) macOS держит сама, для Ttranslator.app (`--data` не нужен).
Проверки — в GitHub Actions на Mac (`source/ci/macos.sh`): окно открывается, показывает страницу, впереди и на весь
экран (снимок экрана).
