# Окно приложения Ttranslator (ttranslator-window)

Маленькая программа, которая показывает интерфейс Ttranslator в обычном окне системы — без браузера. Внутри окна —
веб-движок самой системы: Microsoft Edge WebView2 в Windows, WebKitGTK 4.1 в Linux (позже — WKWebView в macOS).
Программа запуска (Go, только стандартная библиотека) запускает её, если в «Настройках» выбран вид окна
«Окно приложения» (`launch_mode: "window"`, по умолчанию с 0.9.2), а если окно не открылось — открывает окно
Edge/Chrome и показывает причину в «Настройках». Подробно: `source/launcher/window.go`, `source/docs/ARCHITECTURE.md`.

## Файлы

| Файл | Что |
|---|---|
| `ttranslator-window.cc` | вся программа (C++14) |
| `ttranslator-window.rc`, `.manifest` | Windows: значок (тот же, что у Ttranslator.exe), сведения о версии, манифест |
| `build.sh` | сборка: `sh build.sh` (обе), `sh build.sh linux`, `sh build.sh windows`; `OUT=папка` — куда класть |
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

## Как работает

`ttranslator-window URL [--title TEXT] [--size WxH] [--maximized] [--data DIR] [--icon FILE.png]`

- URL — только адрес программы запуска (`http://127.0.0.1:ПОРТ/…` или `http://localhost:ПОРТ/…`).
- `--maximized` — окно на весь экран (Windows: `ShowWindow(SW_MAXIMIZE)`, Linux: `gtk_window_maximize`); размер `--size` — тот, что после «Восстановить». Программа запуска передаёт его, если `start_maximized` (по умолчанию).
- Когда окно создано, программа пишет `ready` в stdout. Коды выхода: 0 — окно закрыли, 2 — неверные аргументы,
  3 — нет веб-движка системы (в Windows — нет WebView2 Runtime; в Linux — нет экрана или WebKitGTK).
- Окно показывает только страницы программы запуска: переходы на другие сайты и ссылки, открывающие новое окно,
  уходят в браузер по умолчанию (Windows: NavigationStarting и NewWindowRequested; Linux: decide-policy).
- Функции для страницы (возвращают Promise): `ttwOpenExternal(url)` — открыть адрес http, https или mailto снаружи;
  `ttwSaveFile(имя, текст, расширение, заголовок, название типа)` — окно «Сохранить как» системы (Windows:
  GetSaveFileNameW; Linux: GtkFileChooserNative), текст пишется в файл как есть (UTF-8); ответ `{path}` или
  `{cancelled: true}`; `ttwClose()` — закрыть окно. Признак для страницы — `window.TTW = { version: 1 }`.
- Linux: данные страницы (хранилище, кэш) WebKitGTK хранит в `~/.local/share/ttranslator` и `~/.cache/ttranslator`
  (имя программы для системы — `ttranslator`).

## Проверки

`source/tests/e2e_window.py` (программа запуска со своим окном: запуск, закрытие, «Выход», запасной путь) и
`source/tests/window_functions.py` (функции для страницы) — под виртуальным экраном (`xvfb-run`, `xdotool`).
Окно Windows проверяет автор на своём компьютере; в облачной среде — только сборка и запуск под Wine без WebView2
(код выхода 3).

## macOS — потом

Нужно добавить часть для Cocoa: окно «Сохранить» (NSSavePanel), открытие ссылок (NSWorkspace), запрет переходов
(WKNavigationDelegate), и собрать на macOS (GitHub Actions): `clang++ -std=c++14 ttranslator-window.cc
-framework WebKit -framework Cocoa`.
