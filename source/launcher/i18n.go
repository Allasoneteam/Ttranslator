package main

// Messages the launcher shows in the window (errors, download states, model notes) in the interface language
// chosen in the settings: Russian (the text in the code), English or German. The key is the Russian text.

import "sync/atomic"

var uiLang atomic.Value // "ru", "en" or "de"

func setUILang(l string) { uiLang.Store(l) }

func curLang() string {
	if v, ok := uiLang.Load().(string); ok && v != "" {
		return v
	}
	return "ru"
}

// tr returns the message in the interface language; a message without a translation stays Russian.
func tr(s string) string {
	var m map[string]string
	switch curLang() {
	case "en":
		m = msgEN
	case "de":
		m = msgDE
	default:
		return s
	}
	if v, ok := m[s]; ok {
		return v
	}
	return s
}

var msgEN = map[string]string{
	// model catalogue
	"Gemma 4 — универсальная: перевод, правка, вопросы (Google, Apache 2.0)":            "Gemma 4 — general purpose: translation, editing, questions (Google, Apache 2.0)",
	"Свои файлы из папки models":                                                        "Your own files from the models folder",
	"Тестовые модели":                                                                   "Test models",
	"основная: быстрая, переводит, правит текст и отвечает на вопросы":                  "main model: fast, translates, edits text and answers questions",
	"качественнее E2B, медленнее примерно в 2 раза":                                     "better quality than E2B, about 2 times slower",
	"точнее Q4_0, медленнее примерно в 1,5 раза; нужно от 8 ГБ памяти":                  "more accurate than Q4_0, about 1.5 times slower; needs 8 GB of memory or more",
	"лучшее качество Gemma E4B, медленнее E2B примерно в 3 раза; нужно от 12 ГБ памяти": "best quality of Gemma E4B, about 3 times slower than E2B; needs 12 GB of memory or more",
	"свой файл":              "your own file",
	"выпуск":                 "release",
	"Windows x64, процессор": "Windows x64, CPU",
	"Linux x64, процессор":   "Linux x64, CPU",
	"Сохранённые":            "Saved",
	// engine
	"платформа %s/%s пока не поддерживается": "the %s/%s platform is not supported yet",
	"Не удалось открыть локальный порт: ":    "Could not open a local port: ",
	"Не удалось выбрать порт для движка: ":   "Could not choose a port for the engine: ",
	"Не удалось создать журнал движка: ":     "Could not create the engine log: ",
	"Не удалось запустить движок: ":          "Could not start the engine: ",
	"Движок не ответил за 4 минуты.":         "The engine did not respond within 4 minutes.",
	"Движок не отвечает: ":                   "The engine does not respond: ",
	"Модель ещё загружается, подождите.":     "The model is still loading, please wait.",
	"Движку не хватает системной библиотеки Windows (обычно это Microsoft Visual C++ Redistributable). Установите её с сайта Microsoft (https://aka.ms/vs/17/release/vc_redist.x64.exe) и нажмите «Повторить».": "The engine is missing a Windows system library (usually the Microsoft Visual C++ Redistributable). Install it from the Microsoft website (https://aka.ms/vs/17/release/vc_redist.x64.exe) and press “Retry”.",
	"Процессор не поддерживает инструкции, нужные этой сборке движка.":                                                                                                                                          "The processor does not support the instructions this engine build needs.",
	"Движок аварийно завершился (ошибка доступа к памяти). Подробности — в журнале ниже.":                                                                                                                       "The engine crashed (memory access error). Details are in the log below.",
	"Движок неожиданно завершился (код %d). Подробности — в журнале ниже.":                                                                                                                                      "The engine stopped unexpectedly (code %d). Details are in the log below.",
	"Движок не нашёл нужные системные библиотеки. Подробности — в журнале ниже. Можно собрать llama.cpp самостоятельно и указать путь к llama-server в config.json (engine_path).":                              "The engine did not find the system libraries it needs. Details are in the log below. You can build llama.cpp yourself and set the path to llama-server in config.json (engine_path).",
	"Движок неожиданно завершился (код %d). Подробности — в журнале ниже. Если в журнале упоминается GLIBC, соберите llama.cpp самостоятельно и укажите путь к llama-server в config.json (engine_path).":       "The engine stopped unexpectedly (code %d). Details are in the log below. If the log mentions GLIBC, build llama.cpp yourself and set the path to llama-server in config.json (engine_path).",
	" (сборка %d)": " (build %d)",
	// downloads
	"скачивание отменено":          "download cancelled",
	"движок: %w":                   "engine: %w",
	"распаковка движка: %w":        "unpacking the engine: %w",
	"в архиве движка нет файла %s": "the engine archive has no file %s",
	"модель: %w":                   "model: %w",
	"нет соединения с %s (%v)":     "no connection to %s (%v)",
	"сервер не принял докачку, нажмите «Повторить»": "the server did not accept resuming, press “Retry”",
	"сервер %s ответил %s":                          "the server %s answered %s",
	"скачивание остановилось: больше минуты не приходили данные; нажмите «Повторить», докачка продолжится": "the download stopped: no data for more than a minute; press “Retry”, it will resume",
	"ошибка при скачивании (%v); нажмите «Повторить», докачка продолжится":                                 "download error (%v); press “Retry”, it will resume",
	"размер файла не совпал (%d вместо %d байт); нажмите «Повторить»":                                      "the file size does not match (%d instead of %d bytes); press “Retry”",
	"контрольная сумма не совпала — файл повреждён и удалён; нажмите «Повторить»":                          "the checksum does not match — the file is damaged and was deleted; press “Retry”",
	"недопустимый путь в архиве: %s": "invalid path in the archive: %s",
	// requests from the window
	"неизвестная модель":                                  "unknown model",
	"идёт скачивание, дождитесь окончания":                "a download is in progress, please wait until it ends",
	"эта модель сейчас работает; сначала выберите другую": "this model is running now; choose another one first",
	"не удалось удалить файл: ":                           "could not delete the file: ",
	"неверный запрос":                                     "invalid request",
	"не удалось прочитать запрос":                         "could not read the request",
	"неверное значение настройки":                         "invalid setting value",
	// glossaries and saved translations
	"недопустимое имя файла словаря":                            "invalid glossary file name",
	"нет такого словаря":                                        "no such glossary",
	"словарь больше 2 МБ":                                       "the glossary is larger than 2 MB",
	"словарь с таким именем уже есть":                           "a glossary with this name already exists",
	"не удалось записать файл: ":                                "could not write the file: ",
	"недопустимое имя файла":                                    "invalid file name",
	"файл больше 16 МБ — это не похоже на сохранённые переводы": "the file is larger than 16 MB — it does not look like saved translations",
	"не удалось записать файл (возможно, он открыт в другой программе, например в Excel): ": "could not write the file (it may be open in another program, for example Excel): ",
	"файл с таким именем уже есть":                                   "a file with this name already exists",
	"запись не найдена — возможно, файл изменили в другой программе": "entry not found — the file may have been changed in another program",
	// reading aloud
	"идёт скачивание голоса, дождитесь окончания": "a voice is being downloaded, please wait until it finishes",
	"программа озвучки: %w":                       "speech program: %w",
	"распаковка программы озвучки: %w":            "unpacking the speech program: %w",
	"в архиве нет файла %s":                       "the archive has no file %s",
	"голос: %w":                                   "voice: %w",
	"голос (%s): %w":                              "voice (%s): %w",
	"распаковка голоса: %w":                       "unpacking the voice: %w",
	"чтение вслух не ответило за минуту":          "reading aloud did not respond within a minute",
	"не удалось прочитать текст вслух: %s":        "could not read the text aloud: %s",
	"неизвестный голос":                           "unknown voice",
	"этот голос сейчас скачивается":               "this voice is being downloaded right now",
	"нет текста для чтения":                       "no text to read",
	"слишком длинный текст для чтения вслух":      "the text is too long to read aloud",
	"для этого языка нет скачанного голоса":       "no voice has been downloaded for this language",
	// the own window (window.go)
	"нет программы окна %s в папке программы":                                                          "the window program %s is not in the program folder",
	"нет веб-движка системы: в Windows нужен Microsoft Edge WebView2 Runtime, в Linux — WebKitGTK 4.1": "the web engine of the system is missing: Windows needs the Microsoft Edge WebView2 Runtime, Linux needs WebKitGTK 4.1",
	"не хватает системных библиотек (нужен WebKitGTK 4.1)":                                             "system libraries are missing (WebKitGTK 4.1 is needed)",
	"программа окна завершилась с кодом %d":                                                            "the window program exited with code %d",
}

var msgDE = map[string]string{
	// Modellkatalog
	"Gemma 4 — универсальная: перевод, правка, вопросы (Google, Apache 2.0)":            "Gemma 4 – universell: Übersetzung, Korrektur, Fragen (Google, Apache 2.0)",
	"Свои файлы из папки models":                                                        "Eigene Dateien aus dem Ordner models",
	"Тестовые модели":                                                                   "Testmodelle",
	"основная: быстрая, переводит, правит текст и отвечает на вопросы":                  "Hauptmodell: schnell, übersetzt, korrigiert Text und beantwortet Fragen",
	"качественнее E2B, медленнее примерно в 2 раза":                                     "bessere Qualität als E2B, etwa 2-mal langsamer",
	"точнее Q4_0, медленнее примерно в 1,5 раза; нужно от 8 ГБ памяти":                  "genauer als Q4_0, etwa 1,5-mal langsamer; braucht mindestens 8 GB Arbeitsspeicher",
	"лучшее качество Gemma E4B, медленнее E2B примерно в 3 раза; нужно от 12 ГБ памяти": "beste Qualität von Gemma E4B, etwa 3-mal langsamer als E2B; braucht mindestens 12 GB Arbeitsspeicher",
	"свой файл":              "eigene Datei",
	"выпуск":                 "Version",
	"Windows x64, процессор": "Windows x64, Prozessor",
	"Linux x64, процессор":   "Linux x64, Prozessor",
	"Сохранённые":            "Gespeichert",
	// Engine
	"платформа %s/%s пока не поддерживается": "die Plattform %s/%s wird noch nicht unterstützt",
	"Не удалось открыть локальный порт: ":    "Lokaler Port konnte nicht geöffnet werden: ",
	"Не удалось выбрать порт для движка: ":   "Kein Port für die Engine gefunden: ",
	"Не удалось создать журнал движка: ":     "Das Engine-Protokoll konnte nicht angelegt werden: ",
	"Не удалось запустить движок: ":          "Die Engine konnte nicht gestartet werden: ",
	"Движок не ответил за 4 минуты.":         "Die Engine hat innerhalb von 4 Minuten nicht geantwortet.",
	"Движок не отвечает: ":                   "Die Engine antwortet nicht: ",
	"Модель ещё загружается, подождите.":     "Das Modell wird noch geladen, bitte warten.",
	"Движку не хватает системной библиотеки Windows (обычно это Microsoft Visual C++ Redistributable). Установите её с сайта Microsoft (https://aka.ms/vs/17/release/vc_redist.x64.exe) и нажмите «Повторить».": "Der Engine fehlt eine Windows-Systembibliothek (meist Microsoft Visual C++ Redistributable). Installieren Sie sie von der Microsoft-Website (https://aka.ms/vs/17/release/vc_redist.x64.exe) und klicken Sie auf „Wiederholen“.",
	"Процессор не поддерживает инструкции, нужные этой сборке движка.":                                                                                                                                          "Der Prozessor unterstützt die Befehle nicht, die diese Engine-Version braucht.",
	"Движок аварийно завершился (ошибка доступа к памяти). Подробности — в журнале ниже.":                                                                                                                       "Die Engine ist abgestürzt (Speicherzugriffsfehler). Einzelheiten stehen im Protokoll unten.",
	"Движок неожиданно завершился (код %d). Подробности — в журнале ниже.":                                                                                                                                      "Die Engine wurde unerwartet beendet (Code %d). Einzelheiten stehen im Protokoll unten.",
	"Движок не нашёл нужные системные библиотеки. Подробности — в журнале ниже. Можно собрать llama.cpp самостоятельно и указать путь к llama-server в config.json (engine_path).":                              "Die Engine hat benötigte Systembibliotheken nicht gefunden. Einzelheiten stehen im Protokoll unten. Sie können llama.cpp selbst bauen und den Pfad zu llama-server in config.json (engine_path) angeben.",
	"Движок неожиданно завершился (код %d). Подробности — в журнале ниже. Если в журнале упоминается GLIBC, соберите llama.cpp самостоятельно и укажите путь к llama-server в config.json (engine_path).":       "Die Engine wurde unerwartet beendet (Code %d). Einzelheiten stehen im Protokoll unten. Wenn dort GLIBC erwähnt wird, bauen Sie llama.cpp selbst und geben Sie den Pfad zu llama-server in config.json (engine_path) an.",
	" (сборка %d)": " (Build %d)",
	// Downloads
	"скачивание отменено":          "Download abgebrochen",
	"движок: %w":                   "Engine: %w",
	"распаковка движка: %w":        "Entpacken der Engine: %w",
	"в архиве движка нет файла %s": "im Engine-Archiv fehlt die Datei %s",
	"модель: %w":                   "Modell: %w",
	"нет соединения с %s (%v)":     "keine Verbindung zu %s (%v)",
	"сервер не принял докачку, нажмите «Повторить»": "der Server unterstützt das Fortsetzen nicht, klicken Sie auf „Wiederholen“",
	"сервер %s ответил %s":                          "der Server %s antwortete %s",
	"скачивание остановилось: больше минуты не приходили данные; нажмите «Повторить», докачка продолжится": "der Download stockt: seit über einer Minute kommen keine Daten; klicken Sie auf „Wiederholen“, er wird fortgesetzt",
	"ошибка при скачивании (%v); нажмите «Повторить», докачка продолжится":                                 "Fehler beim Herunterladen (%v); klicken Sie auf „Wiederholen“, der Download wird fortgesetzt",
	"размер файла не совпал (%d вместо %d байт); нажмите «Повторить»":                                      "die Dateigröße stimmt nicht (%d statt %d Byte); klicken Sie auf „Wiederholen“",
	"контрольная сумма не совпала — файл повреждён и удалён; нажмите «Повторить»":                          "die Prüfsumme stimmt nicht – die Datei ist beschädigt und wurde gelöscht; klicken Sie auf „Wiederholen“",
	"недопустимый путь в архиве: %s": "unzulässiger Pfad im Archiv: %s",
	// Anfragen aus dem Fenster
	"неизвестная модель":                                  "unbekanntes Modell",
	"идёт скачивание, дождитесь окончания":                "ein Download läuft, bitte warten Sie, bis er fertig ist",
	"эта модель сейчас работает; сначала выберите другую": "dieses Modell läuft gerade; wählen Sie zuerst ein anderes",
	"не удалось удалить файл: ":                           "die Datei konnte nicht gelöscht werden: ",
	"неверный запрос":                                     "ungültige Anfrage",
	"не удалось прочитать запрос":                         "die Anfrage konnte nicht gelesen werden",
	"неверное значение настройки":                         "ungültiger Wert der Einstellung",
	// Glossare und gespeicherte Übersetzungen
	"недопустимое имя файла словаря":                            "ungültiger Name der Glossardatei",
	"нет такого словаря":                                        "kein solches Glossar",
	"словарь больше 2 МБ":                                       "das Glossar ist größer als 2 MB",
	"словарь с таким именем уже есть":                           "ein Glossar mit diesem Namen gibt es schon",
	"не удалось записать файл: ":                                "die Datei konnte nicht geschrieben werden: ",
	"недопустимое имя файла":                                    "ungültiger Dateiname",
	"файл больше 16 МБ — это не похоже на сохранённые переводы": "die Datei ist größer als 16 MB – das sieht nicht nach gespeicherten Übersetzungen aus",
	"не удалось записать файл (возможно, он открыт в другой программе, например в Excel): ": "die Datei konnte nicht geschrieben werden (vielleicht ist sie in einem anderen Programm geöffnet, z. B. in Excel): ",
	"файл с таким именем уже есть":                                   "eine Datei mit diesem Namen gibt es schon",
	"запись не найдена — возможно, файл изменили в другой программе": "Eintrag nicht gefunden – die Datei wurde vielleicht in einem anderen Programm geändert",
	// Vorlesen
	"идёт скачивание голоса, дождитесь окончания": "eine Stimme wird heruntergeladen, bitte warten Sie, bis der Download fertig ist",
	"программа озвучки: %w":                       "Sprachausgabe-Programm: %w",
	"распаковка программы озвучки: %w":            "Entpacken des Sprachausgabe-Programms: %w",
	"в архиве нет файла %s":                       "im Archiv fehlt die Datei %s",
	"голос: %w":                                   "Stimme: %w",
	"голос (%s): %w":                              "Stimme (%s): %w",
	"распаковка голоса: %w":                       "Entpacken der Stimme: %w",
	"чтение вслух не ответило за минуту":          "das Vorlesen hat innerhalb einer Minute nicht geantwortet",
	"не удалось прочитать текст вслух: %s":        "der Text konnte nicht vorgelesen werden: %s",
	"неизвестный голос":                           "unbekannte Stimme",
	"этот голос сейчас скачивается":               "diese Stimme wird gerade heruntergeladen",
	"нет текста для чтения":                       "kein Text zum Vorlesen",
	"слишком длинный текст для чтения вслух":      "der Text ist zu lang zum Vorlesen",
	"для этого языка нет скачанного голоса":       "für diese Sprache ist keine Stimme heruntergeladen",
	// the own window (window.go)
	"нет программы окна %s в папке программы":                                                          "das Fensterprogramm %s fehlt im Programmordner",
	"нет веб-движка системы: в Windows нужен Microsoft Edge WebView2 Runtime, в Linux — WebKitGTK 4.1": "die Web-Engine des Systems fehlt: Windows braucht die Microsoft Edge WebView2 Runtime, Linux braucht WebKitGTK 4.1",
	"не хватает системных библиотек (нужен WebKitGTK 4.1)":                                             "Systembibliotheken fehlen (WebKitGTK 4.1 wird benötigt)",
	"программа окна завершилась с кодом %d":                                                            "das Fensterprogramm wurde mit Code %d beendet",
}
