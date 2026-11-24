# Ttranslator для Android

Приложение для телефонов и планшетов с Android 9 и новее (64-битный ARM) — с версии 1.2. Та же программа, что на
компьютере: программа запуска на Go, движок llama.cpp, программа чтения вслух sherpa-onnx и интерфейс `ui/index.html`
— внутри APK; окно — WebView. Как устроено — `source/docs/ARCHITECTURE.md`, раздел «Android»; как собирать и
проверять — здесь и в `source/docs/DEVELOPMENT.md`. История — отчёт проверки осуществимости
([FEASIBILITY.md](FEASIBILITY.md), ноябрь 2026).

## Что внутри APK

| Файл в APK | Что это |
|---|---|
| `lib/arm64-v8a/libttranslator.so` | программа запуска (`source/launcher` без правок, `GOOS=android`, cgo — ради DNS Android) |
| `lib/…/libllama-server.so` и библиотеки | llama-server llama.cpp b11435 — официальная сборка для Android (arm64) |
| `lib/…/libsherpa-onnx-offline-tts.so`, `libsherpa-onnx-c-api.so`, `libonnxruntime.so` | чтение вслух: `native/tts-cli.c` над C API официальных библиотек sherpa-onnx v1.13.7 для Android |
| `classes.dex` | оболочка на Java: `MainActivity` (окно), `Launcher` (запуск программы запуска), `WorkService` (уведомление), `Texts` (тексты на пяти языках) |
| `assets/tests.txt`, `LICENSE.txt`, `THIRD-PARTY.txt` | пары «Подробного теста», лицензии (полные тексты — из `licenses/`); приложение кладёт их в папку `ui` программы. Сам интерфейс `ui/index.html` — внутри программы запуска (`ui_fallback`) |

Программы лежат в папке библиотек приложения (`lib….so`, `extractNativeLibs`): только оттуда Android 10 и новее
разрешает приложению запускать программы. Все скачиваемые при сборке файлы закреплены: версия, размер, SHA-256
(в начале `build.sh`).

## Как работает (коротко)

- `Launcher.java` при каждом запуске готовит папку программы и запускает `libttranslator.so --no-window` с
  переменными: `TDOC_ROOT` (папка программы: Android 11+ — `Android/data/io.github.allasoneteam.ttranslator/files`,
  Android 9–10 — внутренняя `files/Ttranslator`: там `Android/data` могли бы читать другие приложения с разрешением
  на память), `TDOC_ACCESS_KEY` (случайный ключ), `TDOC_PORT_FILE` (сюда программа запуска пишет свой порт),
  `TDOC_OS`, `TDOC_CPU` (устройство — для отчётов теста). Новой установке — язык телефона, если он из пяти языков
  интерфейса, иначе английский.
- Ключ доступа: программа запуска отвечает только на запросы с ключом — окно получает его в куки `tdoc_key`
  (HttpOnly), сама оболочка — в заголовке `X-Tdoc-Key`; другие приложения телефона получают 403
  (`source/launcher/android.go`).
- `MainActivity.java`: WebView со страницей программы запуска; функции окна для страницы (`ttwSaveFile` — окно
  «Сохранить» Android, `ttwOpenExternal`, `ttwClose`, `ttwPlatform = 'android'`); выбор файла для импорта; «Назад»
  (`OnBackInvokedCallback` на Android 13+, `onBackPressed` — раньше) → `ttwBack()` страницы, а если закрывать нечего —
  приложение уходит в фон; текст из других приложений (`PROCESS_TEXT` — «Ttranslator» в меню выделенного текста,
  `SEND` — «Поделиться») → `ttwSetText()`; после долгого перерыва — перезапуск программы запуска, если она не отвечает.
- `WorkService.java`: пока скачивается модель или голос или работает движок (`/api/state`: `download`,
  `tts.download`, `engine_busy`), приложение — служба переднего плана (`dataSync`, на Android 14+ ещё `specialUse`)
  с уведомлением; через 8 с после работы служба заканчивается. Android 13+ один раз спрашивает разрешение на
  уведомления (работа идёт и без него).
- Микрофон (1.4, диктовка 🎤): `RECORD_AUDIO` и `MODIFY_AUDIO_SETTINGS` в манифесте; страница записывает звук сама
  (`getUserMedia`), `onPermissionRequest` даёт странице программы запуска только звук, а при первом запросе Android
  спрашивает разрешение (`onRequestPermissionsResult`). Отказ — страница подсказывает, где его дать (Приложения →
  Ttranslator → Разрешения).
- Каталог моделей на телефоне (`phoneCatalog`): E2B · Q4_0 — всегда, E4B · Q4_0 — от 12 ГБ (MemTotal ≥ 10 ГиБ),
  Q8_0 — нет. Меньше 5 ГБ памяти — предупреждение в окне приветствия и в меню моделей.

## Сборка

```
ANDROID_HOME=<sdk> bash android/build.sh [папка]
```

Нужны Android SDK (с cmdline-tools), JDK 17+, Go 1.24+, git, curl, python3, cmake, ninja; NDK, платформу и
build-tools скрипт ставит сам (версии — в начале `build.sh`; NDK — тот же, что у официальной сборки llama.cpp для
Android). Результат:

- `Ttranslator-<версия>-android-test.apk` — тестовый: arm64 и x86_64 (для эмулятора), подписан открытым
  тестовым ключом `app/debug.keystore`, «отлаживаемый» (проверка в эмуляторе читает ключ доступа через `run-as`);
  версия — `<версия>-android-test`. Только для проверки: обновить его до выпуска нельзя (другая подпись).
- `Ttranslator-<версия>-android-arm64-unsigned.apk` — для телефонов: только arm64, не подписан; код версии —
  из `appVersion` (1.2 → 10200: major·10000 + minor·100 + patch).

## Проверка

`bash android/ci.sh <папка>` (так работает задача `android` в GitHub Actions; локально — Linux с `/dev/kvm`):
`build.sh`, затем `test/emulator_test.py` в эмуляторах — Android 16 с 8 ГБ памяти (как телефон автора; приложение
само скачивает настоящую Gemma 4 E2B · Q4_0 с Hugging Face, загружает и переводит) и Android 10 (основное). Что
проверяется: запуск программы запуска из папки библиотек, ключ (без него — 403), папки, движок и перевод (запросом и
в самой странице), чтение вслух (голос скачивается с GitHub прямо в эмуляторе), раскладка телефона, «Назад»,
уведомление во время перевода и после, текст из другого приложения, лицензии, работа в фоне, остановка приложения
Android'ом, «Выход». Снимки экрана и журналы — в результатах запуска (`android-results`). Страницу тест ведёт по
протоколу отладки WebView (свой маленький клиент: Playwright к WebView не подключается). Раскладку телефона
проверяет и `source/tests/e2e_v12_phone.py` (входит в `run_all.sh`, Chromium с экраном телефона).

## Подпись и выпуск

- Ключ подписи — свой ключ проекта (RSA 4096, PKCS12, псевдоним `ttranslator`), сделан 14.11.2026. Сам ключ и пароль
  — только у автора и в секретах окружения GitHub `android-signing` (`ANDROID_KEYSTORE_BASE64`,
  `ANDROID_KEYSTORE_PASSWORD`); в репозитории — только отпечаток сертификата `signing-cert-sha256.txt`. Файлы ключей
  в репозиторий не попадают (`.gitignore`: `*.p12`, `*.jks`, `*.pem`, `*.base64.txt`, `signing-key/`).
- Ключ менять нельзя: Android ставит обновление только с той же подписью, иначе пользователям пришлось бы удалить
  приложение вместе с моделями. Потеря ключа — то же самое; копии ключа автор хранит у себя.
- GitHub Actions: задача `android` выкладывает неподписанный APK (`android-unsigned`); задача `android-sign` (только
  `main` и `dev`, окружение `android-signing`) выравнивает его (zipalign), подписывает (apksigner, схемы v2 и v3) и
  сверяет сертификат с `signing-cert-sha256.txt`; результат — `Ttranslator-<версия>-android-arm64.apk`. При отправке в
  `main` задача `release` кладёт его в черновик выпуска вместе с архивами для компьютеров и `SHA256SUMS.txt`.

## Решения автора

- 13.11.2026: Android — отдельный выпуск после 1.1; обязательны свой ключ подписи, ключ доступа к программе запуска,
  раскладка для телефона. 14.11.2026: выпуск — 1.2 для всех систем; «да» на план.
- Чтение вслух — в APK (sherpa-onnx с espeak-ng, GPL-3.0: полные тексты лицензий и точные исходники — в
  `THIRD-PARTY.txt`).
- Модели на телефоне — по памяти (см. выше); язык первого запуска — язык телефона, если он из пяти.
- Уведомление на время скачивания и перевода — да; «Перевести» из любого приложения — да; открыть модель из файла
  (выбор `.gguf` на телефоне) — позже.
- Распространение — APK в выпусках GitHub. Google Play и регистрация разработчика (Google требует её и для APK не
  из Google Play: с 30.09.2026 — в Бразилии, Индонезии, Сингапуре и Таиланде, с 2027 года — везде) — отдельным
  решением позже.

## Папка `android/`

```
android/
  README.md              этот файл; FEASIBILITY.md — отчёт проверки осуществимости (история)
  build.sh               сборка обоих APK (версии, размеры, SHA-256 всего скачиваемого — в начале файла)
  ci.sh                  задача android в CI: build.sh, эмуляторы, проверка
  test/emulator_test.py  проверка в эмуляторе (adb, протокол отладки WebView)
  native/tts-cli.c       программа чтения вслух над C API sherpa-onnx (параметры — как у sherpa-onnx-offline-tts)
  THIRD-PARTY.txt        что внутри APK, где исходники; licenses/ — полные тексты лицензий
  signing-cert-sha256.txt  отпечаток сертификата подписи выпусков
  settings.gradle, build.gradle, gradle.properties, app/build.gradle   проект Gradle (только Android Gradle Plugin)
  app/debug.keystore     открытый тестовый ключ (только тестовый APK)
  app/src/main/          AndroidManifest.xml, java/…/{MainActivity,Launcher,WorkService,Texts}.java, res/
```
