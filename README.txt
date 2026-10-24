TTRANSLATOR 1.0 — AN OFFLINE TRANSLATOR

Офлайн-переводчик · Offline-Übersetzer · Traductor sin conexión · 离线翻译器

Ttranslator is a free, open-source offline translator for nine languages:
English, Russian, German, French, Spanish, Greek, Chinese, Latin and Swedish.
It runs a local language model on your own computer — no cloud, no account, no
telemetry — and shows several translation variants in different styles, edits
text in the same language, follows your own glossary, answers questions about
a translation and reads texts aloud. A processor is enough (no graphics card
is needed), with 8 GB of memory and 4–9 GB of disk space for a model.

The interface is in English, Russian, German, Spanish and Chinese. This file
has the installation and the first start in these five languages and then the
full guide in Russian; the program itself has the full guide in every
interface language (the “?” button at the top right, Help).

    1. Installation and first start ............. English
    2. Установка и первый запуск ................ по-русски
    3. Installation und erster Start ............ Deutsch
    4. Instalación y primer inicio .............. español
    5. 安装与首次启动 ........................... 中文
    6. Подробная инструкция ..................... по-русски

==============================================================================
1. INSTALLATION AND FIRST START (ENGLISH)
==============================================================================

WINDOWS

1. Unpack the archive Ttranslator-<version>-windows-x64.zip into any folder
   you can write to — for example, onto the desktop or into Documents, but not
   into Program Files. You get the folder Ttranslator. Nothing is installed
   into the system; the folder can be moved as a whole.
2. Double-click Ttranslator.exe. The translator window opens (maximized), and
   in it the welcome window: the interface language (English on the first
   start; Russian, German, Spanish and Chinese are in the same list), the
   window type and whether to load the model at start. “Get started” closes
   it.
3. On the first start press “Download”: the program downloads the Gemma 4 E2B
   model once (3.35 GB, from huggingface.co); the llama.cpp engine is already
   in the archive. For every file you see where it comes from, the folder it
   goes to and its name. The files are checked by their checksums, and an
   interrupted download resumes where it stopped.
   Or press “Skip”: the window opens at once, without a model, and you choose
   and download one later in the model menu (the “Choose a model” button at
   the top).
4. After that the internet is needed only to download other models and voices.
   To exit, press “Exit” at the top right (a second click confirms) or simply
   close the window: within a few seconds the model is unloaded from memory
   and the program exits.

If Windows shows “Windows protected your PC”: the program is not signed with a
certificate. Click “More info” → “Run anyway”.

The app window uses Microsoft Edge WebView2, which Windows 11 and up-to-date
Windows 10 already have; if it is missing, an Edge or Chrome window opens
instead.

LINUX

Any 64-bit x86 Linux from about 2022 on works: CachyOS, Arch, Manjaro,
EndeavourOS, Ubuntu 22.04 and newer, Debian 12 and newer, Linux Mint 21 and
newer, Fedora 36 and newer, openSUSE Tumbleweed and Leap 16, and systems based
on them (the engine needs glibc 2.34 and libstdc++ of GCC 12 or newer).
Nothing is installed into the system: the program lives in its folder.

1. Install the packages for the app window and its sound (once; most systems
   have some of them already). The command for your system:
     CachyOS, Arch, Manjaro, EndeavourOS:
       sudo pacman -S --needed webkit2gtk-4.1 gst-plugins-base gst-plugins-good
     Ubuntu, Debian, Linux Mint, Pop!_OS, Zorin OS, elementary OS, MX Linux:
       sudo apt install libwebkit2gtk-4.1-0 gstreamer1.0-plugins-good libgomp1
     Fedora:
       sudo dnf install webkit2gtk4.1 gstreamer1-plugins-good libgomp
     openSUSE Tumbleweed, Leap 16:
       sudo zypper install libwebkit2gtk-4_1-0 gstreamer-plugins-good libgomp1
   Without these packages the program works too: a Chrome or Chromium window
   opens instead of its own window, and without them a tab of the default
   browser.
2. Unpack the archive into a folder you can write to, for example your home
   folder:
     cd ~
     tar -xzf ~/Downloads/Ttranslator-<version>-linux-x64.tar.gz
   You get the folder ~/Ttranslator. With the mouse: right-click the archive →
   “Extract here”.
3. Start the program:
     cd ~/Ttranslator
     ./ttranslator-linux
   The translator window opens, and in it the welcome window. On the first
   start press “Download” (the model, 3.35 GB, is downloaded once; the engine
   is already in the archive) or “Skip”. You can minimize the terminal, but do
   not close it: the program closes with it (the shortcut of step 4 needs no
   terminal).
4. A shortcut in the menu of applications (optional, once):
     ./ttranslator-linux --shortcut
   Ttranslator appears in the menu of applications (KDE Plasma, GNOME, Xfce
   and others) with its icon. If you move the program folder later, run this
   command again.

To uninstall: delete the folder Ttranslator and, if you made the shortcut, the
files ~/.local/share/applications/ttranslator.desktop and
~/.local/share/icons/hicolor/256x256/apps/ttranslator.png; the data of the app
window is in ~/.local/share/ttranslator.

If something goes wrong:
- “Permission denied” at start: the file lost its permission to run (for
  example, when copied through a cloud folder). Give it back with chmod +x
  ttranslator-linux (the program does this by itself for the engine and the
  speech program).
- The app window is empty (white): this happens with NVIDIA graphics. The
  program switches WebKitGTK to its older renderer there by itself; if the
  window is still empty, start the program like this:
    env WEBKIT_DISABLE_COMPOSITING_MODE=1 ./ttranslator-linux
  or choose the window type “Browser tab” in “Settings”.
- No sound when reading aloud in the app window (“Could not play the sound”):
  the GStreamer plugins of step 1 are needed (on Arch and CachyOS:
  gst-plugins-base and gst-plugins-good). In a browser tab the sound works
  without them.
- The engine does not start, and “Details” mention GLIBC or GLIBCXX: the
  system is older (for example, Ubuntu 20.04, Debian 11, openSUSE Leap 15,
  AlmaLinux, Rocky Linux or RHEL 9). A newer version of the system helps; or
  build llama.cpp yourself and set the path to llama-server in config.json
  (engine_path).
- NixOS: ordinary Linux programs run there only through programs.nix-ld (or
  steam-run).
- Linux on ARM processors (such as the Raspberry Pi) and 32-bit Linux are not
  supported yet.

UPDATING AND MOVING TO ANOTHER COMPUTER

Everything the program downloads and remembers is in its folder:
    models       — models; models\voices — voices for reading aloud;
    engine       — the llama.cpp engine and the speech program sherpa-onnx,
                   separately for each system: engine\windows-amd64,
                   engine/linux-amd64;
    data         — saved translations, glossaries, test reports, logs;
    config.json  — settings.
- Updating: close the program and unpack the archive of the new version where
  the folder Ttranslator is (for example, on the desktop or in your home
  folder), replacing files. Models, voices, saved translations, glossaries and
  settings stay: they are not in the archive. Of your files only ui\tests.txt
  (the phrases of the “Test”) is replaced — if you changed it, keep a copy.
- To another computer with the same system (Windows → Windows, Linux → Linux),
  simply copy the whole folder Ttranslator: everything works at once, without
  downloading.
- To a computer with another system (for example, Windows → Linux): unpack the
  archive for that system there and copy models (with models\voices), data and
  config.json into the new folder. The engine for the new system is in the
  archive already; the speech program sherpa-onnx (20–30 MB) is offered in the
  model menu (the row “The speech program sherpa-onnx”). The voices need not
  be downloaded again.
- Voices can also be moved one by one: the folder of a voice (for example,
  vits-piper-ru_RU-dmitri-medium) into models\voices. Without the internet,
  the folder of the speech program (sherpa-onnx-…) can be copied from the
  engine folder of another computer with the same system into the same engine
  folder — the program finds it by itself.
- Models likewise: a .gguf file into the folder models.

PRIVACY

No telemetry, no accounts, no analytics. Your texts never leave the computer:
the engine listens only on 127.0.0.1 and requires a random key. The network is
used only to download the engine, models and voices — from official sources,
with the size and SHA-256 checked, and only after you confirm each download.

MORE

- The full guide is inside the program, in every interface language: the “?”
  button at the top right (Help).
- Logs: data\logs (launcher.log — the program, engine.log — the engine).
- The source code, building and tests: the folder source and README.md.
  Licence: MIT (LICENSE.txt), © 2026 Allasoneteam and Ttranslator authors.
  Write to us: Ttranslator@proton.me.

==============================================================================
2. УСТАНОВКА И ПЕРВЫЙ ЗАПУСК (ПО-РУССКИ)
==============================================================================

WINDOWS

1. Распакуйте архив Ttranslator-<версия>-windows-x64.zip в любую папку, куда
   можно писать (например, на рабочий стол или в «Документы», но не в Program
   Files): получится папка Ttranslator. В систему ничего не устанавливается;
   папку можно переносить целиком.
2. Дважды щёлкните Ttranslator.exe. Откроется окно переводчика (на весь
   экран), а в нём — окно приветствия (язык интерфейса, вид окна, загружать
   ли модель при запуске). При первом запуске интерфейс английский: выберите
   «Русский» в списке «Interface language» — окно сразу перейдёт на русский.
   «Начать работу» закрывает окно приветствия.
3. При первом запуске нажмите «Скачать» (там же можно выбрать язык
   интерфейса). Программа один раз скачает модель Gemma 4 E2B (3,35 ГБ, с
   huggingface.co); движок llama.cpp в архиве уже есть (если его в папке нет —
   например, программа собрана из исходников, — она скачает и его: 19 МБ, с
   github.com). Для каждого файла видно, откуда он скачивается, в какую
   папку и под каким именем. Файлы проверяются по контрольным суммам; при
   обрыве скачивание продолжится с того же места.
   Или нажмите «Пропустить»: окно программы откроется сразу, без модели, а
   модель можно выбрать и скачать потом в меню моделей (кнопка «Выбрать
   модель» вверху).
4. Дальше интернет нужен только для скачивания других моделей. Чтобы выйти,
   нажмите «Выход» вверху справа (второе нажатие подтверждает) или просто
   закройте окно: через несколько секунд модель выгрузится из памяти и
   программа завершится.

Если Windows покажет «Система Windows защитила ваш компьютер»: программа
не подписана сертификатом. Нажмите «Подробнее» → «Выполнить в любом случае».


LINUX

Подходит 64-битный Linux на процессоре Intel или AMD (x86-64), выпущенный
примерно с 2022 года: CachyOS, Arch, Manjaro, EndeavourOS, Ubuntu 22.04 и
новее, Debian 12 и новее, Linux Mint 21 и новее, Fedora 36 и новее, openSUSE
Tumbleweed и Leap 16, а также системы на их основе (движку нужны glibc 2.34
и libstdc++ от GCC 12 или новее). В систему ничего не устанавливается:
программа живёт в своей папке.

1. Поставьте пакеты для окна приложения и звука (один раз; часть из них
   обычно уже есть). Команда для вашей системы:
     CachyOS, Arch, Manjaro, EndeavourOS:
       sudo pacman -S --needed webkit2gtk-4.1 gst-plugins-base gst-plugins-good
     Ubuntu, Debian, Linux Mint, Pop!_OS, Zorin OS, elementary OS, MX Linux:
       sudo apt install libwebkit2gtk-4.1-0 gstreamer1.0-plugins-good libgomp1
     Fedora:
       sudo dnf install webkit2gtk4.1 gstreamer1-plugins-good libgomp
     openSUSE Tumbleweed, Leap 16:
       sudo zypper install libwebkit2gtk-4_1-0 gstreamer-plugins-good libgomp1
   Без этих пакетов программа тоже работает: вместо своего окна откроется
   окно Chrome или Chromium, а если их нет — вкладка браузера по умолчанию.
2. Распакуйте архив в папку, куда вы можете писать, например в домашнюю:
     cd ~
     tar -xzf ~/Загрузки/Ttranslator-<версия>-linux-x64.tar.gz
   (папка загрузок может называться Downloads). Получится папка
   ~/Ttranslator. Можно и мышью: правый щелчок по архиву → «Распаковать
   сюда» (или «Извлечь сюда»).
3. Запустите программу:
     cd ~/Ttranslator
     ./ttranslator-linux
   Откроется окно переводчика, в нём — окно приветствия (русский язык
   интерфейса — в списке «Interface language»). При первом запуске
   нажмите «Скачать»: программа один раз скачает модель (3,35 ГБ); движок
   llama.cpp в архиве уже есть. Или «Пропустить» — и выберите модель потом в
   меню моделей. Окно терминала можно свернуть, но не закрывайте его: вместе
   с ним закроется и программа (с ярлыком из пункта 4 терминал не нужен).
4. Ярлык в меню приложений (по желанию, один раз):
     ./ttranslator-linux --shortcut
   Ttranslator появится в меню приложений (KDE Plasma, GNOME, Xfce и
   другие) со своим значком. Если потом перенести папку программы,
   повторите эту команду.

Удалить программу: удалите папку Ttranslator, а если делали ярлык — ещё
файлы ~/.local/share/applications/ttranslator.desktop и
~/.local/share/icons/hicolor/256x256/apps/ttranslator.png; данные окна
WebKitGTK лежат в ~/.local/share/ttranslator.

Если что-то не так:
- «Permission denied» («Отказано в доступе») при запуске: файл потерял право
  на запуск (например, при копировании через облако). Верните его командой
  chmod +x ttranslator-linux (движку и программе озвучки программа
  возвращает это право сама).
- Окно приложения пустое (белое): так бывает с видеокартами NVIDIA.
  Программа сама включает для них запасной способ отрисовки WebKitGTK; если
  окно всё равно пустое, запустите программу так:
    env WEBKIT_DISABLE_COMPOSITING_MODE=1 ./ttranslator-linux
  или выберите в «Настройках» вид окна «Вкладка браузера».
- Нет звука при чтении вслух в окне приложения («Не удалось воспроизвести
  звук»): нужны модули GStreamer из пункта 1 (в Arch и CachyOS —
  gst-plugins-base и gst-plugins-good). Во вкладке браузера звук работает и
  без них.
- Движок не запускается, а в «Подробностях» упоминается GLIBC или GLIBCXX:
  система старше (например, Ubuntu 20.04, Debian 11, openSUSE Leap 15,
  AlmaLinux, Rocky Linux или RHEL 9). Помогает перейти на более новую
  версию системы; или соберите llama.cpp сами и укажите путь к llama-server
  в config.json (engine_path).
- NixOS: обычные программы для Linux запускаются там только через
  programs.nix-ld (или steam-run).
- Linux на процессорах ARM (например, Raspberry Pi) и 32-битный Linux пока
  не поддерживаются.


ОБНОВЛЕНИЕ И ПЕРЕНОС НА ДРУГОЙ КОМПЬЮТЕР

Всё, что программа скачала и запомнила, лежит в её папке:
  models       — модели; models\voices — голоса для чтения вслух;
  engine       — движок llama.cpp и программа озвучки sherpa-onnx, отдельно
                 для каждой системы: engine\windows-amd64, engine/linux-amd64;
  data         — сохранённые переводы, словари, отчёты теста, журналы;
  config.json  — настройки.
- Обновление: закройте программу и распакуйте архив новой версии туда же,
  где лежит папка Ttranslator (например, на рабочий стол или в домашнюю
  папку), с заменой файлов. Модели, голоса, сохранённые переводы, словари и
  настройки останутся: их в архиве нет. Из ваших файлов заменится только
  ui\tests.txt (фразы для «Теста») — если вы его меняли, сохраните копию.
- На другой компьютер с той же системой (Windows → Windows, Linux → Linux)
  можно просто скопировать всю папку Ttranslator: всё заработает сразу, без
  скачивания.
- На компьютер с другой системой (например, Windows → Linux): распакуйте там
  архив для этой системы и скопируйте в новую папку models (вместе с
  models\voices), data и config.json. Движок для новой системы в архиве уже
  есть, а программу озвучки sherpa-onnx (20–30 МБ) меню моделей предложит
  скачать отдельно: строка «Программа озвучки sherpa-onnx». Сами голоса
  заново скачивать не нужно.
- Голоса можно переносить и по одному: папку голоса (например,
  vits-piper-ru_RU-dmitri-medium) — в models\voices. Без интернета папку
  программы озвучки (sherpa-onnx-…) можно скопировать из папки engine
  другого компьютера с той же системой в ту же папку engine\… — программа
  найдёт её сама.
- Модели — так же: файл .gguf в папку models.


КОНФИДЕНЦИАЛЬНОСТЬ

Без телеметрии, учётных записей и сбора статистики. Ваши тексты никуда не
уходят с компьютера: движок слушает только 127.0.0.1 и требует случайный
ключ. Сеть нужна только для скачивания движка, моделей и голосов — с
официальных источников, с проверкой размера и SHA-256 и только после того,
как вы подтвердите каждое скачивание.

Подробная инструкция — в разделе 6 ниже и в самой программе (кнопка «?»
вверху справа, «Справка»).

==============================================================================
3. INSTALLATION UND ERSTER START (DEUTSCH)
==============================================================================

WINDOWS

1. Entpacken Sie das Archiv Ttranslator-<Version>-windows-x64.zip in einen
   beliebigen Ordner, in den Sie schreiben dürfen — zum Beispiel auf den
   Desktop oder in „Dokumente“, aber nicht nach „Programme“ (Program Files).
   Es entsteht der Ordner Ttranslator. Im System wird nichts installiert; der
   Ordner lässt sich als Ganzes verschieben.
2. Doppelklicken Sie auf Ttranslator.exe. Das Übersetzerfenster öffnet sich
   (maximiert), darin das Begrüßungsfenster: die Sprache der Oberfläche (beim
   ersten Start Englisch — stellen Sie in der Liste „Interface language“
   einfach „Deutsch“ ein), die Fensterart und ob das Modell beim Start geladen
   wird. „Loslegen“ schließt es.
3. Klicken Sie beim ersten Start auf „Herunterladen“: Das Programm lädt
   einmalig das Modell Gemma 4 E2B herunter (3,35 GB, von huggingface.co); die
   Engine llama.cpp ist schon im Archiv. Zu jeder Datei sehen Sie, woher sie
   kommt, in welchen Ordner sie geht und wie sie heißt. Die Dateien werden
   anhand ihrer Prüfsummen kontrolliert; ein abgebrochener Download wird
   fortgesetzt.
   Oder klicken Sie auf „Überspringen“: Das Fenster öffnet sich sofort, ohne
   Modell, und Sie wählen und laden ein Modell später im Modellmenü herunter
   (die Schaltfläche „Modell wählen“ oben).
4. Danach ist Internet nur noch zum Herunterladen weiterer Modelle und Stimmen
   nötig. Zum Beenden klicken Sie oben rechts auf „Beenden“ (ein zweiter Klick
   bestätigt) oder schließen einfach das Fenster: Nach wenigen Sekunden wird
   das Modell aus dem Arbeitsspeicher entladen und das Programm beendet.

Zeigt Windows „Der Computer wurde durch Windows geschützt“: Das Programm ist
nicht mit einem Zertifikat signiert. Klicken Sie auf „Weitere Informationen“ →
„Trotzdem ausführen“.

Das App-Fenster nutzt Microsoft Edge WebView2, das Windows 11 und ein
aktuelles Windows 10 bereits haben; fehlt es, öffnet sich stattdessen ein
Edge- oder Chrome-Fenster.

LINUX

Geeignet ist jedes 64-Bit-x86-Linux ab etwa 2022: CachyOS, Arch, Manjaro,
EndeavourOS, Ubuntu 22.04 und neuer, Debian 12 und neuer, Linux Mint 21 und
neuer, Fedora 36 und neuer, openSUSE Tumbleweed und Leap 16 sowie darauf
beruhende Systeme (die Engine braucht glibc 2.34 und libstdc++ von GCC 12 oder
neuer). Im System wird nichts installiert: Das Programm lebt in seinem Ordner.

1. Installieren Sie die Pakete für das App-Fenster und den Ton (einmalig;
   einige davon sind meist schon da). Der Befehl für Ihr System:
     CachyOS, Arch, Manjaro, EndeavourOS:
       sudo pacman -S --needed webkit2gtk-4.1 gst-plugins-base gst-plugins-good
     Ubuntu, Debian, Linux Mint, Pop!_OS, Zorin OS, elementary OS, MX Linux:
       sudo apt install libwebkit2gtk-4.1-0 gstreamer1.0-plugins-good libgomp1
     Fedora:
       sudo dnf install webkit2gtk4.1 gstreamer1-plugins-good libgomp
     openSUSE Tumbleweed, Leap 16:
       sudo zypper install libwebkit2gtk-4_1-0 gstreamer-plugins-good libgomp1
   Ohne diese Pakete funktioniert das Programm auch: Statt des eigenen
   Fensters öffnet sich ein Chrome- oder Chromium-Fenster, ohne diese ein Tab
   des Standardbrowsers.
2. Entpacken Sie das Archiv in einen Ordner, in den Sie schreiben dürfen, zum
   Beispiel in Ihren Home-Ordner:
     cd ~
     tar -xzf ~/Downloads/Ttranslator-<Version>-linux-x64.tar.gz
   Es entsteht der Ordner ~/Ttranslator. Mit der Maus: Rechtsklick auf das
   Archiv → „Hier entpacken“.
3. Starten Sie das Programm:
     cd ~/Ttranslator
     ./ttranslator-linux
   Das Übersetzerfenster öffnet sich, darin das Begrüßungsfenster. Klicken Sie
   beim ersten Start auf „Herunterladen“ (das Modell, 3,35 GB, wird einmalig
   heruntergeladen; die Engine ist schon im Archiv) oder auf „Überspringen“.
   Das Terminal können Sie minimieren, aber nicht schließen: Sonst schließt
   sich auch das Programm (die Verknüpfung aus Schritt 4 braucht kein
   Terminal).
4. Eine Verknüpfung im Anwendungsmenü (optional, einmalig):
     ./ttranslator-linux --shortcut
   Ttranslator erscheint mit seinem Symbol im Anwendungsmenü (KDE Plasma,
   GNOME, Xfce und andere). Wenn Sie den Programmordner später verschieben,
   führen Sie den Befehl erneut aus.

Deinstallieren: Löschen Sie den Ordner Ttranslator und, falls Sie die
Verknüpfung angelegt haben, die Dateien
~/.local/share/applications/ttranslator.desktop und
~/.local/share/icons/hicolor/256x256/apps/ttranslator.png; die Daten des
App-Fensters liegen in ~/.local/share/ttranslator.

Wenn etwas nicht klappt:
- „Permission denied“ („Keine Berechtigung“) beim Start: Die Datei hat ihr
  Ausführungsrecht verloren (zum Beispiel beim Kopieren über einen
  Cloud-Ordner). Geben Sie es mit chmod +x ttranslator-linux zurück (für die
  Engine und das Sprachausgabe-Programm macht das Programm es selbst).
- Das App-Fenster ist leer (weiß): Das kommt mit NVIDIA-Grafik vor. Das
  Programm schaltet WebKitGTK dort selbst auf die ältere Darstellung um;
  bleibt das Fenster leer, starten Sie das Programm so:
    env WEBKIT_DISABLE_COMPOSITING_MODE=1 ./ttranslator-linux
  oder wählen Sie unter „Einstellungen“ die Fensterart „Browser-Tab“.
- Kein Ton beim Vorlesen im App-Fenster („Der Ton konnte nicht abgespielt
  werden“): Es fehlen die GStreamer-Module aus Schritt 1 (unter Arch und
  CachyOS: gst-plugins-base und gst-plugins-good). Im Browser-Tab funktioniert
  der Ton auch ohne sie.
- Die Engine startet nicht, und unter „Details“ steht GLIBC oder GLIBCXX: Das
  System ist älter (zum Beispiel Ubuntu 20.04, Debian 11, openSUSE Leap 15,
  AlmaLinux, Rocky Linux oder RHEL 9). Eine neuere Systemversion hilft; oder
  bauen Sie llama.cpp selbst und tragen Sie den Pfad zu llama-server in
  config.json ein (engine_path).
- NixOS: Gewöhnliche Linux-Programme laufen dort nur über programs.nix-ld
  (oder steam-run).
- Linux auf ARM-Prozessoren (etwa dem Raspberry Pi) und 32-Bit-Linux werden
  noch nicht unterstützt.

AKTUALISIEREN UND AUF EINEN ANDEREN COMPUTER ÜBERTRAGEN

Alles, was das Programm herunterlädt und sich merkt, liegt in seinem Ordner:
models (Modelle; models\voices — Stimmen zum Vorlesen), engine (die Engine
llama.cpp und das Sprachausgabe-Programm sherpa-onnx, für jedes System
getrennt), data (gespeicherte Übersetzungen, Glossare, Testberichte,
Protokolle) und config.json (Einstellungen).
- Aktualisieren: Schließen Sie das Programm und entpacken Sie das Archiv der
  neuen Version dorthin, wo der Ordner Ttranslator liegt, und ersetzen Sie
  dabei die Dateien. Modelle, Stimmen, gespeicherte Übersetzungen, Glossare
  und Einstellungen bleiben erhalten: Sie sind nicht im Archiv. Von Ihren
  Dateien wird nur ui\tests.txt (die Sätze des „Tests“) ersetzt — wenn Sie sie
  geändert haben, sichern Sie eine Kopie.
- Auf einen anderen Computer mit demselben System (Windows → Windows, Linux →
  Linux) kopieren Sie einfach den ganzen Ordner Ttranslator: Alles
  funktioniert sofort, ohne Download.
- Auf einen Computer mit einem anderen System (zum Beispiel Windows → Linux):
  Entpacken Sie dort das Archiv für dieses System und kopieren Sie models (mit
  models\voices), data und config.json in den neuen Ordner. Die Engine für das
  neue System ist schon im Archiv; das Sprachausgabe-Programm sherpa-onnx
  (20–30 MB) bietet das Modellmenü zum Herunterladen an (die Zeile „Das
  Sprachausgabe-Programm sherpa-onnx“). Die Stimmen müssen nicht erneut
  heruntergeladen werden.

DATENSCHUTZ

Keine Telemetrie, keine Konten, keine Analyse. Ihre Texte verlassen den
Computer nie: Die Engine hört nur auf 127.0.0.1 und verlangt einen zufälligen
Schlüssel. Das Netz wird nur zum Herunterladen der Engine, der Modelle und der
Stimmen genutzt — von offiziellen Quellen, mit Prüfung von Größe und SHA-256
und erst nach Ihrer Bestätigung jedes Downloads.

MEHR

- Die vollständige Anleitung ist im Programm, in jeder Sprache der Oberfläche:
  die Schaltfläche „?“ oben rechts (Hilfe).
- Protokolle: data\logs (launcher.log — das Programm, engine.log — die
  Engine).
- Quellcode, Bauen und Tests: der Ordner source und README.md. Lizenz: MIT
  (LICENSE.txt), © 2026 Allasoneteam and Ttranslator authors. Schreiben Sie
  uns: Ttranslator@proton.me.

==============================================================================
4. INSTALACIÓN Y PRIMER INICIO (ESPAÑOL)
==============================================================================

WINDOWS

1. Descomprima el archivo Ttranslator-<versión>-windows-x64.zip en cualquier
   carpeta en la que pueda escribir — por ejemplo, en el escritorio o en
   Documentos, pero no en Archivos de programa (Program Files). Obtendrá la
   carpeta Ttranslator. No se instala nada en el sistema; la carpeta se puede
   mover entera.
2. Haga doble clic en Ttranslator.exe. Se abre la ventana del traductor
   (maximizada) y, dentro, la ventana de bienvenida: el idioma de la interfaz
   (en el primer inicio, inglés: elija «Español» en la lista «Interface
   language»), el tipo de ventana y si se carga el modelo al iniciar.
   «Empezar» la cierra.
3. En el primer inicio pulse «Descargar»: el programa descarga una sola vez el
   modelo Gemma 4 E2B (3,35 GB, de huggingface.co); el motor llama.cpp ya está
   en el archivo. De cada archivo se ve de dónde viene, a qué carpeta va y
   cómo se llama. Los archivos se comprueban con sus sumas de comprobación, y
   una descarga interrumpida continúa donde se quedó.
   O pulse «Omitir»: la ventana se abre enseguida, sin modelo, y usted elige y
   descarga uno más tarde en el menú de modelos (el botón «Elegir un modelo»,
   arriba).
4. Después, internet solo hace falta para descargar otros modelos y voces.
   Para salir, pulse «Salir» arriba a la derecha (un segundo clic lo confirma)
   o simplemente cierre la ventana: en unos segundos el modelo se libera de la
   memoria y el programa termina.

Si Windows muestra «Windows protegió su PC»: el programa no está firmado con
un certificado. Pulse «Más información» → «Ejecutar de todas formas».

La ventana de la aplicación usa Microsoft Edge WebView2, que ya tienen Windows
11 y Windows 10 actualizado; si falta, se abre en su lugar una ventana de Edge
o Chrome.

LINUX

Sirve cualquier Linux x86 de 64 bits de 2022 en adelante, más o menos:
CachyOS, Arch, Manjaro, EndeavourOS, Ubuntu 22.04 y posteriores, Debian 12 y
posteriores, Linux Mint 21 y posteriores, Fedora 36 y posteriores, openSUSE
Tumbleweed y Leap 16, y los sistemas basados en ellos (el motor necesita glibc
2.34 y libstdc++ de GCC 12 o posterior). No se instala nada en el sistema: el
programa vive en su carpeta.

1. Instale los paquetes para la ventana de la aplicación y el sonido (una sola
   vez; la mayoría de los sistemas ya tienen algunos). La orden para su
   sistema:
     CachyOS, Arch, Manjaro, EndeavourOS:
       sudo pacman -S --needed webkit2gtk-4.1 gst-plugins-base gst-plugins-good
     Ubuntu, Debian, Linux Mint, Pop!_OS, Zorin OS, elementary OS, MX Linux:
       sudo apt install libwebkit2gtk-4.1-0 gstreamer1.0-plugins-good libgomp1
     Fedora:
       sudo dnf install webkit2gtk4.1 gstreamer1-plugins-good libgomp
     openSUSE Tumbleweed, Leap 16:
       sudo zypper install libwebkit2gtk-4_1-0 gstreamer-plugins-good libgomp1
   Sin estos paquetes el programa también funciona: en lugar de su propia
   ventana se abre una ventana de Chrome o Chromium y, si no los hay, una
   pestaña del navegador predeterminado.
2. Descomprima el archivo en una carpeta en la que pueda escribir, por ejemplo
   su carpeta personal:
     cd ~
     tar -xzf ~/Descargas/Ttranslator-<versión>-linux-x64.tar.gz
   (la carpeta de descargas puede llamarse Downloads). Obtendrá la carpeta
   ~/Ttranslator. Con el ratón: clic derecho en el archivo → «Extraer aquí».
3. Inicie el programa:
     cd ~/Ttranslator
     ./ttranslator-linux
   Se abre la ventana del traductor y, dentro, la ventana de bienvenida. En el
   primer inicio pulse «Descargar» (el modelo, 3,35 GB, se descarga una sola
   vez; el motor ya está en el archivo) u «Omitir». Puede minimizar el
   terminal, pero no lo cierre: el programa se cerraría con él (el acceso
   directo del paso 4 no necesita terminal).
4. Un acceso directo en el menú de aplicaciones (opcional, una sola vez):
     ./ttranslator-linux --shortcut
   Ttranslator aparece con su icono en el menú de aplicaciones (KDE Plasma,
   GNOME, Xfce y otros). Si más tarde mueve la carpeta del programa, vuelva a
   ejecutar esta orden.

Desinstalar: elimine la carpeta Ttranslator y, si creó el acceso directo, los
archivos ~/.local/share/applications/ttranslator.desktop y
~/.local/share/icons/hicolor/256x256/apps/ttranslator.png; los datos de la
ventana de la aplicación están en ~/.local/share/ttranslator.

Si algo falla:
- «Permission denied» («Permiso denegado») al iniciar: el archivo perdió el
  permiso de ejecución (por ejemplo, al copiarlo a través de una carpeta en la
  nube). Devuélvaselo con chmod +x ttranslator-linux (para el motor y el
  programa de voz, el programa lo hace solo).
- La ventana de la aplicación está vacía (en blanco): ocurre con tarjetas
  gráficas NVIDIA. El programa cambia WebKitGTK por sí mismo a su modo de
  dibujo antiguo; si la ventana sigue vacía, inicie el programa así:
    env WEBKIT_DISABLE_COMPOSITING_MODE=1 ./ttranslator-linux
  o elija en «Ajustes» el tipo de ventana «Pestaña del navegador».
- No hay sonido al leer en voz alta en la ventana de la aplicación («No se
  pudo reproducir el sonido»): faltan los módulos de GStreamer del paso 1 (en
  Arch y CachyOS: gst-plugins-base y gst-plugins-good). En una pestaña del
  navegador el sonido funciona sin ellos.
- El motor no se inicia y en «Detalles» aparece GLIBC o GLIBCXX: el sistema es
  más antiguo (por ejemplo, Ubuntu 20.04, Debian 11, openSUSE Leap 15,
  AlmaLinux, Rocky Linux o RHEL 9). Ayuda una versión más reciente del
  sistema; o compile llama.cpp usted mismo e indique la ruta de llama-server
  en config.json (engine_path).
- NixOS: los programas normales de Linux solo funcionan allí a través de
  programs.nix-ld (o steam-run).
- Linux en procesadores ARM (como la Raspberry Pi) y Linux de 32 bits todavía
  no son compatibles.

ACTUALIZAR Y PASAR A OTRO ORDENADOR

Todo lo que el programa descarga y recuerda está en su carpeta: models
(modelos; models\voices — voces para la lectura en voz alta), engine (el motor
llama.cpp y el programa de voz sherpa-onnx, por separado para cada sistema),
data (traducciones guardadas, glosarios, informes de prueba, registros) y
config.json (ajustes).
- Actualizar: cierre el programa y descomprima el archivo de la nueva versión
  donde está la carpeta Ttranslator, sustituyendo los archivos. Los modelos,
  las voces, las traducciones guardadas, los glosarios y los ajustes se
  conservan: no están en el archivo. De sus archivos solo se sustituye
  ui\tests.txt (las frases de la «Prueba»); si lo modificó, guarde una copia.
- A otro ordenador con el mismo sistema (Windows → Windows, Linux → Linux),
  basta con copiar toda la carpeta Ttranslator: todo funciona enseguida, sin
  descargas.
- A un ordenador con otro sistema (por ejemplo, Windows → Linux): descomprima
  allí el archivo para ese sistema y copie models (con models\voices), data y
  config.json en la carpeta nueva. El motor para el nuevo sistema ya está en
  el archivo; el programa de voz sherpa-onnx (20–30 MB) lo ofrece el menú de
  modelos (la línea «Programa de voz sherpa-onnx»). No hace falta volver a
  descargar las voces.

PRIVACIDAD

Sin telemetría, sin cuentas, sin analíticas. Sus textos nunca salen del
ordenador: el motor solo escucha en 127.0.0.1 y exige una clave aleatoria. La
red solo se usa para descargar el motor, los modelos y las voces — de fuentes
oficiales, comprobando el tamaño y el SHA-256, y solo después de que usted
confirme cada descarga.

MÁS INFORMACIÓN

- La guía completa está dentro del programa, en cada idioma de la interfaz: el
  botón «?» arriba a la derecha (Ayuda).
- Registros: data\logs (launcher.log — el programa, engine.log — el motor).
- El código fuente, la compilación y las pruebas: la carpeta source y
  README.md. Licencia: MIT (LICENSE.txt), © 2026 Allasoneteam and Ttranslator
  authors. Escríbanos: Ttranslator@proton.me.

==============================================================================
5. 安装与首次启动（中文）
==============================================================================

WINDOWS

1. 把压缩包 Ttranslator-<版本>-windows-x64.zip 解压到任意一个您有写入权限的文
   件夹——例如桌面或“文档”，但不要放进 Program Files。解压后得到 Ttranslator 文
   件夹。程序不会向系统安装任何东西；整个文件夹可以随意移动。
2. 双击 Ttranslator.exe。翻译器窗口会打开（最大化），其中显示欢迎窗口：界面语
   言（首次启动时为英语——在 “Interface language” 列表中选择 “中文” 即可）、窗
   口类型，以及启动时是否加载模型。点击“开始使用”关闭欢迎窗口。
3. 首次启动时点击“下载”：程序会一次性下载 Gemma 4 E2B 模型（3.35 GB，来自
   huggingface.co）；llama.cpp 引擎已包含在压缩包中。每个文件都会显示来源、保
   存到哪个文件夹以及文件名。文件会按校验和检查，下载中断后可从中断处继续。
   也可以点击“跳过”：窗口会立即打开，暂不加载模型，之后再在模型菜单（顶部的“选
   择模型”按钮）中选择并下载模型。
4. 此后只有下载其他模型和语音时才需要联网。要退出，请点击右上角的“退出”（再点
   一次确认），或直接关闭窗口：几秒钟后模型会从内存中卸载，程序随之退出。

如果 Windows 显示“Windows 已保护你的电脑”：这是因为程序没有数字证书签名。请点
击“更多信息”→“仍要运行”。

应用窗口使用 Microsoft Edge WebView2，Windows 11 和已更新的 Windows 10 都已自
带；如果缺少，程序会改为打开 Edge 或 Chrome 窗口。

LINUX

大约 2022 年以后的任何 64 位 x86 Linux 都可以使用：CachyOS、Arch、Manjaro、
EndeavourOS、Ubuntu 22.04 及更高版本、Debian 12 及更高版本、Linux Mint 21 及更
高版本、Fedora 36 及更高版本、openSUSE Tumbleweed 和 Leap 16，以及基于它们的系
统（引擎需要 glibc 2.34 和 GCC 12 或更高版本的 libstdc++）。程序不会向系统安装
任何东西，全部内容都在它自己的文件夹中。

1. 安装应用窗口和声音所需的软件包（只需一次；大多数系统已经装有其中一部分）。
   适用于您系统的命令：
     CachyOS, Arch, Manjaro, EndeavourOS:
       sudo pacman -S --needed webkit2gtk-4.1 gst-plugins-base gst-plugins-good
     Ubuntu, Debian, Linux Mint, Pop!_OS, Zorin OS, elementary OS, MX Linux:
       sudo apt install libwebkit2gtk-4.1-0 gstreamer1.0-plugins-good libgomp1
     Fedora:
       sudo dnf install webkit2gtk4.1 gstreamer1-plugins-good libgomp
     openSUSE Tumbleweed, Leap 16:
       sudo zypper install libwebkit2gtk-4_1-0 gstreamer-plugins-good libgomp1
   没有这些软件包，程序也能运行：会改用 Chrome 或 Chromium 窗口；如果也没有这
   两个浏览器，则使用默认浏览器的标签页。
2. 把压缩包解压到您有写入权限的文件夹，例如主文件夹：
     cd ~
     tar -xzf ~/下载/Ttranslator-<版本>-linux-x64.tar.gz
   （下载文件夹也可能叫 Downloads。）解压后得到 ~/Ttranslator 文件夹。也可以用
   鼠标：右键单击压缩包 →“提取到此处”。
3. 启动程序：
     cd ~/Ttranslator
     ./ttranslator-linux
   翻译器窗口会打开，其中显示欢迎窗口。首次启动时点击“下载”（模型 3.35 GB，只
   需下载一次；引擎已包含在压缩包中）或“跳过”。终端窗口可以最小化，但不要关闭：
   关闭终端，程序也会随之关闭（第 4 步的快捷方式不需要终端）。
4. 在应用程序菜单中创建快捷方式（可选，只需一次）：
     ./ttranslator-linux --shortcut
   Ttranslator 会带着自己的图标出现在应用程序菜单中（KDE Plasma、GNOME、Xfce
   等）。如果以后移动了程序文件夹，请重新运行这条命令。

卸载：删除 Ttranslator 文件夹；如果创建过快捷方式，还要删除
~/.local/share/applications/ttranslator.desktop 和
~/.local/share/icons/hicolor/256x256/apps/ttranslator.png 两个文件；应用窗口的
数据位于 ~/.local/share/ttranslator。

如果出现问题：
- 启动时提示 “Permission denied”（权限不够）：文件失去了运行权限（例如通过云同
  步文件夹复制时）。用 chmod +x ttranslator-linux 恢复即可（引擎和语音合成程序
  的运行权限由程序自动恢复）。
- 应用窗口是空白的：使用 NVIDIA 显卡时可能出现这种情况。程序会自动让 WebKitGTK
  改用旧的绘制方式；如果窗口仍是空白，请这样启动程序：
    env WEBKIT_DISABLE_COMPOSITING_MODE=1 ./ttranslator-linux
  或在“设置”中把窗口类型改为“浏览器标签页”。
- 在应用窗口中朗读时没有声音（“无法播放声音”）：需要第 1 步中的 GStreamer 插件
  （Arch 和 CachyOS 上为 gst-plugins-base 和 gst-plugins-good）。在浏览器标签
  页中，没有这些插件也有声音。
- 引擎无法启动，“详细信息”中提到 GLIBC 或 GLIBCXX：系统版本较旧（例如 Ubuntu
  20.04、Debian 11、openSUSE Leap 15、AlmaLinux、Rocky Linux 或 RHEL 9）。升级
  系统版本即可解决；或者自行编译 llama.cpp，并在 config.json 中设置
  llama-server 的路径（engine_path）。
- NixOS：普通 Linux 程序只能通过 programs.nix-ld（或 steam-run）运行。
- 暂不支持 ARM 处理器（例如树莓派）上的 Linux 和 32 位 Linux。

更新与迁移到另一台电脑

程序下载和记住的所有内容都在它的文件夹中：models（模型；models\voices 为朗读语
音）、engine（llama.cpp 引擎和语音合成程序 sherpa-onnx，按系统分别存放）、data
（已保存的译文、术语表、测试报告、日志）和 config.json（设置）。
- 更新：关闭程序，把新版本的压缩包解压到 Ttranslator 文件夹所在的位置，并覆盖
  文件。模型、语音、已保存的译文、术语表和设置都会保留，因为压缩包中没有这些内
  容。您的文件中只有 ui\tests.txt（“测试”的句子）会被替换——如果您修改过它，请
  先备份。
- 迁移到使用相同系统的另一台电脑（Windows → Windows，Linux → Linux）：直接复制
  整个 Ttranslator 文件夹即可，无需下载，立即可用。
- 迁移到使用其他系统的电脑（例如 Windows → Linux）：在那里解压对应系统的压缩包，
  再把 models（含 models\voices）、data 和 config.json 复制到新文件夹中。新系
  统的引擎已包含在压缩包中；语音合成程序 sherpa-onnx（20–30 MB）会在模型菜单中
  提示下载（“语音合成程序 sherpa-onnx”一行）。语音本身无需重新下载。

隐私

没有遥测，没有账户，没有数据分析。您的文本绝不会离开这台电脑：引擎只监听
127.0.0.1，并且需要随机密钥。只有下载引擎、模型和语音时才会联网——从官方来源下
载，检查文件大小和 SHA-256，并且每次下载前都需要您确认。

更多信息

- 完整的使用说明内置于程序中，支持所有界面语言：右上角的“?”按钮（帮助）。
- 日志：data\logs（launcher.log 为程序日志，engine.log 为引擎日志）。
- 源代码、编译和测试：source 文件夹和 README.md。许可证：MIT（LICENSE.txt），©
  2026 Allasoneteam and Ttranslator authors。联系我们：Ttranslator@proton.me。

==============================================================================
6. ПОДРОБНАЯ ИНСТРУКЦИЯ (ПО-РУССКИ)
==============================================================================

TTRANSLATOR — локальный переводчик, версия 1.0

Локальный переводчик для девяти языков: русского, английского, немецкого,
французского, испанского, греческого, китайского, латыни и шведского.
Показывает несколько вариантов перевода, правит текст на том же языке,
учитывает ваш словарь терминов, отвечает на вопросы в окне «Спросить
модель» и читает тексты вслух. Работает на процессоре, без видеокарты; текст
никуда не отправляется. Модели запускает движок llama.cpp, голоса для чтения
вслух — программа sherpa-onnx.


ЧТО НОВОГО В 1.0

- Интерфейс — на пяти языках: к русскому, английскому и немецкому
  добавлены испанский и китайский (с ними — справка, «О программе»,
  сообщения программы и вопросы кнопки «?»). При первом запуске (новый
  config.json) интерфейс английский; язык меняется прямо на экране первого
  запуска, в окне приветствия или в «Настройках». Если в вашем config.json
  язык уже записан, ничего не меняется.
- Инструкция по установке и первому запуску — в начале этого файла, на
  английском, русском, немецком, испанском и китайском.
- Латынь вслух: латинский текст читает итальянский голос Paola (CC0) — с
  «церковным» (итальянским) произношением; ударения программа расставляет
  сама по правилам латыни (см. «Чтение вслух»). Голос скачивается в меню
  моделей, как остальные.
- «Тест»: пары фраз на любых двух языках из девяти (строки «EN: …», «RU: …»,
  «LA: …» и т. д.). В наборе — две прежние пары английский ↔ русский и четыре
  латинских крылатых выражения: Audentes fortuna iuvat, Ego cogito, ergo sum,
  Corruptissima re publica plurimae leges, Ex aequo et bono.
- «Авто» справа: текст на языке интерфейса переводится на английский (при
  английском интерфейсе — на русский), текст на другом языке — на язык
  интерфейса. Для русского интерфейса всё как раньше.
- Новый словарь (и первый, при самом первом запуске) — со столбцом языка
  интерфейса, если это испанский или китайский.

ЧТО НОВОГО В 0.9.5

- На экране первого запуска — кнопка «Пропустить»: окно программы
  открывается сразу, без модели (плашка «Модель не выбрана», вверху —
  «Выбрать модель»), а модель выбирается и скачивается в меню моделей. Выбор
  запоминается до первой скачанной модели.
- Голоса, скопированные с другого компьютера в папку models\voices, теперь
  работают. Если программы озвучки sherpa-onnx ещё нет, кнопка 🔊 и меню
  моделей подсказывают, что скачать нужно только её (строка «Программа
  озвучки sherpa-onnx»), — голоса заново не скачиваются. Папку программы
  озвучки, скопированную вручную, программа находит сама. Подробнее — в
  разделе «Обновление и перенос на другой компьютер».
- Linux: подробная инструкция по установке для CachyOS, Arch, Ubuntu, Debian,
  Fedora, openSUSE и других систем (раздел 2, «Linux»); команда
  ./ttranslator-linux --shortcut добавляет программу в меню приложений. С
  видеокартой NVIDIA окно приложения само включает запасной способ
  отрисовки (без него окно бывает пустым), а программам, потерявшим при
  копировании право на запуск, программа возвращает его сама.

ЧТО НОВОГО В 0.9.4

- Испанский голос для чтения вслух — теперь Sharvard (женский, Испания,
  CC BY 3.0). Прежний голос MLS 9972 читал короткие фразы неверно:
  выдуманными словами и в несколько раз дольше, чем нужно (это изъян самой
  модели голоса, а не программы). Новый голос скачивается в меню моделей
  одним архивом с GitHub, как остальные голоса.
- Если MLS 9972 у вас уже скачан, папку
  models\voices\vits-piper-es_ES-mls_9972-low (около 80 МБ) можно удалить:
  программа её больше не использует.
- Все голоса каталога проверены программой распознавания речи: читают по
  тексту и в обычном темпе.
- Архивы для Windows и Linux (пробные сборки): распакуйте в любую папку и
  запустите — движок llama.cpp уже внутри, при первом запуске скачивается
  только модель (см. раздел 2).

ЧТО НОВОГО В 0.9.3

- Новые голоса для чтения вслух: испанский MLS 9972 (женский, CC BY 4.0) и
  китайский Chaowen (мужской, CC0) — в меню моделей. Китайский текст
  читается по предложениям (。！？) кусками покороче.
- Окно программы при запуске открывается поверх других окон, а не за окном
  папки, из которой запущен Ttranslator.exe.
- Окно приветствия можно передвинуть мышью — за заголовок или за пустое
  место окна; при следующем открытии оно снова на своём месте. Новая
  кнопка «Выйти» рядом с «Начать работу» закрывает программу (нажать ещё
  раз для подтверждения).
- Лицензия MIT: правообладатели — Allasoneteam and Ttranslator authors
  (LICENSE.txt, «О программе»).

ЧТО НОВОГО В 0.9.2

- Окно приложения — теперь собственное окно программы, без браузера, и вид
  окна по умолчанию. При запуске оно развёрнуто на весь экран (галочка
  «Окно приложения — на весь экран» в «Настройках»). Второй вариант —
  «Вкладка браузера». Если окно приложения не откроется, откроется окно
  Edge или Chrome, а причина будет видна в «Настройках».
- «Учебный пример» точнее: строгий запрос (в начале — заголовок или вопрос,
  в конце — ответ или совет; только проверенные правила из учебников),
  низкая температура, без тем, где маленькие модели ошибаются чаще всего
  (ударение, произношение, идиомы, «любопытные факты»). Перед показом
  модель проверяет пример и исправляет найденные ошибки (галочка в окошке ▾;
  так дольше). Под полем — «Пример придуман моделью — возможны неточности и
  ошибки» и кнопка «Уточнить»: модель разбирает пример по пунктам.
- Чтение вслух: на паузе подсветка текста снимается; рядом с 🔊 — кнопка ■
  «Стоп»; правка текста прекращает чтение сама.
- «О программе»: «Выбор различных моделей для чтения вслух.»

ЧТО НОВОГО В 0.9.1

- «Учебный пример»: стрелка ▾ рядом с кнопкой — уровень (начальный,
  средний, продвинутый), тема из списка для языка текста или своя и
  «Упражнение в «Спросить модель»»: модель даёт задания без ответов, вы
  отвечаете в переписке, модель проверяет и объясняет ошибки. Под полем
  после примера — кнопка «Проверить»: модель ещё раз проверяет правило и
  ответы (ответ — в «Спросить модель»).
- Проба своего окна: в «Настройках» (и в окне приветствия) — вид окна
  «Окно Ttranslator (проба)». Это окно самой программы — со своим значком,
  без браузера, вкладок и адресной строки; внутри — веб-движок системы
  (WebView2 в Windows, WebKitGTK в Linux). Если окно не откроется,
  откроется окно Edge или Chrome, а причина будет видна в «Настройках».
  Вид окна меняется со следующего запуска.
- Начальный словарь 0.9 — отдельным файлом «Пример словаря.tsv» в папке
  data\glossary (выберите его в списке словарей).

ЧТО НОВОГО В 0.9

- Чтение вслух: кнопка 🔊 у поля текста, у каждого варианта, у «Своего
  варианта» и у ответов модели. Пока текст звучит, кнопка и текст подсвечены
  зелёным; второе нажатие — пауза. Голоса Piper (русский, английский,
  немецкий, шведский) скачиваются в меню моделей; вместе с первым голосом
  один раз скачивается программа озвучки sherpa-onnx (около 20 МБ).
- Кнопка «Учебный пример» рядом со «Случайно»: модель придумывает короткое
  правило с примерами, упражнение, «найдите ошибку» или любопытный факт о
  языке текста — его можно сразу перевести. Маленькие модели иногда
  ошибаются в правилах.
- Примеры для всех, а не только для научных текстов: подсказки в полях
  «Свой» стиль и «Контекст» (двойной щелчок по пустому полю вставляет
  пример), новый начальный словарь (5 терминов с примечаниями) и новые
  фразы для кнопки «Тест» (нейтральный и разговорный стиль, 14 заданий).

ЧТО НОВОГО В 0.8

- Формулы LaTeX ($…$ и $$…$$) не переводятся и не портятся: модель получает
  вместо них метки, а в переводе остаются сами формулы — символ в символ.
  Знак доллара в ценах («$5 и $10», «5$») формулой не считается.
- Если модель потеряла формулу, запрос повторяется; если формула так и не
  вернулась, у варианта будет предупреждение.
- «Авто» и подсказка о языке больше не путаются из-за латинских букв в
  формулах.
- Кнопка «Тест» проверяет и фразы с формулами; в отчёте — раздел «Формулы
  LaTeX».

ЧТО НОВОГО В 0.7

- При запуске открывается окно приветствия: что нового, язык интерфейса,
  вид окна (окно приложения или вкладка браузера), «Загружать выбранную
  модель при запуске» и «Показывать это окно при запуске». Выбор
  запоминается; те же настройки — в ⚙ «Настройки».
- «Свой вариант» под вариантами перевода: напишите свой перевод или возьмите
  вариант модели за основу, поправьте и сохраните в «Сохранённые».
- Для скачивания остались четыре модели Gemma 4: E2B и E4B, каждая в Q4_0 и
  Q8_0. Перед скачиванием видно, откуда скачивается файл, в какую папку и под
  каким именем; скачивание начинается только после кнопки «Скачать».

История версий — в source\docs\CHANGELOG.md.


ПЕРЕВОД

- Вверху два списка: язык текста и язык результата. При запуске слева стоит
  язык интерфейса, справа — английский (при английском интерфейсе — русский);
  «Авто» слева определяет язык по тексту. Если слева выбран язык, а текст
  явно на другом, под полем появится подсказка с кнопкой «Выбрать …» или
  «Поменять местами». Справа от списков видно текущее направление. Кнопка ↔
  между списками меняет их местами: «Авто» при этом заменяется тем языком,
  который определён сейчас, а сам текст не меняется. Если оба языка
  одинаковые (правка текста), менять нечего.
- Кнопка «Случайно» под полем текста просит модель придумать пословицу,
  поговорку или устойчивое выражение на языке текста (выбранном слева; при
  «Авто» — на языке текста в поле, а если поле пусто — на последнем
  определённом). Результат появляется в поле текста; если там уже был текст,
  кнопка сначала спрашивает «Заменить текст?» — нажмите ещё раз. Перевод сам
  не запускается. Нужна загруженная модель. Виды и темы запросов можно
  поменять в начале ui\index.html (раздел «Настройки», RANDOM).
- Кнопка «Учебный пример» рядом: модель придумывает на языке текста (как у
  «Случайно») короткое правило с примерами, упражнение «вставьте слово»,
  задание «найдите ошибку» или два слова, которые легко перепутать: в
  начале — заголовок или вопрос, в конце — ответ или совет. Пример
  появляется в поле текста — его можно сразу перевести или исправить.
- Чтобы ошибок было меньше, модель сначала проверяет свой пример (второй
  запрос) и исправляет найденные ошибки, а потом показывает его; это дольше,
  проверку можно выключить в окошке ▾. Под полем — напоминание «Пример
  придуман моделью — возможны неточности и ошибки» и кнопка «Уточнить»:
  модель ещё раз разбирает пример по пунктам (ответ — в «Спросить модель»).
  Маленькие модели (например, Gemma 4 E2B) всё равно иногда ошибаются в
  правилах: надёжнее всего — учебник или словарь; E4B точнее.
- Стрелка ▾ рядом с «Учебным примером» открывает окошко: уровень —
  начальный (A1–A2), средний (B1–B2) или продвинутый (C1–C2); тема — любая
  (каждый раз другая), из списка для языка текста или своя («Своя тема…»,
  например: предлоги места); «Проверять пример перед показом»; «Пример в
  поле текста» — то же, что кнопка; «Упражнение в «Спросить модель»» —
  модель даёт 3–5 заданий без ответов, вы отвечаете в переписке (номер
  задания и ответ), модель проверяет каждый ответ и объясняет ошибки. Выбор
  запоминается. Виды примеров, уровни, темы и запросы — в начале
  ui\index.html (раздел «Настройки», LESSON и LESSON_ASK).
- Введите текст (до 1000 знаков) и отметьте стили. Нейтральный перевод всегда
  идёт первым, остальные появляются по очереди. Если стиль дал тот же текст,
  это видно в подписи варианта.
- Контекст (необязательно) — одна строка о том, откуда текст. В пустых полях
  «Контекст» и «Свой» стиль видна подсказка («например: текст
  научно-популярной статьи», «например: художественно-литературный»);
  двойной щелчок по пустому полю вставляет этот пример, его можно поправить.
- У каждого варианта: прочитать вслух (🔊), копировать, сохранить, обратный
  перевод, другой вариант.
- Формулы LaTeX ($…$ — в строке, $$…$$ — отдельной строкой) не переводятся и
  не меняются: модель видит вместо них метки {F1}, {F2}…, а в варианты
  возвращаются сами формулы. Под полем текста видно, сколько формул найдено.
  Если модель потеряла формулу, запрос повторяется (до двух раз); если
  формула так и не вернулась, у варианта появится предупреждение — такой
  вариант стоит проверить. Знак доллара в ценах («$5 и $10», «5$») и \$
  формулой не считаются. «Замечания» получают текст с формулами как есть.
  Отключить защиту формул можно в начале ui\index.html (раздел «Настройки»,
  MATH).
- «Свой вариант» под вариантами: поле для своего перевода (при правке на том
  же языке — своего варианта текста). «Взять вариант» подставляет в поле
  любой готовый вариант — его можно поправить. Закладка сохраняет текст в
  выбранный файл «Сохранённых» со стилем «Свой вариант»; если после этого
  текст поправить и нажать закладку снова, сохранённая запись заменится
  новой; повторное нажатие без правки убирает запись. Новый перевод другого
  текста очищает поле, перевод того же текста (например, в других стилях) —
  нет.
- Ctrl+Enter — перевести, Esc — остановить.
- Текст из PDF очищается автоматически: лигатуры (ﬁ, ﬃ), переносы строк.
- Внизу справа показано время и скорость в токенах в секунду.
- Длинный текст обрабатывается дольше. По оценке, около 1000 знаков с
  Gemma 4 E2B на компьютере вроде Ryzen 5 3600 занимают 10–20 секунд на
  каждый вариант.
- Если включён словарь и в тексте нашлись его термины, рядом с кнопкой
  «Перевести» видно «Словарь: 2 термина» (наведите — появится список), а над
  вариантами — какие термины учтены.


ЧТЕНИЕ ВСЛУХ

Кнопка 🔊 у поля текста, у каждого варианта, у «Своего варианта» и у ответов
в окне «Спросить модель» читает текст вслух прямо на этом компьютере.
- Пока текст звучит, кнопка зелёная (в ней значок паузы), а сам текст
  подсвечен зелёным. Второе нажатие — пауза: подсветка текста снимается,
  у кнопки остаётся зелёная рамка; третье — продолжить. Кнопка ■ рядом с
  🔊, другая кнопка 🔊 или Esc останавливают чтение; правка текста (или
  щелчок в поле на паузе) — тоже.
- Длинный текст читается по предложениям: звук начинается после первого
  куска, следующий готовится, пока звучит предыдущий. Формулы LaTeX и
  разметка не читаются.
- Голоса скачиваются в меню моделей (кнопка с названием модели вверху),
  группа «Голоса для чтения вслух». Как и у моделей, сначала видно, откуда
  скачивается файл, в какую папку (models\voices) и под каким именем. Вместе
  с первым голосом один раз скачивается программа озвучки sherpa-onnx
  (около 20 МБ, в папку engine). Пока голос скачивается, переводить можно
  как обычно; ход скачивания виден внизу окна.
- Голоса (60–80 МБ каждый; послушать: rhasspy.github.io/piper-samples):
    Русский    Ruslan      мужской   CC BY-NC-SA 4.0 — только некоммерческое
                                      использование
    Русский    Dmitri      мужской   CC0
    Английский HFC female  женский   CC BY-NC-SA 4.0 — только некоммерческое
                                      использование
    Английский LJSpeech    женский   общественное достояние
    Немецкий   Kerstin     женский   CC0
    Испанский  Sharvard    женский   CC BY 3.0
    Китайский  Chaowen     мужской   CC0
    Шведский   Alma        женский   CC BY 4.0
    Латынь     Paola       женский   CC0 (итальянский голос)
- Китайский голос читает по словарю произношения (без espeak-ng); числа,
  даты и номера телефонов он произносит словами.
- Латинских голосов у Piper нет, поэтому латынь читает итальянский голос
  Paola с «церковным» (итальянским) произношением. Перед чтением программа
  пишет латынь итальянским письмом: ae и oe → e (caelum — «челум»), ti перед
  гласной → zi (gratia — «грациа»), ph → f, th → t, y и j → i, h не читается
  (mihi и nihil — «михи», «нихил» как michi, nichil), excelsis — «экшельсис».
  Ударение ставится по правилам латыни: на предпоследний слог, если он долгий
  (дифтонг, гласная перед двумя согласными или с макроном: fortūna), иначе —
  на третий от конца (Dóminus, hominibus, véritas). Долготы гласных в обычном
  тексте не видны, поэтому изредка ударение может оказаться не там; если в
  тексте уже стоят знаки ударения (Dóminus), программа их не трогает.
- Если для языка скачано два голоса, читает тот, что отмечен ✓; другой
  выбирается щелчком по нему. Ненужный голос удаляется значком корзины.
- Голос не держится в памяти: для каждого куска текста программа озвучки
  запускается на секунду-две и сразу освобождает память.
- Если для языка текста голоса нет, кнопка 🔊 бледная, а нажатие подсказывает,
  где его скачать. Для французского и греческого голосов пока нет.
- Голоса, скопированные с другого компьютера в папку models\voices,
  программа видит сама. Если программы озвучки ещё нет, кнопка 🔊 и меню
  моделей подскажут: скачать нужно только её (строка «Программа озвучки
  sherpa-onnx»), голоса заново не скачиваются (см. «Обновление и перенос на
  другой компьютер»). Читать вслух можно и без модели для перевода.
- При запуске без Ttranslator.exe (start.bat) чтения вслух нет.


КНОПКА «?» У ВАРИАНТА

Задаёт модели вопрос об этом варианте; вопрос и ответ появляются в окне
«Спросить модель»:
- Почему так? — объяснение выбора слов и конструкций;
- Объяснить — что чему соответствует в переводе;
- Как сказать точнее? — 2–3 более точных варианта с пояснением;
- Свой вопрос… — вариант и исходный текст вставляются в поле вопроса,
  остаётся дописать вопрос.
В вопрос автоматически входят исходный текст, вариант, его стиль и термины
словаря, если они были учтены. Для правки на том же языке и для «Замечаний»
вопросы свои. Тексты вопросов можно поменять в начале ui\index.html
(раздел «Настройки», ASK_ABOUT).


СЛОВАРЬ ТЕРМИНОВ

Вкладка «Словарь» рядом с «Спросить модель».
- «Учитывать при переводе» включает и выключает словарь.
- Программа ищет термины словаря в тексте, в том числе в других формах
  слова («теорию возмущений», «unperturbed solutions»), и передаёт модели
  только найденные. Модель ставит их в нужную форму по смыслу предложения.
  Словарь работает и для обратного перевода, и в тесте; при правке на том же
  языке он не используется.
- «+ Термин» добавляет строку; клетки правятся прямо в таблице. Корзина
  удаляет термин со второго нажатия. «+» в заголовке добавляет столбец
  другого языка, «×» убирает столбец (тоже со второго нажатия). Поиск
  фильтрует строки. Термины, найденные в текущем тексте, подсвечены.
- Правки сохраняются в файл сами, через полсекунды.
- Файлы словарей лежат в папке data\glossary; список справа вверху выбирает
  файл. Меню ⋯: новый словарь, копия под другим именем, импорт терминов из
  таблицы (.tsv, .csv, .txt — в том числе сохранённой из Excel), экспорт в
  любое выбранное место, открыть папку словарей.
- Формат файла — таблица с табуляциями (UTF-8): первая строка — названия
  языков (Английский, Русский, Немецкий… или коды en, ru, de) и столбец
  «Примечание», дальше по одному термину в строке. Файл открывается в Excel и
  LibreOffice. Если поправить его там, программа перечитает его, когда вы
  вернётесь в её окно.
- В первом словаре «Мой словарь» (создаётся при самом первом запуске) лежат
  5 примеров в трёх столбцах — английский, русский, немецкий (и четвёртый —
  язык интерфейса, если это испанский или китайский) — с
  примечаниями: название, которое не переводится (Ttranslator), слово с
  отличием в значении (decade — десятилетие, а «декада» — это 10 дней),
  замена кальки (user-friendly — удобный), идиома (a piece of cake — проще
  простого) и термин (reduced Planck constant — приведённая постоянная
  Планка). Уже созданные словари не меняются.
- В запасном режиме (start.bat) словарь хранится только в браузере; импорт и
  экспорт работают.


ЯЗЫКИ

Русский, английский, немецкий, французский, испанский, греческий, китайский
(результат — упрощённые иероглифы), латынь, шведский.
- «Авто» слева определяет язык текста. Кириллица, греческий алфавит и
  иероглифы различаются сразу. Языки с латинским алфавитом определяются по
  частым словам и характерным буквам (ä, ß, é, ç, ñ, å…). Для одного-двух
  слов определение ненадёжно — тогда выберите язык в списке. Что определилось,
  видно справа от списков.
- «Авто» справа: текст на языке интерфейса переводится на английский (при
  английском интерфейсе — на русский), текст на любом другом языке — на язык
  интерфейса. При русском интерфейсе: русский текст — на английский, любой
  другой — на русский. Любую пару можно выбрать вручную, например
  немецкий → английский.
- Gemma 4 знает все девять языков.


ПРАВКА НА ТОМ ЖЕ ЯЗЫКЕ

Выберите язык результата таким же, как язык текста (например, «Немецкий» для
немецкого текста). Тогда перевода не будет, а варианты станут такими:
- Исправленный — исправлены опечатки, грамматика и пунктуация; правки
  подсвечены (удалённое зачёркнуто, добавленное выделено зелёным); кнопка ±
  переключает подсветку;
- Другими словами — пересказ с тем же смыслом;
- стили (научный, деловой и т. д.) — текст переписан в этом стиле;
- Замечания — список логических и смысловых неточностей вместо переписанного
  текста.
Работает для всех девяти языков.


СПРОСИТЬ МОДЕЛЬ

Окно под кнопкой «Перевести» — переписка с выбранной моделью: как перевести
термин, чем различаются варианты, верна ли фраза и т. п.
- Enter или «Ввод» — отправить вопрос, Shift+Enter — новая строка. Пока модель
  отвечает, кнопка «Ввод» становится «Стоп» (то же делает Esc).
- У каждого ответа есть кнопка «Копировать».
- Модель видит только эту переписку, но не текст и варианты в окне перевода.
  Если нужно спросить о них, вставьте нужный кусок в вопрос.
- «Обновить» стирает всю переписку. Модель «помнит» разговор только потому,
  что программа каждый раз отправляет его целиком, поэтому после очистки она
  начинает с чистого листа. Сама модель при этом остаётся загруженной, и
  перевод работает дальше. Чтобы освободить память целиком, используйте
  кнопку ⏏ вверху.
- Память модели ограничена (ctx_size в config.json, 4096 токенов — несколько
  страниц текста). Когда переписка становится длиннее, самые ранние сообщения
  бледнеют, и модель их больше не учитывает.


МОДЕЛИ

Кнопка с названием модели вверху справа открывает список. Если модель ещё не
скачана, щелчок по ней показывает, откуда скачивается файл, в какую папку
(models) и под каким именем; скачивание начинается только после кнопки
«Скачать» («Отмена» — ничего не скачивать). Скачанную, но не работающую модель
можно удалить значком корзины. Скорость указана относительно Gemma 4 E2B
(на Ryzen 5 3600 — около 23 токенов в секунду).

Gemma 4 (Google) — универсальная: перевод, правка текста, вопросы:
  E2B  Q4_0    3,35 ГБ  основная
  E2B  Q8_0    4,97 ГБ  точнее Q4_0, медленнее примерно в 1,5 раза;
                        нужно от 8 ГБ памяти
  E4B  Q4_0    5,15 ГБ  качественнее E2B, медленнее примерно в 2 раза
  E4B  Q8_0    8,03 ГБ  лучшее качество, медленнее E2B примерно в 3 раза;
                        нужно от 12 ГБ памяти
Все четыре — под лицензией Apache 2.0. Модели Hy-MT2 (Tencent) для
скачивания больше не предлагаются: для работы они заметно хуже. Уже скачанный
файл Hy-MT2 остаётся в папке models и в списке, в группе «Свои файлы». Если
до обновления была выбрана Hy-MT2, программа выберет Gemma 4 E2B.

Выгрузить из памяти: кнопка ⏏ справа от названия модели. Процесс модели
завершается, вся занятая ею память освобождается, файл остаётся в папке
models. Окно остаётся: текст, варианты, чат и «Сохранённые» можно смотреть,
править и копировать. Над окном появляется плашка «Модель выгружена из
памяти» с кнопками «Загрузить» и «Выбрать другую модель». Пока модель не
загружена, кнопки «Перевести», «Ввод», «Случайно», «Учебный пример»,
«Запустить тест», «?», «Обратный перевод» и «Другой вариант» бледные, а
нажатие на них пишет
«Please load a model.». Выбор любой модели в списке тоже загружает её. При
следующем запуске программы модель загружается как обычно — если в окне
приветствия или в «Настройках» не снята галочка «Загружать выбранную модель
при запуске». Если снята, программа открывается без модели (плашка «Модель не
загружена») и не занимает память, пока вы не нажмёте «Загрузить».

Без модели: на экране первого запуска можно нажать «Пропустить». Окно
программы откроется сразу: над ним плашка «Модель не выбрана», вверху —
кнопка «Выбрать модель», которая открывает этот список (сразу после
«Пропустить» он открывается сам). Выберите модель — она скачается (вместе с
движком, если его ещё нет), и программа начнёт работать. Пока модели нет,
работают словари, «Сохранённые» и чтение вслух, а кнопки перевода пишут
«Please load a model.». Если скачивание отменить или оно оборвётся,
программа вернётся в окно без модели и напишет причину на плашке.

Свои модели: положите файл .gguf в папку models, и он появится в списке
в группе «Свои файлы». Подходят обычные диалоговые (instruct) модели; файлы,
в названии которых есть «Hy-MT», получают шаблоны запросов Hy-MT2 (она
обучена только переводу: для правки текста, вопросов и кнопки «Случайно»
лучше Gemma 4 — программа об этом подскажет).


СОХРАНЁННЫЕ

Значок закладки у варианта сохраняет перевод в выбранный файл. Файлы лежат в
папке data\saved — например, по файлу на статью, проект или тему. Каждый
файл — таблица с табуляциями (открывается в Excel и LibreOffice); в столбце
«стиль» указана и модель, а у своего перевода — «Свой вариант».
- Вверху панели «Сохранённые» — выбор файла и меню «⋯»: «Новый файл…»,
  «Сохранить копию как…», «Импорт из файла…», «Экспорт в таблицу (.tsv)…»,
  «Экспорт в текст (.txt)…», «Открыть папку». Число у кнопки «Сохранённые» —
  записи выбранного файла.
- Импорт добавляет записи в выбранный файл, повторы пропускаются. Подходят:
  таблица этой программы и её текстовый экспорт; простая таблица из двух
  столбцов — текст и перевод (в .txt через табуляцию, в .csv через точку с
  запятой или запятую; первая строка может называть языки, например
  «English;Русский»); список в .txt — по тексту на строку, без перевода.
- Экспорт в текст (.txt) — читаемый список «оригинал → перевод»: отправить,
  распечатать, вставить в документ. Его же можно импортировать обратно.
- Поиск находит записи по словам из текста, перевода, контекста или стиля
  (все слова запроса, в любом порядке; ё и е не различаются).
- «В поле» вставляет текст записи в поле перевода и ставит её языки; если в
  поле уже есть другой текст, кнопка сначала спрашивает «Заменить текст?».
  Перевод сам не запускается.
- Файл можно поправить в Excel или LibreOffice: программа перечитает его,
  когда её окно снова станет активным. Пока файл открыт в Excel, новая
  закладка в него может не записаться — программа об этом скажет.
- При запуске без Ttranslator.exe (start.bat) сохранённые хранятся только в
  этом браузере; импорт и экспорт работают.


ТЕСТ

Кнопка «Тест» переводит пары фраз из ui\tests.txt в обе стороны, нейтрально
и в разговорном стиле, а также исправляет каждую фразу на её языке. Отчёт с
временем, текстами и правками сохраняется в data\reports; в нём указана
модель, так что отчёты разных моделей можно сравнивать. Если словарь включён,
найденные в фразах термины учитываются; это видно в отчёте. Кроме фраз из
tests.txt, тест переводит фразу с формулами LaTeX (в обе стороны; MATH_TESTS в
ui\index.html) и пишет в отчёт, остались ли формулы на месте и сколько раз
пришлось повторить запрос.
- Пара — две строки подряд на двух разных языках: «EN: …» и «RU: …», «LA: …»
  и «EN: …» и т. д. (коды EN, RU, DE, FR, ES, EL, ZH, LA, SV); пары
  разделяются пустой строкой, строки с # в начале пропускаются. Свои пары
  можно дописывать.
- Набор 1.0: две пары английский ↔ русский (как в 0.9) и четыре латинских
  крылатых выражения с английским переводом — Audentes fortuna iuvat
  (Вергилий), Ego cogito, ergo sum (Декарт), Corruptissima re publica
  plurimae leges (Тацит), Ex aequo et bono (юридический термин). Всего 38
  заданий. Крылатые выражения модели часто знают наизусть, а у коротких фраз
  chrF скачет сильнее — оценки латыни сравнивайте между моделями, а не с
  оценками длинных фраз.


ОКНО ПРИВЕТСТВИЯ

Открывается при запуске программы (при перезагрузке окна и во втором окне,
открытом позже, — нет; открыть его снова можно в «Настройках»):
- что нового в этой версии;
- язык интерфейса — окно перезагружается на новом языке, окно приветствия
  остаётся открытым; языки перевода ставятся заново: слева — новый язык
  интерфейса;
- вид окна: «Окно приложения» (окно самой программы, см. «Окно
  приложения» ниже) или «Вкладка браузера»; меняется со следующего запуска;
- «Загружать выбранную модель при запуске» (рядом — название модели).
  Галочка действует и на этот запуск: если её снять и нажать «Начать
  работу», модель выгрузится; если поставить — загрузится. Окно приветствия,
  открытое позже (второе окно, кнопка в «Настройках»), модель уже не трогает;
- «Показывать это окно при запуске» — если снять, окно больше не появляется;
  вернуть его можно в «Настройках».
Всё сохраняется сразу и показывается при следующем запуске таким, каким было
выбрано. Кнопки: «Начать работу» (или Esc) — закрыть окно и работать;
«Выйти» — закрыть программу (нажать ещё раз для подтверждения, как
«Выход» вверху); «О программе» — сведения о программе. Окно приветствия
можно передвинуть мышью — за заголовок или за пустое место окна (не за
кнопки); за край окна программы оно не уходит, а при следующем открытии
снова стоит на своём месте.


ОКНО ПРИЛОЖЕНИЯ

«Окно приложения» (вид окна по умолчанию) — окно самой программы, без
браузера: со своим значком на панели задач, без вкладок, адресной строки и
расширений браузера. Внутри — веб-движок, который уже есть в системе:
Microsoft Edge WebView2 в Windows (в Windows 11 встроен, в Windows 10 почти
всегда уже установлен) и WebKitGTK 4.1 в Linux (пакет libwebkit2gtk-4.1-0).
Окно — отдельная маленькая программа ttranslator-window.exe
(ttranslator-window-linux) рядом с Ttranslator.exe.
- При запуске окно развёрнуто на весь экран; кнопка «Восстановить» в его
  заголовке делает его обычного размера. Галочка «Окно приложения — на весь
  экран» в «Настройках» выключает это.
- При запуске окно открывается поверх других окон — в том числе окна папки,
  из которой запущен Ttranslator.exe. (Если, пока окно открывается, вы
  перешли в другую программу, Windows его поверх не ставит, а подсвечивает
  значок на панели задач.)
- Если окно не открылось (нет WebView2 или WebKitGTK), откроется окно Edge
  или Chrome без вкладок, а в «Настройках» под видом окна будет причина.
  WebView2 Runtime можно бесплатно скачать с сайта Microsoft.
- Ссылки на сайты и адрес почты открываются в обычном браузере и почтовой
  программе; экспорт словаря и «Сохранённых» — через окно «Сохранить как».
- Закрыли окно — программа завершается через несколько секунд; «Выход»
  закрывает окно.
- Мелкие запомненные удобства окна (выбранные языки, свой стиль, выбор
  «Учебного примера») у окна приложения свои, отдельные от браузера;
  настройки из config.json общие.
- Данные окна WebView2 (хранилище страницы, кэш) лежат в data\webview — папка
  программы остаётся переносимой. В Linux такие данные WebKitGTK хранит в
  ~/.local/share/ttranslator.
- «Вкладка браузера» — интерфейс во вкладке браузера, выбранного в системе
  по умолчанию.


НАСТРОЙКИ

Кнопка ⚙ вверху справа:
- Язык интерфейса — English, русский, Deutsch, Español или 中文 (при первом
  запуске — английский). Окно перезагружается на
  новом языке; текст в поле и контекст остаются, а полученные варианты и
  переписка — нет. На этом языке и справка, и сообщения программы, и вопросы
  кнопки «?» (модель отвечает на языке вопроса). Запросы на перевод от этого
  не меняются. Язык можно выбрать и на экране первого запуска.
- Тема — светлая или тёмная.
- Размер шрифта — мелкий, обычный, крупный или очень крупный.
- Вид окна («Окно приложения» или «Вкладка браузера»; галочка «Окно
  приложения — на весь экран») и «При запуске»: «Загружать выбранную
  модель», «Показывать окно приветствия» — то же, что в окне приветствия.
- «Справка», «О программе», «Окно приветствия» и «Выйти из программы».
Всё сохраняется сразу в config.json и действует в любом окне программы.

config.json (появляется после первого запуска):
  active_model       — выбранная модель (меняется из списка моделей);
  ctx_size           — размер контекста движка (4096); это и память окна
                       «Спросить модель». Значение 8192 позволит вести
                       переписку вдвое длиннее, но займёт больше памяти;
  threads            — число потоков процессора (0 = автоматически);
  ui_port            — порт окна (8765);
  engine_path        — путь к своему llama-server, если скачанный не подходит;
  extra_engine_args  — дополнительные параметры движка;
  ui_language        — язык интерфейса: en, ru, de, es или zh (без
                       config.json — en);
  theme              — тема: light или dark;
  font_scale         — размер шрифта в процентах: 90, 100, 115 или 130;
  show_welcome       — показывать окно приветствия при запуске: true или false;
  launch_mode        — вид окна: window (окно приложения) или tab (вкладка
                       браузера); прежнее app становится window;
  start_maximized    — окно приложения на весь экран при запуске: true или
                       false;
  load_model_at_start — загружать выбранную модель при запуске: true или false;
  voices             — какой голос читает каждый язык (меняется в меню
                       моделей), например {"ru": "ru-ruslan"};
  setup_skipped      — на экране первого запуска нажата «Пропустить»: окно
                       открывается без модели; исчезает, когда появится
                       первая модель.
Языки, стили, шаблоны запросов, параметры генерации для каждого семейства
моделей, настройки окна «Спросить модель», вопросы кнопки «?», начальные
термины словаря, защита формул LaTeX (MATH), фразы с формулами для теста
(MATH_TESTS), примеры в пустых полях (STYLE_EXAMPLE, CTX_EXAMPLE), виды и
темы учебных примеров (LESSON) и чтение вслух (SPEAK: длина куска и
скорость речи) описаны в начале файла ui\index.html (раздел «Настройки»).


ЕСЛИ ЧТО-ТО НЕ РАБОТАЕТ

- Справка в самой программе — кнопка «?» вверху справа.
- Журналы: data\logs (launcher.log — программа, engine.log — движок).
- Если окно приложения не открывается: причина — в «Настройках» под видом
  окна и в launcher.log (строки «own window»); тогда открывается окно Edge
  или Chrome. Можно выбрать «Вкладка браузера».
- Если не читает вслух: в launcher.log строки «tts» показывают, что ответила
  программа озвучки. Помогает удалить голос в меню моделей и скачать его
  снова. В Windows программе озвучки, как и движку, нужен Microsoft Visual
  C++ Redistributable.
- Плашка над окном показывает, что с моделью: загрузка (синяя), выгружена
  (жёлтая), ошибка движка (красная; «Подробности» открывают журнал). Если
  написано «Программа Ttranslator не отвечает», её, скорее всего, закрыли:
  запустите снова; тексты, уже полученные в окне, можно скопировать.
- Запасной запуск без Ttranslator.exe: start.bat (Windows) или start.sh (Linux),
  когда движок и модель уже скачаны. Берётся первая найденная в папке models
  модель Gemma 4 (E2B Q4_0, E2B Q8_0, E4B Q4_0, E4B Q8_0), а если их нет —
  Hy-MT2-1.8B. В этом режиме сохранённые переводы хранятся только в браузере,
  а выбора и выгрузки модели и окна приветствия нет.
- Скачать файлы вручную:
  движок для Windows: https://github.com/ggml-org/llama.cpp/releases/download/b11435/llama-b11435-bin-win-cpu-x64.zip
          распаковать в engine\windows-amd64
  движок для Linux: https://github.com/ggml-org/llama.cpp/releases/download/b11435/llama-b11435-bin-ubuntu-x64.tar.gz
          распаковать в engine/linux-amd64
  модель: https://huggingface.co/google/gemma-4-E2B-it-qat-q4_0-gguf/resolve/675cff42a74c774d6cb76f76d8eacb49b48c9b93/gemma-4-E2B_q4_0-it.gguf
          положить в models
  программа озвучки для Windows: https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.13.7/sherpa-onnx-v1.13.7-win-x64-shared-MD-Release.tar.bz2
          распаковать в engine\windows-amd64
  программа озвучки для Linux: https://github.com/k2-fsa/sherpa-onnx/releases/download/v1.13.7/sherpa-onnx-v1.13.7-linux-x64-shared.tar.bz2
          распаковать в engine/linux-amd64


ИСХОДНЫЙ КОД

Папка source: программа запуска на Go (только стандартная библиотека),
окно приложения на C++ (source\window, библиотека webview), описание
устройства программы и план развития (source\docs), инструкции для работы
над программой с Claude (source\CLAUDE.md) и автоматические тесты
(source\tests). Сборка: source/build.sh (нужен Go 1.24 или новее; для окна
приложения — компилятор C++, см. source\window\README.md), архивы для
Windows и Linux — source/release.sh. README.md —
описание программы по-английски для GitHub (репозиторий
github.com/Allasoneteam/Ttranslator). Лицензия — MIT (файл
LICENSE.txt), правообладатели — Allasoneteam and Ttranslator authors; окно
приложения использует библиотеку webview (MIT) и в Windows — Microsoft Edge
WebView2.
