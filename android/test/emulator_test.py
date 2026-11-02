# Ttranslator for Android, the check in the emulator (android/ci.sh starts the emulator and then this script).
#   python3 emulator_test.py <apk> <out-dir> <tiny-model.gguf> [--quick] [--real-model]
# adb must see one booted emulator. --quick: only the core (older Android versions). --real-model: afterwards the
# app downloads and runs the catalog model Gemma 4 E2B · Q4_0 (3.35 GB; the emulator needs 8 GB of memory).
# What is checked: the APK installs; the window starts the launcher from the app's library folder and the launcher
# answers (/api/state, through adb forward); the engine (llama-server) and the reading-aloud program are found; a
# tiny model (random weights: its "translations" are gibberish) loads and a translation goes through the launcher to
# the engine — over HTTP and in the page itself; the page has the window functions; Chinese fonts; reading aloud (a
# voice downloaded from GitHub inside the emulator: DNS and HTTPS of the launcher on Android); the launcher keeps
# running in the background; it ends with the app; «Выход» closes the window. Screenshots and logs go to <out-dir>.
# The page is driven over the DevTools protocol of the WebView (the test APK enables WebView debugging) with a small
# client below: Playwright cannot attach to a WebView (it needs browser contexts, which WebView does not have).
# Python standard library only.
import base64, json, os, re, socket, struct, subprocess, sys, time, urllib.error, urllib.request

APK, OUT, MODEL = sys.argv[1], sys.argv[2], sys.argv[3]
QUICK = '--quick' in sys.argv
REAL = '--real-model' in sys.argv
DEADLINE = float(os.environ.get('TT_DEADLINE') or 0)  # android/ci.sh: when the CI job must be done (seconds since 1970)
PKG = 'io.github.allasoneteam.ttranslator'
ACT = PKG + '/.MainActivity'
EXT = '/sdcard/Android/data/%s/files' % PKG
PORT, CDP_PORT = 18765, 19222
BASE = 'http://127.0.0.1:%d' % PORT
os.makedirs(OUT, exist_ok=True)
results = []


def time_left():
    return DEADLINE - time.time() if DEADLINE else 1e9


def log(line):
    results.append(line)
    print(line, flush=True)


def ok(cond, msg):
    log(('OK   ' if cond else 'FAIL ') + msg)
    return cond


def info(msg):
    log('INFO ' + msg)


def step(name, fn):
    """A part of the check: an exception is a FAIL of this part, the next parts still run."""
    try:
        return fn()
    except Exception as e:
        log('FAIL %s: %s' % (name, (str(e).splitlines() or [repr(e)])[0][:300]))


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


def get(path, timeout=5, base=BASE):
    with urllib.request.urlopen(base + path, timeout=timeout) as r:
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


def wait(cond, timeout, every=1.0):
    end = time.time() + timeout
    while time.time() < end:
        try:
            v = cond()
            if v:
                return v
        except Exception:
            pass
        time.sleep(every)
    return None


def alive():
    try:
        return json.loads(get('/api/ping', 2)[2]).get('app') == 'tdoc-translator'
    except Exception:
        return False


def phase():
    try:
        return api('/api/state')['phase']
    except Exception:
        return None


def procs():
    """Processes of the app: [(pid, ppid, name)] for the app, the launcher, the engine, the reading-aloud program."""
    out = []
    for line in sh('ps -A -o PID,PPID,NAME').splitlines()[1:]:
        p = line.split()
        if len(p) < 3:
            continue
        name = p[2].rsplit('/', 1)[-1]  # argv[0], with or without the folder
        if name == PKG or name.startswith(('libttranslator', 'libllama-server', 'libsherpa-onnx')):
            out.append((p[0], p[1], name))
    return out


def start_app():
    adb('shell', 'am', 'start', '-W', '-n', ACT, timeout=60)
    adb('forward', 'tcp:%d' % PORT, 'tcp:8765', check=True)
    return wait(alive, 90)


def meminfo():
    m = dict(re.findall(r'^(\w+):\s+(\d+) kB', sh('cat /proc/meminfo'), re.M))
    return 'MemTotal %.1f GB, MemAvailable %.1f GB' % (int(m.get('MemTotal', 0)) / 1e6, int(m.get('MemAvailable', 0)) / 1e6)


def engine_memory():
    eng = [x for x in procs() if x[2].startswith('libllama-server')]
    if not eng:
        return 'no engine process'
    st = dict(re.findall(r'^(\w+):\s+(\d+) kB', sh('cat /proc/%s/status' % eng[0][0]), re.M))
    return 'engine: VmRSS %.2f GB (RssAnon %.2f — its own memory, RssFile %.2f — the model file in memory)' % (
        int(st.get('VmRSS', 0)) / 1e6, int(st.get('RssAnon', 0)) / 1e6, int(st.get('RssFile', 0)) / 1e6)


def model_seen(name, timeout=15):
    return wait(lambda: any(m['id'] == 'file:' + name and m['present'] for m in api('/api/state')['models']), timeout)


def put_model(local, name):
    """Copies a model into the app's models folder as a computer does over USB (MTP). Android 11+ does not let adb
    (nor run-as) write into another app's Android/data folder; then as root (the emulator's images allow it)."""
    dest = EXT + '/models/' + name
    r = adb('push', local, dest, timeout=180)
    if r.returncode == 0 and model_seen(name):
        return 'adb push'
    info('adb push into Android/data: %s' % (r.stdout + r.stderr).decode(errors='replace').strip()[-160:])
    tmp = '/data/local/tmp/' + name
    if adb('push', local, tmp, timeout=180).returncode == 0:
        sh('chmod 644 ' + tmp)
        r = adb('shell', 'run-as', PKG, 'cp', tmp, dest, timeout=180)
        sh('rm -f ' + tmp)
        if r.returncode == 0 and model_seen(name):
            return 'run-as cp'
        info('run-as cp: %s' % (r.stdout + r.stderr).decode(errors='replace').strip()[-160:])
    r = adb('root', timeout=60)
    if r.returncode != 0:
        info('adb root: %s' % (r.stdout + r.stderr).decode(errors='replace').strip()[-160:])
        return None
    adb('wait-for-device', timeout=60)
    time.sleep(3)
    adb('forward', 'tcp:%d' % PORT, 'tcp:8765')  # adbd has restarted: the forward again
    if adb('push', local, dest, timeout=180).returncode == 0 and model_seen(name):
        return 'adb root, adb push'
    # straight into the storage behind /sdcard, owned and labelled as the folder
    lower = '/data/media/0/Android/data/%s/files/models' % PKG
    owner = sh('stat -c %%u:%%g %s' % lower).strip()
    label = sh('ls -dZ %s' % lower).split()[0] if sh('ls -dZ %s' % lower).strip() else ''
    if adb('push', local, lower + '/' + name, timeout=180).returncode == 0:
        sh('chown %s %s/%s; chmod 660 %s/%s' % (owner, lower, name, lower, name))
        if label:
            sh('chcon %s %s/%s' % (label, lower, name))
        if model_seen(name):
            return 'adb root, into /data/media'
    info('as root: %s' % sh('ls -lZ %s' % lower).strip()[-300:])
    return None


# ---------------------------------------------------------------- the DevTools protocol of the WebView

class Page:
    """The page in the app's WebView over the DevTools protocol: a minimal WebSocket client (RFC 6455)."""

    def __init__(self):
        pid = sh('pidof ' + PKG).strip()
        sock = 'webview_devtools_remote_' + pid
        if not wait(lambda: sock in sh('cat /proc/net/unix'), 30):
            raise RuntimeError('no DevTools socket ' + sock)
        adb('forward', 'tcp:%d' % CDP_PORT, 'localabstract:' + sock, check=True)
        def target():
            for t in json.loads(get('/json/list', 5, 'http://127.0.0.1:%d' % CDP_PORT)[2]):
                if t.get('type') == 'page' and t.get('url', '').startswith('http://127.0.0.1:8765'):
                    return t
        t = wait(target, 30)
        if not t:
            raise RuntimeError('the page of the launcher is not in the WebView')
        path = '/devtools/page/' + t['id']
        self.s = socket.create_connection(('127.0.0.1', CDP_PORT), timeout=60)
        key = base64.b64encode(os.urandom(16)).decode()
        self.s.sendall(('GET %s HTTP/1.1\r\nHost: 127.0.0.1:%d\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n'
                        'Sec-WebSocket-Key: %s\r\nSec-WebSocket-Version: 13\r\n\r\n' % (path, CDP_PORT, key)).encode())
        self.buf = b''
        while b'\r\n\r\n' not in self.buf:
            chunk = self.s.recv(4096)
            if not chunk:
                raise RuntimeError('DevTools: no handshake')
            self.buf += chunk
        head, self.buf = self.buf.split(b'\r\n\r\n', 1)
        if b' 101 ' not in head.split(b'\r\n')[0] + b' ':
            raise RuntimeError('DevTools: ' + head.decode(errors='replace')[:200])
        self.n = 0

    def _send(self, data):
        mask = os.urandom(4)
        n = len(data)
        if n < 126:
            head = bytes([0x81, 0x80 | n])
        elif n < 65536:
            head = bytes([0x81, 0x80 | 126]) + struct.pack('>H', n)
        else:
            head = bytes([0x81, 0x80 | 127]) + struct.pack('>Q', n)
        self.s.sendall(head + mask + bytes(b ^ mask[i % 4] for i, b in enumerate(data)))

    def _read(self, n):
        while len(self.buf) < n:
            chunk = self.s.recv(1 << 16)
            if not chunk:
                raise RuntimeError('DevTools: the connection is closed (the window was closed?)')
            self.buf += chunk
        out, self.buf = self.buf[:n], self.buf[n:]
        return out

    def _message(self):
        msg = b''
        while True:
            b0, b1 = self._read(2)
            n = b1 & 0x7f
            if n == 126:
                n = struct.unpack('>H', self._read(2))[0]
            elif n == 127:
                n = struct.unpack('>Q', self._read(8))[0]
            mask = self._read(4) if b1 & 0x80 else None
            data = self._read(n)
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            op = b0 & 0x0f
            if op == 0x8:
                raise RuntimeError('DevTools: closed by the page')
            if op in (0x0, 0x1, 0x2):
                msg += data
                if b0 & 0x80:
                    return msg.decode('utf-8', errors='replace')

    def call(self, method, params=None, timeout=60):
        self.n += 1
        mine = self.n
        self._send(json.dumps({'id': mine, 'method': method, 'params': params or {}}).encode())
        self.s.settimeout(timeout)
        while True:
            m = json.loads(self._message())
            if m.get('id') == mine:
                if 'error' in m:
                    raise RuntimeError('%s: %s' % (method, m['error']))
                return m.get('result', {})

    def js(self, expr, timeout=60):
        r = self.call('Runtime.evaluate', {'expression': expr, 'awaitPromise': True, 'returnByValue': True}, timeout)
        if r.get('exceptionDetails'):
            raise RuntimeError('in the page: ' + json.dumps(r['exceptionDetails'], ensure_ascii=False)[:300])
        return r.get('result', {}).get('value')

    def wait_js(self, expr, timeout):
        return wait(lambda: self.js(expr, 20), timeout, 0.5)

    def screenshot(self, name):
        p = os.path.join(OUT, name + '.png')
        with open(p, 'wb') as f:
            f.write(base64.b64decode(self.call('Page.captureScreenshot', {'format': 'png'})['data']))
        info('screenshot of the page %s' % os.path.basename(p))

    def close(self):
        try:
            self.s.close()
        except Exception:
            pass

    # what the user does (through the page's own elements and events)
    def visible(self, sel):
        return self.js("(() => { const e = document.querySelector(%s); return !!e && !e.hidden && "
                       "getComputedStyle(e).display !== 'none' && e.getClientRects().length > 0; })()" % json.dumps(sel))

    def click(self, sel):
        if not self.js("(() => { const e = document.querySelector(%s); if (!e) return false; e.click(); return true; })()" % json.dumps(sel)):
            raise RuntimeError('no element ' + sel)

    def fill(self, sel, text):
        self.js("(() => { const e = document.querySelector(%s); e.focus(); e.value = %s; e.dispatchEvent(new Event('input', {bubbles: true})); return true; })()"
                % (json.dumps(sel), json.dumps(text)))

    def select(self, sel, value):
        self.js("(() => { const e = document.querySelector(%s); e.value = %s; e.dispatchEvent(new Event('change', {bubbles: true})); return true; })()"
                % (json.dumps(sel), json.dumps(value)))

    def ready(self, timeout=120):
        """The page is loaded and the model is ready; JavaScript errors are collected from now on."""
        done = self.wait_js("document.readyState === 'complete' && document.body.dataset.model === 'ready'", timeout)
        self.js("window.__ttErrors = window.__ttErrors || []; if (!window.__ttErrHook) { window.__ttErrHook = 1; "
                "addEventListener('error', (e) => __ttErrors.push(String(e.message || e))); "
                "addEventListener('unhandledrejection', (e) => __ttErrors.push(String(e.reason))); } true")
        return done

    def start_work(self):
        if self.visible('#welcomeView'):
            self.click('#welcomeStart')
            time.sleep(0.8)

    def reload(self):
        self.call('Page.reload')
        time.sleep(1)


def translate(page, text, target=None, timeout=180):
    if target:
        page.select('#tgtSel', target)
    page.fill('#src', text)
    time.sleep(0.6)
    t0 = time.time()
    page.click('#goBtn')
    page.wait_js("document.querySelectorAll('.card').length > 0", timeout)
    page.wait_js("!document.querySelector('#goBtn').hidden", timeout)
    texts = page.js("Array.from(document.querySelectorAll('.card .card-text')).map((e) => e.innerText)") or []
    return texts, time.time() - t0


# ---------------------------------------------------------------- the parts of the check

STATE = {}


def check_device():
    info('Android %s (API %s), %s, ABI %s' % (sh('getprop ro.build.version.release').strip(), sh('getprop ro.build.version.sdk').strip(),
                                            sh('getprop ro.product.model').strip(), sh('getprop ro.product.cpu.abi').strip()))
    wv = re.search(r'Current WebView package \(name, version\): \((.*?)\)', sh('dumpsys webviewupdate'))
    info('WebView: ' + (wv.group(1) if wv else '?'))
    cpu = sh('cat /proc/cpuinfo')
    flags = re.search(r'^flags\s*:\s*(.*)$', cpu, re.M)
    info('CPU of the emulator: %d cores, %s' % (cpu.count('processor\t'), ' '.join(
        f for f in (flags.group(1).split() if flags else []) if f in ('sse4_2', 'avx', 'avx2', 'fma', 'f16c', 'avx512f', 'avx512_vnni', 'avx_vnni'))))
    info('memory of the emulator: ' + meminfo())


def check_start():
    r = adb('install', '-r', APK, timeout=300)
    ok(r.returncode == 0, 'the APK installs: ' + (r.stdout + r.stderr).decode(errors='replace').strip().splitlines()[-1])
    libdir = re.search(r'legacyNativeLibraryDir=(\S+)', sh('dumpsys package ' + PKG))
    info('library folder: %s' % (libdir.group(1) if libdir else '?'))
    t0 = time.time()
    if not ok(start_app(), 'the window starts the launcher from the app\'s library folder; it answers in %.1f s' % (time.time() - t0)):
        raise RuntimeError('the launcher does not answer')
    st = api('/api/state')
    ok(st['phase'] in ('setup', 'nomodel'), 'first start: phase %s (no model yet)' % st['phase'])
    ok(st['engine']['present'], 'the engine is found: llama-server in the library folder (config.json engine_path)')
    ok(st['tts']['engine']['present'], 'the reading-aloud program is found (tts.json)')
    info('machine: %s' % json.dumps(st.get('machine'), ensure_ascii=False))
    ok(st['models_dir'].startswith('/storage/emulated/0/Android/data/' + PKG), 'program folder on the shared storage: %s' % st['models_dir'])
    pr = procs()
    app_pid = [x[0] for x in pr if x[2] == PKG]
    launcher = [x for x in pr if x[2].startswith('libttranslator')]
    STATE['launcher'] = launcher
    ok(app_pid and launcher and launcher[0][1] == app_pid[0], 'the launcher is a child process of the app: %s' % pr)
    if not QUICK:
        def first_screen():
            page = Page()
            try:
                page.wait_js("document.readyState === 'complete' && ['setupView', 'mainView'].some((id) => !document.getElementById(id).hidden)", 60)
                time.sleep(1.5)
                shot('1-first-start')
            finally:
                page.close()
        step('the first-start screen', first_screen)
    else:
        time.sleep(4)
        shot('1-first-start')
        # an old WebView (the emulator images of Android 10 have WebView 74 of 2019, phones get updates from Google
        # Play): the page's script needs 80+, the app says so instead of showing a broken page
        wv = re.search(r'Current WebView package \(name, version\): \(.*?, (\d+)\.', sh('dumpsys webviewupdate'))
        if wv and int(wv.group(1)) < 80:
            sh('uiautomator dump /sdcard/tt-ui.xml')
            screen = sh('cat /sdcard/tt-ui.xml')
            ok('Android System WebView' in screen, 'WebView %s is too old for the page: the app asks to update it in Google Play' % wv.group(1))


def check_model_and_engine():
    how = put_model(MODEL, 'tiny-test.gguf')
    if how:
        ok(True, 'a model copied into Android/data/…/files/models (as a computer does over USB): %s; the launcher lists it as an own file' % how)
        code, _, body = post('/api/model', {'id': 'file:tiny-test.gguf'})
        ok(code == 200, 'model chosen (as in the menu of models): %d %s' % (code, body[:120]))
        t0 = time.time()
        st = wait(lambda: (lambda s: s if s['phase'] in ('ready', 'error') else None)(api('/api/state')), 240)
        ok(st and st['phase'] == 'ready', 'the engine started with the model in %.1f s: %s' % (time.time() - t0, st and (st['phase'], st.get('error'), st.get('engine_info'))))
        if st and st['phase'] != 'ready':
            info('engine log:\n' + (st.get('engine_log') or ''))
    else:
        info('the tiny model could not be copied into Android/data here (only the app itself and a computer over USB '
             'may write there): the checks go on with the real model of the catalog')
        if not load_real_model():
            raise RuntimeError('no model')
    pr = procs()
    eng = [x for x in pr if x[2].startswith('libllama-server')]
    launcher = STATE.get('launcher')
    ok(eng and launcher and eng[0][1] == launcher[0][0], 'the engine is a child process of the launcher: %s' % pr)
    t0 = time.time()
    code, ctype, body = post('/v1/chat/completions', {'messages': [{'role': 'user', 'content': 'Translate into German: Good morning!'}],
                                                      'max_tokens': 12, 'temperature': 0.2}, timeout=120)
    try:
        j = json.loads(body)
    except ValueError:
        j = {}
    ok(code == 200 and j.get('choices'), 'a reply of the engine through the launcher (%.1f s): %s' % (time.time() - t0, body[:160]))


def check_page():
    page = Page()
    try:
        ok(page.js("typeof ttwSaveFile === 'function' && typeof ttwOpenExternal === 'function' && typeof ttwClose === 'function'"),
           'the page has the window functions (ttwSaveFile, ttwOpenExternal, ttwClose): the app window of the computer version')
        info('page: %s' % page.js("JSON.stringify({width: innerWidth, height: innerHeight, pixelRatio: devicePixelRatio, secure: isSecureContext, "
                                  "clipboard: !!navigator.clipboard, ua: navigator.userAgent})"))
        ok(page.ready(), 'the page shows the model as ready')
        if page.visible('#welcomeView'):
            shot('2-welcome')
        page.start_work()
        shot('3-main-window')
        page.js('window.__ttTestMarker = 1')
        # a translation in the page, as the user does it
        texts, dt = translate(page, 'Good morning! The weather is nice today.')
        ok(texts, 'the page translated through the engine in %.1f s: %d variants (the first: %r)' % (dt, len(texts), (texts or [''])[0][:50]))
        time.sleep(0.5)
        page.screenshot('4-translation-page')
        shot('4-translation')
        # the copy button of a variant
        if page.js("!!document.querySelector('.card [data-act=copy]')"):
            page.click('.card [data-act=copy]')
            time.sleep(0.8)
            toast = page.js("(document.querySelector('.toast.show') || {}).textContent || ''")
            ok(toast, 'copy button: message %r' % toast)
        # the settings on a phone screen
        page.click('#settingsBtn')
        time.sleep(0.8)
        shot('5-settings')
        page.reload()
        ok(page.ready(60), 'the page loads again (reload)')
        # the Chinese interface: the fonts of the phone
        post('/api/settings', {'ui_language': 'zh'})
        page.reload()
        page.ready(60)
        page.start_work()
        page.fill('#src', '今天天气很好。我们去公园散步吧。')
        time.sleep(0.8)
        shot('6-chinese')
        fonts = page.js("getComputedStyle(document.body).fontFamily")
        ok('sans-serif' in fonts, 'Chinese interface, fonts: ' + fonts[:120])
        post('/api/settings', {'ui_language': 'en'})
        page.reload()
        page.ready(60)
        page.js('window.__ttTestMarker = 1')
        errors = page.js('window.__ttErrors || []')
        ok(not errors, 'no errors in the page: %s' % errors[:3])
    finally:
        page.close()


def check_tts():
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
    r = wait(voice_done, max(60, min(600, time_left() - 600)), 2)
    ok(r == 'ok', 'voice en-ljspeech (67 MB) downloaded from github.com and unpacked by the launcher in %.0f s: %s' % (time.time() - t0, r))
    if r != 'ok':
        return
    t0 = time.time()
    code, ctype, body = post('/api/tts', {'lang': 'en', 'text': 'Hello! This is Ttranslator on Android.', 'speed': 1}, timeout=90)
    ok(code == 200 and body[:4] == b'RIFF', 'read aloud (sherpa-onnx from the library folder): %d %s, %d bytes, %.1f s'
       % (code, ctype, len(body), time.time() - t0))
    if body[:4] == b'RIFF':
        with open(os.path.join(OUT, 'tts-en.wav'), 'wb') as f:
            f.write(body)
    else:
        info('reply: %s' % body[:300])


def check_background():
    adb('shell', 'input', 'keyevent', 'KEYCODE_HOME')
    time.sleep(30)
    ok(alive(), 'after 30 s in the background the launcher still answers')
    ok(phase() == 'ready', 'after 30 s in the background the model is still loaded')
    adb('shell', 'am', 'start', '-W', '-n', ACT, timeout=60)
    time.sleep(2)
    def back():
        page = Page()
        try:
            ok(page.js('window.__ttTestMarker') == 1, 'back in front: the same page, not reloaded (the text stays)')
        finally:
            page.close()
    step('back in front, the page', back)


def check_killed():
    adb('shell', 'input', 'keyevent', 'KEYCODE_HOME')
    time.sleep(2)
    adb('shell', 'am', 'kill', PKG)
    time.sleep(3)
    left = procs()
    if any(x[2] == PKG for x in left):
        info('am kill did not end the app: force-stop')
        adb('shell', 'am', 'force-stop', PKG)
        time.sleep(3)
        left = procs()
    ok(not left, 'Android ended the app in the background: the launcher and the engine ended with it: %s' % left)
    ok(start_app(), 'started again')
    ok(wait(lambda: phase() == 'ready', 240), 'the model is loaded again at start')


def check_exit():
    by_page = []
    def through_page():
        page = Page()
        try:
            page.ready(60)
            page.start_work()
            shot('7-before-exit')
            page.click('#quitBtn')
            time.sleep(0.5)
            page.click('#quitBtn')
            by_page.append(1)
        finally:
            page.close()
    if not QUICK:
        step('Exit through the page', through_page)
    if not by_page:
        post('/api/quit', {})
    ok(wait(lambda: not alive() and not [x for x in procs() if x[2] != PKG], 30), 'Exit: the launcher and the engine have ended: %s' % procs())
    if by_page:
        time.sleep(2)
        top = sh('dumpsys activity activities | grep -E "mResumedActivity|topResumedActivity"')
        ok(PKG not in top, 'Exit closed the window: %s' % top.strip()[:160])


def load_real_model():
    """The model of the catalog for real: the launcher downloads Gemma 4 E2B · Q4_0 (3.35 GB) from Hugging Face inside
    the emulator (unless it is there already), checks its size and SHA-256 and loads it."""
    info('real model: before: ' + meminfo())
    t0 = time.time()
    present = any(m['id'] == 'g4-e2b' and m['present'] for m in api('/api/state')['models'])
    code, _, body = post('/api/model', {'id': 'g4-e2b'})
    ok(code == 200, 'real model: Gemma 4 E2B · Q4_0 chosen in the menu of models%s: %d %s'
       % ('' if present else ', its download started', code, body[:100]))
    last = [0]
    def ready():
        s = api('/api/state')
        d = s.get('download') or {}
        if d.get('active') and time.time() - last[0] > 60:
            last[0] = time.time()
            info('real model: downloading %.2f of %.2f GB, %.1f MB/s' % (d.get('done', 0) / 1e9, (d.get('total') or 0) / 1e9, (d.get('speed') or 0) / 1e6))
        if s['phase'] == 'ready':
            return s
        if s['phase'] in ('error', 'setup') and not d.get('active') and (d.get('error') or s.get('error')):
            return s
    s = wait(ready, max(60, min(1500, time_left() - 420)), 3)
    ok(s and s['phase'] == 'ready', 'real model: %s and loaded in %.0f s: %s'
       % ('already downloaded' if present else 'downloaded from Hugging Face (size and SHA-256 checked by the launcher)', time.time() - t0,
          s and (s['phase'], (s.get('download') or {}).get('error'), s.get('error'), s.get('engine_info'))))
    if s and s['phase'] == 'ready':
        STATE['real'] = True
        info('real model: after loading: ' + meminfo() + '; ' + engine_memory())
        return True
    return False


def real_model():
    """The real model: a translation into Russian over HTTP and in the page; the memory the engine takes on Android."""
    ok(start_app(), 'real model: the app started again')
    if not load_real_model():
        return
    t0 = time.time()
    code, _, body = post('/v1/chat/completions', {'messages': [{'role': 'user', 'content':
        'Translate the text into Russian. Reply with the translation only.\n\nThe weather is nice today, so we are going for a walk in the park.'}],
        'max_tokens': 60, 'temperature': 0.2}, timeout=600)
    try:
        j = json.loads(body)
        text = j['choices'][0]['message']['content']
    except (ValueError, KeyError, IndexError):
        j, text = {}, ''
    ok(code == 200 and re.search('[а-яё]', text.lower()), 'real model: a translation into Russian (%.1f s): %r' % (time.time() - t0, text[:120]))
    if j.get('timings'):
        info('real model: prompt %d tokens at %.1f t/s, generation %d tokens at %.1f t/s (the emulator\'s x86 processor, not a phone)'
             % (j['timings'].get('prompt_n', 0), j['timings'].get('prompt_per_second', 0), j['timings'].get('predicted_n', 0), j['timings'].get('predicted_per_second', 0)))
    def in_page():
        page = Page()
        try:
            page.ready(120)
            page.start_work()
            texts, dt = translate(page, 'Science is a way of thinking much more than it is a body of knowledge.', 'ru',
                                  max(60, min(900, time_left() - 180)))
            ok(any(re.search('[а-яё]', x.lower()) for x in texts), 'real model: the page translated into Russian in %.0f s: %r' % (dt, texts[:3]))
            time.sleep(0.5)
            shot('8-real-model-translation')
            page.screenshot('8-real-model-translation-page')
            info('real model: after translating: ' + meminfo() + '; ' + engine_memory())
        finally:
            page.close()
    step('real model, the page', in_page)
    post('/api/quit', {})
    ok(wait(lambda: not alive(), 30), 'real model: Exit')


# ---------------------------------------------------------------- the check

try:
    step('the device', check_device)
    step('install and start', check_start)
    if not alive():
        raise RuntimeError('the app does not start: the other checks are pointless')
    step('model and engine', check_model_and_engine)
    if not QUICK:
        step('the page', check_page)
        step('reading aloud', check_tts)
        step('in the background', check_background)
        step('the app ended by Android', check_killed)
    step('Exit', check_exit)
    if REAL:
        if time_left() > 900:
            step('real model', real_model)
        else:
            info('real model: skipped, only %d s left for the CI job' % time_left())
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
