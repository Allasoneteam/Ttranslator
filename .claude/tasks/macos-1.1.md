# Задание: Ttranslator 1.1 для macOS (облачная сессия)

Выдано координатором (чат проекта автора) 01.11.2026. Правила — `CLAUDE.md` в корне и `source/CLAUDE.md`; план — `source/docs/ROADMAP.md` («Первостепенное», пункт 0; «Этап 5», шаги 3–4). Спешки нет: важнее, чтобы работало и было проверено.

## Цель
Ttranslator для macOS — Intel (x86_64) и Apple Silicon (arm64) — собирается и проверяется в GitHub Actions, а тестовые архивы лежат в артефактах запуска, чтобы автор проверил их на своём Mac. Выпуск не делать.

## Решения автора (не менять)
- Архивы — zip, как для Windows: `Ttranslator-<версия>-macos-x64.zip` и `Ttranslator-<версия>-macos-arm64.zip`, внутри — `Ttranslator.app` (README.txt и LICENSE.txt — рядом с ним).
- Движок llama.cpp — внутри (как в архивах Windows и Linux); программа озвучки sherpa-onnx и голоса — не в архиве: скачиваются при первом голосе (`osx-universal2` уже есть в `currentTTSPackage`).
- Данные и модели — в `~/Library/Application Support/Ttranslator` (решение от 22.10.2026: неподписанную программу macOS часто запускает из временной папки только для чтения); в «Настройках» и меню — «Открыть папку данных»; сохранение и загрузка файлов — через окна macOS «Сохранить» и «Открыть».
- Подписи Apple Developer нет (99 $ в год — не сейчас): только подпись ad-hoc и инструкция для первого запуска.
- Go — только стандартная библиотека; окно — `source/window` (библиотека webview: Cocoa и WKWebView).
- Проверяет автор на MacBook Pro 2019 (Intel). Mac на Apple Silicon у автора пока нет: arm64 проверяется только в CI.

## Минимальная версия macOS — вопрос автору открыт
На MacBook Pro 2019 автора сейчас macOS 10.15 Catalina. Координатор проверил 01.11.2026 (`python3 -I .claude/tools/macho_minos.py <папка>` — минимальная версия из заголовков Mach-O):
- официальные сборки llama.cpp b11435 для macOS (x64 и arm64) — `minos 13.3` во всех файлах;
- sherpa-onnx v1.13.7 `osx-universal2-shared`: программы — `minos 10.14` (x86_64) и `11.0` (arm64), но `lib/libonnxruntime.dylib` — `minos 15.5` в обоих срезах;
- Go 1.23 и новее требует macOS 11 (Go 1.22 — последний для 10.15, без исправлений с февраля 2025).

Автору предложено: 1.1 — для macOS 13.3 и новее, MacBook Pro 2019 обновить до macOS 15 Sequoia (она для него есть). Пока решения нет: минимальная версия — 13.3 (`-mmacosx-version-min=13.3`, `LSMinimumSystemVersion` 13.3), ничего особого для 10.15 не делать. Решение координатор допишет сюда.

Выясни и опиши в отчёте: на каких версиях macOS заработает чтение вслух с этой `libonnxruntime.dylib` (`minos 15.5`). Машины GitHub — `macos-15`, `macos-15-intel`, `macos-26`; более старых, скорее всего, уже нет. Если голоса будут только на 15.5 и новее — предложи варианты (например, другой выпуск sherpa-onnx для macOS, чья onnxruntime собрана под 13.3 или ниже, с проверкой `voice_check.py`), но сам не меняй.

## Что сделать (по порядку; после каждого шага — отправка в свою ветку)
1. **Программа запуска для macOS** (`source/launcher`).
   - `sys_darwin.go`: сейчас `GOOS=darwin go build` (с `ui_fallback`, как в `source/build.sh`) не находит 16 функций: `fatal`, `makeShortcut`, `machineInfo`, `platformInit`, `engineEnv`, `setChildAttrs`, `attachChild`, `terminate`, `exitMessage`, `openFolder`, `windowHelperName`, `openWindow`, `windowArgs`, `windowEnv`, `windowChildAttrs`, `allowForeground`. Образец — `sys_linux.go`; окно ошибки — `osascript`, «открыть папку» — `open`.
   - Папка данных `~/Library/Application Support/Ttranslator` (`config.json`, `data`, `models`, `engine`); всё внутри `Ttranslator.app` — только для чтения; `ui/` — из `Contents/Resources`.
   - `enginePackageFor("darwin", …)`: официальные `llama-b11435-bin-macos-x64.tar.gz` и `llama-b11435-bin-macos-arm64.tar.gz` (размер и SHA-256 — по файлам выпуска). На Apple Silicon — Metal (он есть в этой сборке), на Intel — процессор.
   - Кнопка «Открыть папку данных» в «Настройках» и меню — текст через `t('…')` на пяти языках; в Windows и Linux — не показывать (или открывать папку программы — реши и опиши).
   - Сборка `CGO_ENABLED=0 GOOS=darwin GOARCH=amd64` и `arm64` должна проходить и в Linux: добавь в `source/build.sh` (или проверкой `go vet` в `run_all.sh`). Новая логика (пути, выбор движка) — с модульными тестами.
2. **Окно приложения для macOS** (`source/window`): часть Cocoa — WKWebView; `ttwSaveFile` — окно «Сохранить» (NSSavePanel); `ttwOpenExternal` — NSWorkspace; запрет переходов на чужие страницы; `ttwClose`; на весь экран при запуске (`start_maximized`); выход на передний план. Сборка — `clang++`, `-mmacosx-version-min=13.3`. Подсказки — `source/window/README.md`, раздел «macOS — потом».
3. **Ttranslator.app и архивы**: `Info.plist` (имя, версия из `appVersion`, `LSMinimumSystemVersion`, значок), значок `.icns` из того же рисунка (`make_icon.go` умеет PNG — допиши ICNS или собери `iconutil`), движок — внутри приложения (символьные ссылки `dylib` сохранить), подпись ad-hoc всего приложения (`codesign --force --deep --sign -`), zip, `SHA256SUMS`. Где собирать — в `source/release.sh` или в отдельном скрипте для macOS, реши сам.
4. **CI**: `source/ci/macos.sh <arch> <out-dir>` — его уже запускает шаг `macos` в `ci.yml` (`macos-15-intel` — x64, `macos-15` — arm64); всё, что положишь в `<out-dir>`, станет артефактом; строка `MACZIP=<имя архива>` в `$GITHUB_ENV` выгрузит архив отдельным артефактом, без второй упаковки. Скрипт:
   - собирает программы, приложение и архив;
   - проверяет без настоящей модели: приложение запускается с маленькой тестовой моделью (`source/tests/make_tiny_gguf.py`), `/api/state` отвечает, перевод проходит через движок (ответ — бессмыслица, важна цепочка), голос читает фразу в WAV (sherpa-onnx и один голос — с GitHub), окно приложения открывается (снимок `screencapture` — в результаты);
   - проверяет защиту macOS: `codesign --verify --deep --strict`; приложение с признаком карантина (`xattr -w com.apple.quarantine …` на архиве, распаковка как у пользователя) после разрешения запуска не спотыкается о движок и программу окна — или программа снимает признак со своих файлов сама; окончательно это проверит автор;
   - по возможности — часть наборов `source/tests` на Mac (playwright и Chromium) — не обязательно.
5. **Тексты** (когда CI зелёный): `README.txt` (UTF-8 с BOM, CRLF) — установка и первый запуск на Mac на пяти языках, там же — подробно по-русски: macOS 13–14 — щелчок с Control → «Открыть»; macOS 15 и новее — «Системные настройки → Конфиденциальность и безопасность → Всё равно открыть»; обновление и удаление на Mac; где лежат данные. `README.md` (по-английски) и справка в `index.html` (`HELP`, пять языков) — то же коротко.

## Чего не делать
- Не трогать `main`, `dev`, метки, выпуски, настройки репозитория.
- Не менять поведение программы в Windows и Linux: все наборы `run_all.sh` проходят, как сейчас.
- Без новых сторонних компонентов. Можно: системные инструменты macOS и Xcode на машинах GitHub (`clang++`, `codesign`, `ditto`, `iconutil`, `sips`, `screencapture`, `osascript`), модули Python, которые уже нужны тестам.
- Не поднимать версию (`appVersion`, `WHATS_NEW`) и не писать CHANGELOG и ROADMAP — это сделает координатор перед выпуском.
- `ui/index.html` в это же время больше никто не правит — правь его только ты.

## Готово, когда
- В твоей ветке оба шага `macos` и все прежние шаги CI зелёные; в артефактах — оба архива и снимки окна.
- `bash source/tests/run_all.sh <рабочая-папка>` — `ALL SUITES PASSED`.
- Отчёт для автора (по-русски) — в описании черновика PR в `dev`, а если PR создать нельзя — в `.claude/tasks/macos-1.1-report.md` в своей ветке: что сделано; ссылки на запуски CI; что проверить на Mac — по шагам (скачать архив из артефактов, первый запуск, модель, перевод, «Быстрый тест», голос, «Сохранить», «Открыть папку данных»); что осталось и какие решения нужны от автора.
- Если работа упирается в решение автора — спроси в чате сессии (автор его видит) и продолжай с тем, что от решения не зависит.
