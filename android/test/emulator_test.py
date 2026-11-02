# Ttranslator for Android, the check in the emulator (android/ci.sh starts the emulator and then this script).
#   python3 emulator_test.py <apk> <out-dir> <tiny-model.gguf> [--quick]
# adb must see one booted emulator. --quick: only the core (older Android versions).
# What is checked: the APK installs; the window starts the launcher from the app's library folder and the launcher
# answers (/api/state, through adb forward); the engine (llama-server) and the reading-aloud program are found; a
# tiny model (random weights: its "translations" are gibberish) loads and a translation goes through the launcher to
# the engine — over HTTP and in the page itself (the page is driven over the DevTools protocol of the WebView); the
# page has the window functions; Chinese fonts; reading aloud (a voice downloaded from GitHub inside the emulator:
# DNS and HTTPS of the launcher on Android); the launcher keeps running in the background; it ends with the app;
# «Выход» closes the window. Screenshots of the phone screen and the logs go to <out-dir>.
import json, os, re, subprocess, sys, time, urllib.error, urllib.request

APK, OUT, MODEL = sys.argv[1], sys.argv[2], sys.argv[3]
QUICK = '--quick' in sys.argv
PKG = 'io.github.allasoneteam.ttranslator'
ACT = PKG + '/.MainActivity'
EXT = '/sdcard/Android/data/%s/files' % PKG
PORT, CDP_PORT = 18765, 19222
BASE = 'http://127.0.0.1:%d' % PORT
os.makedirs(OUT, exist_ok=True)
results = []


def log(line):
    results.append(line)
    print(line, flush=True)


def ok(cond, msg):
    log(('OK   ' if cond else 'FAIL ') + msg)
    return cond


def info(msg):
    log('INFO ' + msg)


def adb(*args, timeout=120, check=False):
    r = subprocess.run(['adb'] + list(args), capture_output=True, timeout=timeout)
    if check and r.returncode != 0:
        raise RuntimeError('adb %s: %s' % (' '.join(args), r.stderr.decode(errors='replace')))
    return r


def sh(cmd, timeout=60):
    return adb('shell', cmd, timeout=timeout).stdout.decode(errors='replace').replace('\r', '')


def shot(name):
    p = os.path.join(OUT, name + '.png')
    with open(p, 'wb') as f:
        f.write(adb('exec-out', 'screencap', '-p', timeout=60).stdout)
    info('screenshot %s (%d bytes)' % (os.path.basename(p), os.path.getsize(p)))
    return p


def get(path, timeout=5):
    with urllib.request.urlopen(BASE + path, timeout=timeout) as r:
        return r.status, r.headers.get('Content-Type', ''), r.read()


def api(path):
    return json.loads(get(path)[2])


def post(path, body, timeout=30):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method='POST',
                                 headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.headers.get('Content-Type', ''), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get('Content-Type', ''), e.read()


def wait(cond, timeout, step=1.0):
    end = time.time() + timeout
    while time.time() < end:
        try:
            v = cond()
            if v:
                return v
        except Exception:
            pass
        time.sleep(step)
    return None


def alive():
    try:
        return json.loads(get('/api/ping', 2)[2]).get('app') == 'tdoc-translator'
    except Exception:
        return False


def procs():
    """Processes of the app: [(pid, ppid, name)] for the app, the launcher, the engine, the reading-aloud program."""
    out = []
    for line in sh('ps -A -o PID,PPID,NAME').splitlines()[1:]:
        p = line.split()
        if len(p) >= 3 and (p[2] == PKG or p[2].startswith('libttranslator') or p[2].startswith('libllama-server')
                            or p[2].startswith('libsherpa-onnx')):
            out.append((p[0], p[1], p[2]))
    return out


def start_app():
    adb('shell', 'am', 'start', '-W', '-n', ACT, timeout=60)
    adb('forward', 'tcp:%d' % PORT, 'tcp:8765', check=True)
    return wait(alive, 90)


def page_session(p):
    """The page of the app over the DevTools protocol of its WebView (the test APK enables WebView debugging)."""
    pid = sh('pidof ' + PKG).strip()
    sock = 'webview_devtools_remote_' + pid
    if not wait(lambda: sock in sh('cat /proc/net/unix'), 30):
        raise RuntimeError('no DevTools socket ' + sock)
    adb('forward', 'tcp:%d' % CDP_PORT, 'localabstract:' + sock, check=True)
    b = p.chromium.connect_over_cdp('http://127.0.0.1:%d' % CDP_PORT, timeout=30000)
    def find():
        for c in b.contexts:
            for pg in c.pages:
                if pg.url.startswith('http://127.0.0.1:8765'):
                    return pg
    page = wait(find, 30)
    if not page:
        raise RuntimeError('the page of the launcher is not in the WebView: %s' % [pg.url for c in b.contexts for pg in c.pages])
    return b, page


failed = False
try:
    sdk = sh('getprop ro.build.version.sdk').strip()
    info('Android %s (API %s), %s, ABI %s' % (sh('getprop ro.build.version.release').strip(), sdk,
                                            sh('getprop ro.product.model').strip(), sh('getprop ro.product.cpu.abi').strip()))
    wv = re.search(r'Current WebView package \(name, version\): \((.*?)\)', sh('dumpsys webviewupdate'))
    info('WebView: ' + (wv.group(1) if wv else '?'))
    flags = re.search(r'^flags\s*:\s*(.*)$', sh('cat /proc/cpuinfo'), re.M)
    info('CPU of the emulator: %d cores, %s' % (sh('cat /proc/cpuinfo').count('processor\t'),
         ' '.join(f for f in (flags.group(1).split() if flags else []) if f in ('sse4_2', 'avx', 'avx2', 'fma', 'f16c', 'avx512f', 'avx512_vnni', 'avx_vnni'))))
    info('memory of the emulator: ' + ' '.join(sh('cat /proc/meminfo').split('\n')[:3]))

    # ---------------------------------------------------------------- install and start
    r = adb('install', '-r', APK, timeout=300)
    ok(r.returncode == 0, 'the APK installs: ' + (r.stdout + r.stderr).decode(errors='replace').strip().splitlines()[-1])
    libdir = re.search(r'legacyNativeLibraryDir=(\S+)', sh('dumpsys package ' + PKG))
    info('library folder: %s' % (libdir.group(1) if libdir else '?'))
    t0 = time.time()
    ok(start_app(), 'the window starts the launcher from the app\'s library folder; it answers in %.1f s' % (time.time() - t0))
    st = api('/api/state')
    ok(st['phase'] in ('setup', 'nomodel'), 'first start: phase %s (no model yet)' % st['phase'])
    ok(st['engine']['present'], 'the engine is found: llama-server in the library folder (config.json engine_path)')
    ok(st['tts']['engine']['present'], 'the reading-aloud program is found (tts.json)')
    info('machine: %s' % json.dumps(st.get('machine'), ensure_ascii=False))
    ok(st['models_dir'].startswith('/storage/emulated/0/Android/data/' + PKG), 'program folder on the shared storage: %s' % st['models_dir'])
    pr = procs()
    app_pid = [x[0] for x in pr if x[2] == PKG]
    launcher = [x for x in pr if x[2].startswith('libttranslator')]
    ok(app_pid and launcher and launcher[0][1] == app_pid[0], 'the launcher is a child process of the app: %s' % pr)
    time.sleep(2)
    shot('1-first-start')

    # ---------------------------------------------------------------- a model: a tiny one, copied by "USB" (adb push)
    r = adb('push', MODEL, EXT + '/models/tiny-test.gguf', timeout=120)
    ok(r.returncode == 0, 'a model copied into Android/data/…/files/models (as over USB): ' + r.stdout.decode(errors='replace').strip()[-80:])
    ok(wait(lambda: any(m['id'] == 'file:tiny-test.gguf' and m['present'] for m in api('/api/state')['models']), 20),
       'the launcher lists it as an own file')
    code, _, body = post('/api/model', {'id': 'file:tiny-test.gguf'})
    ok(code == 200, 'model chosen (as in the menu of models): %d %s' % (code, body[:120]))
    t0 = time.time()
    st = wait(lambda: (lambda s: s if s['phase'] in ('ready', 'error') else None)(api('/api/state')), 240)
    ok(st and st['phase'] == 'ready', 'the engine started with the model in %.1f s: %s' % (time.time() - t0, st and (st['phase'], st.get('error'), st.get('engine_info'))))
    if st and st['phase'] != 'ready':
        info('engine log:\n' + (st.get('engine_log') or ''))
    pr = procs()
    eng = [x for x in pr if x[2].startswith('libllama-server')]
    ok(eng and launcher and eng[0][1] == launcher[0][0], 'the engine is a child process of the launcher: %s' % pr)

    # ---------------------------------------------------------------- a translation through the launcher to the engine
    t0 = time.time()
    code, ctype, body = post('/v1/chat/completions', {'messages': [{'role': 'user', 'content': 'Translate into German: Good morning!'}],
                                                      'max_tokens': 12, 'temperature': 0.2}, timeout=120)
    try:
        j = json.loads(body)
    except ValueError:
        j = {}
    ok(code == 200 and j.get('choices'), 'a reply of the engine through the launcher (%.1f s): %s' % (time.time() - t0, body[:200]))
    if j.get('timings'):
        info('engine speed in the emulator (tiny model): %.1f tokens/s' % j['timings'].get('predicted_per_second', 0))

    if not QUICK:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b, page = page_session(p)
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            ok(page.evaluate("typeof ttwSaveFile === 'function' && typeof ttwOpenExternal === 'function' && typeof ttwClose === 'function'"),
               'the page has the window functions (ttwSaveFile, ttwOpenExternal, ttwClose): OWN_WINDOW')
            info('page size: %s' % page.evaluate("JSON.stringify({w: innerWidth, h: innerHeight, dpr: devicePixelRatio, ua: navigator.userAgent})"))
            page.wait_for_selector('body[data-model="ready"]', timeout=120000)
            if page.is_visible('#welcomeView'):
                shot('2-welcome')
                page.click('#welcomeStart')
            page.wait_for_timeout(800)
            shot('3-main-window')
            page.evaluate('window.__ttTestMarker = 1')

            # a translation in the page, as the user does it
            page.fill('#src', 'Good morning! The weather is nice today.')
            page.wait_for_timeout(500)
            page.click('#goBtn')
            page.wait_for_selector('.card', timeout=120000)
            page.wait_for_selector('#goBtn:not([hidden])', timeout=180000)
            cards = page.locator('.card').count()
            ok(cards >= 1, 'the page translated through the engine: %d variant cards (text of the first: %r)'
               % (cards, page.locator('.card .card-text').first.inner_text()[:60] if cards else ''))
            page.wait_for_timeout(500)
            page.screenshot(path=os.path.join(OUT, '4-translation-webview.png'))
            shot('4-translation')

            # the clipboard (the copy button of a variant)
            if page.locator('.card [data-act=copy]').count():
                page.locator('.card [data-act=copy]').first.click()
                page.wait_for_timeout(700)
                info('copy button: toast %r' % page.evaluate("(document.querySelector('.toast.show') || {}).textContent || ''"))

            # Chinese interface: the fonts of the phone
            post('/api/settings', {'ui_language': 'zh'})
            page.reload()
            page.wait_for_selector('body[data-model="ready"]', timeout=60000)
            if page.is_visible('#welcomeView'):
                page.click('#welcomeStart')
            page.fill('#src', '今天天气很好。')
            page.wait_for_timeout(800)
            shot('5-chinese')
            fonts = page.evaluate("getComputedStyle(document.body).fontFamily")
            ok('Noto Sans CJK SC' in fonts or 'sans-serif' in fonts, 'Chinese interface, font list: ' + fonts[:120])
            post('/api/settings', {'ui_language': 'en'})
            page.reload()
            page.wait_for_selector('body[data-model="ready"]', timeout=60000)
            page.evaluate('window.__ttTestMarker = 1')
            ok(not errors, 'no errors in the page: %s' % errors[:3])
            b.close()

        # ---------------------------------------------------------------- reading aloud
        # the voice is downloaded by the launcher from github.com inside the emulator: DNS and HTTPS of Go on Android
        t0 = time.time()
        code, _, body = post('/api/voice', {'id': 'en-ljspeech'})
        ok(code == 200, 'voice download started: %d %s' % (code, body[:120]))
        def voice_done():
            s = api('/api/state')['tts']
            v = [x for x in s['voices'] if x['id'] == 'en-ljspeech'][0]
            if s['download'].get('error'):
                return 'error: ' + s['download']['error']
            return 'ok' if v['present'] and not s['download']['active'] else None
        r = wait(voice_done, 600, 2)
        ok(r == 'ok', 'voice en-ljspeech (67 MB) downloaded and unpacked by the launcher in %.0f s: %s' % (time.time() - t0, r))
        if r == 'ok':
            t0 = time.time()
            code, ctype, body = post('/api/tts', {'lang': 'en', 'text': 'Hello! This is Ttranslator on Android.', 'speed': 1}, timeout=90)
            ok(code == 200 and body[:4] == b'RIFF', 'read aloud (sherpa-onnx in the library folder): %d %s, %d bytes, %.1f s'
               % (code, ctype, len(body), time.time() - t0))
            if body[:4] == b'RIFF':
                with open(os.path.join(OUT, 'tts-en.wav'), 'wb') as f:
                    f.write(body)
            else:
                info('reply: %s' % body[:300])

        # ---------------------------------------------------------------- in the background
        adb('shell', 'input', 'keyevent', 'KEYCODE_HOME')
        time.sleep(30)
        ok(alive() and api('/api/state')['phase'] == 'ready', 'after 30 s in the background the launcher still answers, the model is loaded')
        adb('shell', 'am', 'start', '-W', '-n', ACT, timeout=60)
        time.sleep(2)
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b, page = page_session(p)
            ok(page.evaluate('window.__ttTestMarker') == 1, 'back in front: the same page, not reloaded (the text stays)')
            b.close()

        # ---------------------------------------------------------------- Android ends the app: its programs end too
        adb('shell', 'input', 'keyevent', 'KEYCODE_HOME')
        time.sleep(2)
        adb('shell', 'am', 'kill', PKG)
        time.sleep(3)
        left = procs()
        if any(x[2] == PKG for x in left):
            info('am kill did not end the app (it was not in the background yet): force-stop')
            adb('shell', 'am', 'force-stop', PKG)
            time.sleep(3)
            left = procs()
        ok(not left, 'Android ended the app in the background: the launcher and the engine ended with it: %s' % left)

        ok(start_app(), 'started again')
        st = wait(lambda: (lambda s: s if s['phase'] in ('ready', 'error') else None)(api('/api/state')), 240)
        ok(st and st['phase'] == 'ready', 'the model is loaded again at start')

    # ---------------------------------------------------------------- «Выход» (Exit)
    if not QUICK:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b, page = page_session(p)
            page.wait_for_selector('body[data-model="ready"]', timeout=60000)
            if page.is_visible('#welcomeView'):
                page.click('#welcomeStart')
            shot('6-before-exit')
            try:
                page.click('#quitBtn', timeout=5000)
                page.click('#quitBtn', timeout=5000)
            except Exception as e:
                info('the Exit button is not reachable on this screen (%s): quitApp() twice' % str(e).splitlines()[0])
                page.evaluate('quitApp()')
                page.evaluate('quitApp()')
            try:
                b.close()
            except Exception:
                pass
    else:
        post('/api/quit', {})
    gone = wait(lambda: not alive() and not [x for x in procs() if x[2] != PKG], 30)
    ok(gone, 'Exit: the launcher and the engine have ended: %s' % procs())
    if not QUICK:
        time.sleep(2)
        top = sh('dumpsys activity activities | grep -E "mResumedActivity|topResumedActivity"')
        ok(PKG not in top, 'Exit closed the window: %s' % top.strip()[:160])
except Exception as e:
    import traceback
    log('FAIL exception: %s' % e)
    traceback.print_exc()
finally:
    try:
        shot('9-last')
    except Exception:
        pass
    logs = os.path.join(OUT, 'device-logs')
    os.makedirs(logs, exist_ok=True)
    adb('pull', EXT + '/data/logs/.', logs, timeout=120)
    adb('pull', EXT + '/config.json', logs, timeout=60)
    with open(os.path.join(OUT, 'logcat.txt'), 'wb') as f:
        f.write(adb('logcat', '-d', '-v', 'time', timeout=120).stdout)
    fails = [x for x in results if x.startswith('FAIL')]
    log('FAILS: %d' % len(fails))
    with open(os.path.join(OUT, 'results.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(results) + '\n')
    sys.exit(1 if fails else 0)
