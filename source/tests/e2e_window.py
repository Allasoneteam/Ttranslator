# v0.9.1: the own window (launch_mode "window") with the real program ttranslator-window-linux on WebKitGTK.
# Runs under a virtual screen (xvfb-run); the launcher is started without --no-window, as on a real computer.
#   - the window program starts, its page connects with ttw=1 (it has the functions of the own window);
#   - closing the window (the program ends) lets the launcher exit after a few seconds;
#   - «Выход» in the program closes the window;
#   - without the window program: an Edge/Chrome window instead, and the reason in the state for the settings.
# Usage: e2e_window.py <work> <launcher binary> <window program> <engine url> <models.json> <port>
import sys, os, json, time, shutil, subprocess, urllib.request, signal
W, LAUNCHER, HELPER, ENGINE_URL, MODELS, PORT = sys.argv[1:7]
URL = 'http://127.0.0.1:%s/' % PORT
res = []
def ok(c, m): res.append(('OK  ' if c else 'FAIL') + ' ' + m); print(res[-1], flush=True)
def get(path):
    return json.load(urllib.request.urlopen(URL.rstrip('/') + path, timeout=5))
def post(path, body=None):
    req = urllib.request.Request(URL.rstrip('/') + path, data=json.dumps(body or {}).encode(), headers={'Content-Type': 'application/json', 'Origin': URL.rstrip('/')})
    return json.load(urllib.request.urlopen(req, timeout=10))
def wait(cond, secs):
    end = time.time() + secs
    while time.time() < end:
        try:
            if cond(): return True
        except Exception: pass
        time.sleep(0.3)
    return False
def helpers():   # running window programs: by the program file of the process, not by command lines
    found = []
    for d in os.listdir('/proc'):
        if not d.isdigit(): continue
        try:
            if os.path.basename(os.readlink('/proc/%s/exe' % d)) == 'ttranslator-window-linux': found.append(d)
        except OSError: pass
    return found

def start(root, with_helper):
    shutil.rmtree(root, ignore_errors=True)
    os.makedirs(os.path.join(root, 'ui'))
    shutil.copy(LAUNCHER, os.path.join(root, 'ttranslator'))
    if with_helper:
        shutil.copy(HELPER, os.path.join(root, 'ttranslator-window-linux'))
    app = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for f in ('index.html', 'tests.txt'):
        shutil.copy(os.path.join(app, 'ui', f), os.path.join(root, 'ui', f))
    cfg = {'active_model': 'q4', 'ui_language': 'ru', 'launch_mode': 'window', 'show_welcome': False, 'load_model_at_start': False, 'open_window': True}
    json.dump(cfg, open(os.path.join(root, 'config.json'), 'w'))
    env = dict(os.environ, TDOC_ENGINE_URL=ENGINE_URL, TDOC_TEST_MODELS=MODELS,
               WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS='1')   # a container without user namespaces
    log = open(os.path.join(W, 'launcher-window.log'), 'a')
    p = subprocess.Popen([os.path.join(root, 'ttranslator'), '--port', PORT], cwd=root, env=env, stdout=log, stderr=log)
    wait(lambda: get('/api/ping')['app'] == 'tdoc-translator', 10)
    return p

def shot(name):
    subprocess.run(['import', '-window', 'root', os.path.join(W, 'shots', name)], capture_output=True)

os.makedirs(os.path.join(W, 'shots'), exist_ok=True)
for p in helpers(): os.kill(int(p), signal.SIGTERM)

# ================= the own window opens and its page connects
root = os.path.join(W, 'rwin')
p = start(root, True)
ok(wait(lambda: get('/api/state')['window']['pages'] == 1, 40), 'the page connected inside the own window (ttw=1): %s' % get('/api/state').get('window'))
st = get('/api/state')['window']
ok(st['available'] is True and st['error'] == '' and len(helpers()) == 1, 'state: available, no error, one window program: %s' % st)
logtext = open(os.path.join(root, 'data', 'logs', 'launcher.log'), encoding='utf-8').read()
ok('own window opened (ttranslator-window-linux)' in logtext and 'page connected in the own window' in logtext, 'the log tells about the own window')
ok(os.path.exists(os.path.join(root, 'data', 'webview', 'ttranslator.png')), 'the window icon is in data/webview')
time.sleep(1.5); shot('v091-window.png')

# ================= closing the window: the launcher exits soon (no 20-second wait)
for h in helpers(): os.kill(int(h), signal.SIGTERM)
t0 = time.time()
try: p.wait(20); code = p.returncode
except subprocess.TimeoutExpired: code = None
ok(code == 0 and time.time() - t0 < 12, 'after the window is closed the launcher exits in %.1f s (code %s)' % (time.time() - t0, code))

# ================= «Выход»: the launcher closes its window
p = start(root, True)
ok(wait(lambda: get('/api/state')['window']['pages'] == 1, 40), 'second start: the page is in the own window again')
post('/api/quit')
try: p.wait(10); code = p.returncode
except subprocess.TimeoutExpired: code = None
ok(code == 0 and wait(lambda: not helpers(), 10), 'Exit: the launcher has ended and the window is closed (%s, %s)' % (code, helpers()))

# ================= no window program: the usual window instead, the reason for the settings
p = start(os.path.join(W, 'rwin2'), False)
ok(wait(lambda: 'нет программы окна ttranslator-window-linux' in get('/api/state')['window']['error'], 15),
   'without the window program: the reason is in the state: %s' % get('/api/state')['window'])
ok(get('/api/state')['window']['available'] is False, 'not available without the window program')
try: post('/api/quit'); p.wait(10)
except Exception: p.kill()

print('FAILS:', sum(1 for x in res if x.startswith('FAIL')), 'of', len(res))
