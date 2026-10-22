# v0.9.1: the functions of the own window program (ttranslator-window-linux, WebKitGTK) for the page, tested with
# a page of our own (fixture written for the test) served on 127.0.0.1:
#   window.TTW; ttwOpenExternal (a stand-in default browser records the address); navigation to another site is
#   not shown inside the window but goes to the browser; a link with target=_blank too; ttwSaveFile (the "Save as"
#   dialog of GTK is confirmed with the Enter key through xdotool) writes the text byte for byte; a cancelled
#   dialog; ttwClose ends the program with code 0.
# Runs under a virtual screen (xvfb-run), needs xdotool.
# Usage: window_functions.py <work> <window program> <port>
import sys, os, json, time, shutil, subprocess, threading, http.server
W, HELPER, PORT = sys.argv[1], sys.argv[2], int(sys.argv[3])
res = []
def ok(c, m): res.append(('OK  ' if c else 'FAIL') + ' ' + m); print(res[-1], flush=True)

home = os.path.join(W, 'wf-home')
shutil.rmtree(home, ignore_errors=True)
for d in ('Downloads', '.config', '.local/share/applications', 'bin'):
    os.makedirs(os.path.join(home, d), exist_ok=True)
opened = os.path.join(home, 'opened.txt')
# a stand-in default browser and mail program: writes the address it got
browser = os.path.join(home, 'bin', 'fake-browser')
open(browser, 'w').write('#!/bin/sh\necho "$1" >> "%s"\n' % opened)
os.chmod(browser, 0o755)
open(os.path.join(home, '.local/share/applications', 'fake-browser.desktop'), 'w').write(
    '[Desktop Entry]\nType=Application\nName=Fake browser\nExec=%s %%u\nMimeType=x-scheme-handler/http;x-scheme-handler/https;x-scheme-handler/mailto;\n' % browser)
open(os.path.join(home, '.config', 'mimeapps.list'), 'w').write(
    '[Default Applications]\nx-scheme-handler/http=fake-browser.desktop\nx-scheme-handler/https=fake-browser.desktop\nx-scheme-handler/mailto=fake-browser.desktop\n')
open(os.path.join(home, '.config', 'user-dirs.dirs'), 'w').write('XDG_DOWNLOAD_DIR="$HOME/Downloads"\n')

TEXT = '﻿Термин\tTerm\r\n«кавычки» "quotes" \\ back\\slash\ttab\r\n😀 emoji   line separator\r\n'
results = {}
got = threading.Event()
PAGE = '''<!doctype html><meta charset="utf-8"><title>ttw test</title>
<a id="blank" href="https://example.org/blank" target="_blank">blank</a>
<script>
const report = (k, v) => fetch('/result', { method: 'POST', body: JSON.stringify({ k, v }) });
(async () => {
  await report('ttw', { TTW: window.TTW || null, fns: ['ttwOpenExternal', 'ttwSaveFile', 'ttwClose'].map(f => typeof window[f]) });
  try { await report('ext', await window.ttwOpenExternal('https://example.com/a?b=1')); } catch (e) { await report('ext', 'error: ' + e); }
  try { await window.ttwOpenExternal('file:///etc/passwd'); await report('file', 'opened'); } catch (e) { await report('file', String(e)); }
  document.getElementById('blank').click();
  await new Promise(r => setTimeout(r, 400));
  location.href = 'https://example.net/away';
  await new Promise(r => setTimeout(r, 800));
  await report('stayed', location.href);
  await report('saving', 1);
  try { await report('save', await window.ttwSaveFile('Мой словарь.tsv', TEXT, 'tsv', 'Сохранить файл', 'Таблица словаря')); } catch (e) { await report('save', 'error: ' + e); }
  await report('saving2', 1);
  try { await report('cancel', await window.ttwSaveFile('x.txt', 'x', 'txt', 'Save', 'Text')); } catch (e) { await report('cancel', 'error: ' + e); }
  await report('closing', 1);
  await window.ttwClose();
})();
</script>'''.replace('TEXT', json.dumps(TEXT))

class H(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        b = PAGE.encode()
        self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8'); self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)
    def do_POST(self):
        n = int(self.headers.get('Content-Length', 0)); j = json.loads(self.rfile.read(n))
        results[j['k']] = j['v']; got.set()
        self.send_response(204); self.end_headers()
srv = http.server.ThreadingHTTPServer(('127.0.0.1', PORT), H)
threading.Thread(target=srv.serve_forever, daemon=True).start()

def wait_key(k, secs):
    end = time.time() + secs
    while time.time() < end:
        if k in results: return True
        time.sleep(0.2)
    return False
def dialog_key(key):   # the GTK "Save" dialog: wait for it, then press a key in it
    for i in range(50):
        r = subprocess.run(['xdotool', 'search', '--name', '^(Сохранить файл|Save)$'], capture_output=True, text=True)
        ids = r.stdout.split()
        if ids:
            time.sleep(0.7)   # no window manager here: give the dialog the keyboard focus, then a real key press
            subprocess.run(['xdotool', 'windowfocus', '--sync', ids[-1]], capture_output=True)
            subprocess.run(['xdotool', 'key', key], capture_output=True)
            return True
        time.sleep(0.2)
    return False

env = dict(os.environ, HOME=home, XDG_CONFIG_HOME=os.path.join(home, '.config'), XDG_DATA_HOME=os.path.join(home, '.local/share'),
           PATH=os.path.join(home, 'bin') + ':' + os.environ['PATH'], WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS='1', GTK_USE_PORTAL='0')
err = open(os.path.join(W, 'window-functions.err'), 'w')
p = subprocess.Popen([HELPER, 'http://127.0.0.1:%d/' % PORT, '--size', '900x600'], env=env, stdout=subprocess.PIPE, stderr=err, text=True)
ready = p.stdout.readline().strip()
ok(ready == 'ready', 'the program says ready: %r' % ready)
ok(wait_key('ttw', 30) and results['ttw'] == {'TTW': {'version': 1}, 'fns': ['function', 'function', 'function']}, 'window.TTW and the three functions: %s' % results.get('ttw'))
ok(wait_key('ext', 10) and results['ext'] is True, 'ttwOpenExternal resolves: %s' % results.get('ext'))
ok(wait_key('file', 10) and 'only http, https and mailto' in str(results['file']), 'ttwOpenExternal refuses file: addresses: %s' % results.get('file'))
ok(wait_key('stayed', 15) and results['stayed'] == 'http://127.0.0.1:%d/' % PORT, 'navigation to another site does not leave the page: %s' % results.get('stayed'))
time.sleep(1)
seen = open(opened).read().split() if os.path.exists(opened) else []
ok(seen == ['https://example.com/a?b=1', 'https://example.org/blank', 'https://example.net/away'], 'the default browser got the external addresses: %s' % seen)
ok(wait_key('saving', 10) and dialog_key('Return'), 'the "Save as" dialog appeared, Enter pressed')
want = os.path.join(home, 'Downloads', 'Мой словарь.tsv')
ok(wait_key('save', 20) and results['save'] == {'path': want}, 'ttwSaveFile resolves with the path: %s' % results.get('save'))
data = open(want, 'rb').read() if os.path.exists(want) else b''
ok(data == TEXT.encode('utf-8'), 'the file holds the text byte for byte (%d bytes)' % len(data))
ok(wait_key('saving2', 10) and dialog_key('Escape'), 'second dialog: Escape')
ok(wait_key('cancel', 20) and results['cancel'] == {'cancelled': True}, 'a cancelled dialog: %s' % results.get('cancel'))
ok(wait_key('closing', 10), 'the page asks to close the window')
try: code = p.wait(15)
except subprocess.TimeoutExpired: p.kill(); code = None
ok(code == 0, 'ttwClose ends the program with code 0: %s' % code)
srv.shutdown()
print('FAILS:', sum(1 for x in res if x.startswith('FAIL')), 'of', len(res))
