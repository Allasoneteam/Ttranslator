# Release archives (source/release.sh): what is inside, and the Linux archive starts without downloading the engine.
#   - Windows zip and Linux tar.gz: one folder Ttranslator/ with the programs (the same bytes as built), ui/,
#     README.txt, LICENSE.txt, THIRD-PARTY.txt, start.bat / start.sh, source/, the engine unpacked in
#     engine/<os>-amd64/<version>/ and engine.json pointing at llama-server; no user data (config.json, data/,
#     models/), no build leftovers (ui_fallback, __pycache__); executable bits in the tar.gz; SHA256SUMS.txt right;
#   - the Linux archive unpacked into a fresh folder: the launcher sees the engine at once (engine present before any
#     download), the first-start download fetches only the model (the engine address is a dead one), the engine
#     starts with it (phase "ready").
# Usage: release_check.py <work> <dist-dir> <bin-dir> <models.json> <port>
import hashlib, io, json, os, shutil, subprocess, sys, tarfile, time, urllib.request, zipfile
W, DIST, BIN, MODELS, PORT = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5])
res = []
def ok(c, m): res.append(('OK  ' if c else 'FAIL') + ' ' + m); print(res[-1], flush=True)
def sha(b): return hashlib.sha256(b).hexdigest()

names = sorted(os.listdir(DIST))
wz = [n for n in names if n.endswith('-windows-x64.zip')]
lt = [n for n in names if n.endswith('-linux-x64.tar.gz')]
ok(len(wz) == 1 and len(lt) == 1 and 'SHA256SUMS.txt' in names, 'archives: %s' % names)
sums = dict(reversed(l.split()) for l in open(os.path.join(DIST, 'SHA256SUMS.txt')) if l.strip())
for n in wz + lt:
    ok(sums.get(n) == sha(open(os.path.join(DIST, n), 'rb').read()), 'SHA256SUMS.txt: %s' % n)

def check(files, read, isexec, plat, progs, server_name, start):
    top = {f.split('/')[1] for f in files if f.count('/') >= 1}
    ok(all(f.startswith('Ttranslator/') for f in files), '%s: one folder Ttranslator/' % plat)
    need = progs + [start, 'README.txt', 'LICENSE.txt', 'THIRD-PARTY.txt', 'ui/index.html', 'ui/tests.txt',
                    'source/launcher/main.go', 'source/docs/CHANGELOG.md', 'engine/%s/engine.json' % plat]
    missing = [x for x in need if 'Ttranslator/' + x not in files]
    ok(not missing, '%s: everything inside (missing: %s)' % (plat, missing))
    bad = [f for f in files if any(s in f for s in ('/config.json', '/data/', '/models/', 'ui_fallback', '__pycache__', '.part'))]
    ok(not bad, '%s: no user data or build leftovers: %s' % (plat, bad[:5]))
    for p, built in zip(progs, [os.path.join(BIN, x) for x in progs]):
        ok(read('Ttranslator/' + p) == open(built, 'rb').read(), '%s: %s — the same bytes as built' % (plat, p))
    meta = json.loads(read('Ttranslator/engine/%s/engine.json' % plat))
    server = 'Ttranslator/engine/%s/%s' % (plat, meta.get('server', ''))
    ok(meta.get('server', '').endswith('/' + server_name) and server in files, '%s: engine.json → %s' % (plat, meta))
    if isexec:
        ok(all(isexec(x) for x in ['Ttranslator/' + p for p in progs] + ['Ttranslator/' + start, server]), '%s: programs are executable' % plat)
    tp = read('Ttranslator/THIRD-PARTY.txt').decode('utf-8')
    ok('llama.cpp' in tp and 'webview' in tp and 'WebView2' in tp and 'sherpa-onnx' in tp and '\r\n' in tp, '%s: THIRD-PARTY.txt names the components' % plat)
    # the MIT licences need their text in every copy: llama.cpp (its Windows archive has no LICENSE file) and webview
    ok(tp.count('MIT License') >= 2 and 'The ggml authors' in tp and 'Serge Zaitsev' in tp, '%s: the licence texts of llama.cpp and webview are in THIRD-PARTY.txt' % plat)

if wz:
    z = zipfile.ZipFile(os.path.join(DIST, wz[0]))
    files = [i.filename for i in z.infolist() if not i.is_dir()]
    check(files, z.read, None, 'windows-amd64', ['Ttranslator.exe', 'ttranslator-window.exe'], 'llama-server.exe', 'start.bat')
if lt:
    t = tarfile.open(os.path.join(DIST, lt[0]))
    mem = {m.name: m for m in t.getmembers()}
    files = [n for n, m in mem.items() if m.isfile() or m.issym()]
    check(files, lambda n: t.extractfile(mem[n]).read(), lambda n: bool(mem[n].mode & 0o111), 'linux-amd64',
          ['ttranslator-linux', 'ttranslator-window-linux'], 'llama-server', 'start.sh')

    # ================= the Linux archive in a fresh folder: no engine download
    root = os.path.join(W, 'release-run')
    shutil.rmtree(root, ignore_errors=True); os.makedirs(root)
    t.extractall(root, filter='data') if sys.version_info >= (3, 12) else t.extractall(root)
    app = os.path.join(root, 'Ttranslator')
    log = open(os.path.join(W, 'release-run.log'), 'w')
    env = dict(os.environ, TDOC_ENGINE_URL='http://127.0.0.1:9/no-engine-here.tar.gz', TDOC_TEST_MODELS=MODELS)
    p = subprocess.Popen(['./ttranslator-linux', '--no-window', '--port', str(PORT)], cwd=app, env=env, stdout=log, stderr=subprocess.STDOUT)
    URL = 'http://127.0.0.1:%d' % PORT
    def state(): return json.load(urllib.request.urlopen(URL + '/api/state', timeout=10))
    st = None
    for _ in range(100):
        try: st = state(); break
        except Exception: time.sleep(0.2)
    ok(st is not None and st['engine'].get('present') is True, 'the engine of the archive is found at once: %s' % (st and st.get('engine')))
    urllib.request.urlopen(urllib.request.Request(URL + '/api/setup', data=b'', method='POST', headers={'Origin': URL}), timeout=10)
    phase = ''
    for _ in range(240):
        st = state(); phase = st['phase']
        if phase in ('ready', 'error'): break
        time.sleep(0.5)
    ok(phase == 'ready', 'first start: only the model is downloaded, the engine starts (phase %s, %s)' % (phase, st.get('error', '')))
    ok(not os.path.exists(os.path.join(app, 'engine', 'linux-amd64', 'no-engine-here.tar.gz')), 'no engine download was tried')
    try: urllib.request.urlopen(urllib.request.Request(URL + '/api/quit', data=b'', method='POST', headers={'Origin': URL}), timeout=10)
    except Exception: pass
    try: p.wait(15)
    except subprocess.TimeoutExpired: p.kill()

fails = [r for r in res if r.startswith('FAIL')]
print('\nFAILS: %d of %d' % (len(fails), len(res)))
