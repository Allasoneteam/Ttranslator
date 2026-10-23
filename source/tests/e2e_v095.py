# End-to-end test for v0.9.5:
#   1) «Пропустить» on the first-start screen: the main window without a model (body[data-model="nomodel"]), the
#      banner «Модель не выбрана», the model menu opens by itself, nothing is downloaded, config.json keeps the choice
#      across a restart; choosing a model in the menu downloads the engine and the model (cancel → back to the main
#      window with the reason), then the model works and the choice is forgotten;
#   2) voices copied from another computer into models/voices without the speech program: 🔊 says what is missing,
#      the model menu offers only the program (from, to, file; how to copy it without internet), the voice is not
#      downloaded again, and reading aloud works — even before any translation model is there;
#   3) a sherpa-onnx folder copied by hand (no tts.json) is found; a folder copied half way is not; a program that
#      lost its execute permission gets it back.
# Launcher + real sherpa-onnx + a real Piper voice from the local mirror; stand-in models.
# Usage: e2e_v095.py <work> <ui_url> <root> <engine_url> <models.json> <tts_url> <voices.json>
#   (a launcher in a fresh folder BEFORE the first run, started with TDOC_TTS_URL and TDOC_TEST_VOICES; the test
#   restarts it itself with the same addresses and test catalogues, and closes it at the end)
import glob, json, os, subprocess, sys, tarfile, time, urllib.error, urllib.request
from playwright.sync_api import sync_playwright
S, URL, ROOT, ENGINE_URL, MODELS, TTS_URL, VOICES = sys.argv[1:8]
BASE = URL.rstrip('/')
PORT = BASE.rsplit(':', 1)[1]
ENG = os.path.join(ROOT, 'engine', 'linux-amd64')
VDIR = os.path.join(ROOT, 'models', 'voices')
TTS_DIR = os.path.basename(TTS_URL).replace('.tar.bz2', '')
shots = os.path.join(S, 'shots', 'v095'); os.makedirs(shots, exist_ok=True)
res = []
def ok(c, m): res.append(('OK  ' if c else 'FAIL') + ' ' + m); print(res[-1], flush=True)
def state():
    return json.load(urllib.request.urlopen(BASE + '/api/state', timeout=5))
def post(path, body=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body or {}).encode(), method='POST',
                                 headers={'Content-Type': 'application/json', 'Origin': BASE})
    return json.load(urllib.request.urlopen(req, timeout=10))
def tts(text, lang='en'):
    req = urllib.request.Request(BASE + '/api/tts', data=json.dumps({'lang': lang, 'text': text}).encode(), method='POST',
                                 headers={'Content-Type': 'application/json', 'Origin': BASE})
    try:
        r = urllib.request.urlopen(req, timeout=120)
        return r.status, r.headers.get('Content-Type', ''), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get('Content-Type', ''), e.read()
def cfg():
    return json.load(open(os.path.join(ROOT, 'config.json'), encoding='utf-8'))
def alive():
    try:
        urllib.request.urlopen(BASE + '/api/ping', timeout=1); return True
    except Exception:
        return False
def wait(pred, t=10):
    end = time.time() + t
    while time.time() < end:
        try:
            if pred(): return True
        except Exception:
            pass
        time.sleep(0.2)
    return False
def log_text():
    try: return open(os.path.join(ROOT, 'data', 'logs', 'launcher.log'), encoding='utf-8', errors='replace').read()
    except OSError: return ''

procs = []
def restart():
    # the running launcher exits, a new one starts in the same folder with the same addresses and test catalogues;
    # an event stream keeps it running between browser windows (as run_all.sh does)
    try: post('/api/quit')
    except Exception: pass
    if not wait(lambda: not alive(), 20): return False
    lf = open(os.path.join(S, 'launcher-v095.log'), 'a')
    env = dict(os.environ, TDOC_ENGINE_URL=ENGINE_URL, TDOC_TEST_MODELS=MODELS, TDOC_TTS_URL=TTS_URL, TDOC_TEST_VOICES=VOICES)
    procs.append(subprocess.Popen(['./ttranslator', '--no-window', '--port', PORT], cwd=ROOT, env=env, stdout=lf, stderr=lf))
    if not wait(alive, 15): return False
    procs.append(subprocess.Popen(['curl', '-s', '-N', BASE + '/api/events'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    return True

errs = []
try:
  with sync_playwright() as pw:
    b = pw.chromium.launch()
    def window(welcome=False):
        ctx = b.new_context(viewport={'width': 1180, 'height': 860}, locale='ru-RU')
        ctx.add_init_script("window.close = () => {};")
        if not welcome:
            ctx.add_init_script("try { sessionStorage.setItem('tdoc.window', '1'); sessionStorage.setItem('tdoc.welcome', 'done') } catch (e) {}")
        page = ctx.new_page()
        page.on('pageerror', lambda e: errs.append(str(e)))
        page.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'status of 4' not in m.text else None)
        return ctx, page
    def toast(page): return page.inner_text('#toast')
    def open_menu(page):
        if page.is_hidden('#modelMenu'): page.click('#modelBtn')
        page.wait_for_selector('#modelMenu:not([hidden])')
    def close_menu(page):
        page.click('header .brand'); page.wait_for_timeout(150)
    def row(page, label):
        return page.locator('#modelMenu .mitem', has=page.locator('.title', has_text=label))

    # ================= 1. the first-start screen: «Пропустить»
    ctx, page = window()
    page.goto(URL); page.wait_for_selector('#setupView:not([hidden])', timeout=15000)
    skip = page.locator('#setupSkipBtn')
    ok(page.evaluate('document.body.dataset.model') == 'setup' and skip.is_visible() and skip.inner_text() == 'Пропустить'
       and 'без модели' in (skip.get_attribute('title') or '') and page.is_visible('#dlBtn'),
       'first start: «Скачать» and «Пропустить» (%s)' % skip.get_attribute('title'))
    page.screenshot(path=os.path.join(shots, '1-first-start.png'))
    skip.click()
    page.wait_for_selector('body[data-model="nomodel"]', timeout=10000)
    page.wait_for_selector('#modelMenu:not([hidden])', timeout=5000)
    ok(page.is_visible('#mainView') and page.is_hidden('#setupView'), 'after «Пропустить»: the main window, the model menu opens by itself')
    st = state()
    ok(st['phase'] == 'nomodel' and not st['download']['active'] and not st['engine']['present'], 'phase nomodel, nothing is being downloaded: %s' % st['download'])
    ok(cfg().get('setup_skipped') is True, 'config.json: setup_skipped')
    ok(not glob.glob(os.path.join(ROOT, 'models', '*.gguf*')) and not glob.glob(os.path.join(ENG, '*')), 'nothing downloaded: %s' % os.listdir(ENG))
    menu = page.inner_text('#modelMenu')
    ok(page.locator('#modelMenu .mitem.active').count() == 0 and '✓' not in menu and 'работает сейчас' not in menu and menu.count('нужно скачать') >= 2,
       'model menu: no model marked as working, the models are to be downloaded')
    page.screenshot(path=os.path.join(shots, '2-nomodel-menu.png'))
    close_menu(page)
    banner = page.inner_text('#bnNoModel')
    ok(page.is_hidden('#modelMenu') and page.is_visible('#bnNoModel') and 'Модель не выбрана.' in banner and 'Выберите модель в меню моделей' in banner
       and 'Не получилось' not in banner, 'banner: ' + banner.replace('\n', ' | '))
    ok(page.inner_text('#modelName') == 'Выбрать модель' and page.inner_text('#engineInfo') == 'модель не выбрана' and page.is_hidden('#unloadBtn'),
       'header: «%s», «%s», no ⏏' % (page.inner_text('#modelName'), page.inner_text('#engineInfo')))
    page.fill('#src', 'The laser pulse is short.'); page.wait_for_timeout(300)
    page.click('#goBtn'); page.wait_for_timeout(300)
    ok(toast(page) == 'Please load a model.' and page.locator('#cards .card').count() == 0, '«Перевести» without a model: ' + toast(page))
    page.screenshot(path=os.path.join(shots, '3-nomodel-window.png'))
    page.click('#noModelBtn'); page.wait_for_selector('#modelMenu:not([hidden])', timeout=3000)
    ok(True, 'the banner button «Выбрать модель» opens the model menu')
    close_menu(page)
    ctx.close()

    # ================= the choice stays across a restart; the welcome window over the main window
    ok(restart(), 'restart')
    ctx, page = window(welcome=True)
    page.goto(URL); page.wait_for_selector('#welcomeView:not([hidden])', timeout=15000)
    ok(page.evaluate('document.body.dataset.model') == 'nomodel' and page.is_visible('#mainView') and page.is_hidden('#setupView'),
       'after a restart: the main window without a model, not the first-start screen')
    ok(page.inner_text('#welcomeModel') == '' and page.is_visible('#welcomeAbout'), 'welcome window: no model named, «О программе» there')
    page.click('#welcomeStart'); page.wait_for_selector('#welcomeView', state='hidden')
    page.wait_for_timeout(500)
    ok(page.is_hidden('#modelMenu') and state()['phase'] == 'nomodel', 'the menu does not open by itself after a restart; still nomodel')
    page.screenshot(path=os.path.join(shots, '4-after-restart.png'))

    # ================= 2. voices copied from another computer, no speech program
    os.makedirs(VDIR, exist_ok=True)
    with tarfile.open(os.path.join(S, 'mirror', 'vits-piper-en_US-ljspeech-medium.tar.bz2')) as tf:
        tf.extractall(VDIR, filter='data')
    onnx = os.path.join(VDIR, 'vits-piper-en_US-ljspeech-medium', 'en_US-ljspeech-medium.onnx')
    mtime = os.stat(onnx).st_mtime_ns
    st = state()['tts']
    en = next(v for v in st['voices'] if v['id'] == 'en-lj')
    ok(en['present'] and en['active'] and not st['engine']['present'], 'copied voice: present %s, active %s; program %s' % (en['present'], en['active'], st['engine']['present']))
    page.reload(); page.wait_for_selector('body[data-model="nomodel"]', timeout=15000)
    page.select_option('#srcSel', 'en'); page.select_option('#tgtSel', 'ru')
    page.fill('#src', 'The cat sleeps in the house.'); page.wait_for_timeout(400)
    ok('no-voice' in (page.get_attribute('#srcSpeak', 'class') or '') and page.get_attribute('#srcSpeak', 'title') == 'Нужна программа озвучки (меню моделей)',
       '🔊 without the program: ' + (page.get_attribute('#srcSpeak', 'title') or ''))
    page.click('#srcSpeak'); page.wait_for_timeout(200)
    ok('Голос «Английский · LJSpeech» есть, но нет программы озвучки sherpa-onnx' in toast(page) and 'голоса скачивать заново не нужно' in toast(page), '🔊 says: ' + toast(page))
    open_menu(page)
    prog = page.locator('#modelMenu .mitem.tts-program')
    ok(prog.count() == 1 and 'Программа озвучки sherpa-onnx' in prog.inner_text() and 'нужна, чтобы голоса, которые уже есть в папке, читали текст' in prog.inner_text(),
       'model menu: the row of the speech program: ' + (prog.inner_text().replace('\n', ' | ') if prog.count() else '-'))
    ok('есть в папке; нужна программа озвучки' in row(page, 'Английский · LJSpeech').inner_text() and 'нужно скачать' in row(page, 'Русский · Dmitri').inner_text(),
       'voices: the copied one is «in the folder», the other one is to be downloaded')
    page.screenshot(path=os.path.join(shots, '5-voices-without-program.png'))
    row(page, 'Английский · LJSpeech').locator('.pick').click()
    q = page.inner_text('#modelMenu .dl-confirm')
    ok('Скачать программу озвучки sherpa-onnx' in q and 'Голоса уже есть в папке' in q and TTS_URL in q and ENG in q and os.path.basename(TTS_URL) in q
       and 'vits-piper' not in q, 'question: ' + q.replace('\n', ' | ')[:240])
    ok('Без интернета: скопируйте с другого компьютера папку %s в папку %s' % (TTS_DIR, ENG) in q, 'how to copy it without internet')
    page.screenshot(path=os.path.join(shots, '6-program-question.png'))
    page.locator('#modelMenu .dl-confirm button', has_text='Отмена').click()
    ok(page.locator('#modelMenu .dl-confirm').count() == 0 and not state()['tts']['download']['active'], '«Отмена»: nothing downloaded')
    prog.locator('.pick').click()
    page.locator('#modelMenu .dl-confirm button.primary').click()
    ok(wait(lambda: state()['tts']['engine']['present'] and not state()['tts']['download']['active'], 120), 'the speech program is downloaded')
    st = state()['tts']
    ok(not st['download'].get('error') and json.load(open(os.path.join(ENG, 'tts.json')))['version'] == 'v1.13.7', 'no error, tts.json: %s' % st['download'])
    ok(os.stat(onnx).st_mtime_ns == mtime and not glob.glob(os.path.join(VDIR, '*.part')) and not glob.glob(os.path.join(ENG, '*.tar.bz2*')),
       'the voice was not downloaded again; no archives left')
    ok(not cfg().get('voices'), 'config.json: no voice choice written (%s)' % cfg().get('voices'))
    ok(wait(lambda: 'Программа озвучки скачана' in toast(page), 10), 'message: ' + toast(page))
    page.wait_for_timeout(300)
    ok(page.locator('#modelMenu .mitem.tts-program').count() == 0 and 'читает этот язык' in row(page, 'Английский · LJSpeech').inner_text(),
       'menu: no program row, the voice reads English')
    close_menu(page)
    ok(wait(lambda: page.get_attribute('#srcSpeak', 'title') == 'Прочитать вслух (Английский · LJSpeech)', 8), '🔊: ' + (page.get_attribute('#srcSpeak', 'title') or ''))
    page.click('#srcSpeak')
    page.wait_for_function("speech && speech.audio && !speech.audio.paused && speech.audio.currentTime > 0", timeout=30000)
    ok(True, 'reading aloud works — without a translation model')
    page.wait_for_function("!document.querySelector('#srcSpeak').classList.contains('speaking')", timeout=60000)
    ok('не удалось' not in toast(page).lower(), 'no error: ' + toast(page))

    # ================= 3. the sherpa-onnx folder copied by hand
    tj = os.path.join(ENG, 'tts.json')
    os.remove(tj)
    ok(state()['tts']['engine']['present'], 'without tts.json the program is found')
    meta = json.load(open(tj))
    ok(meta['version'] == 'manual' and meta['exe'] == TTS_DIR + '/bin/sherpa-onnx-offline-tts', 'tts.json written again: %s' % meta)
    ok('sherpa-onnx found (copied or unpacked by hand)' in log_text(), 'launcher.log says so')
    os.remove(tj)
    lib = os.path.join(ENG, TTS_DIR, 'lib')
    os.rename(lib, lib + '.away')
    ok(not state()['tts']['engine']['present'] and not os.path.exists(tj), 'a folder copied half way (no lib/libonnxruntime.so) is not taken')
    os.rename(lib + '.away', lib)
    ok(state()['tts']['engine']['present'], 'complete again: found')
    exe = os.path.join(ENG, TTS_DIR, 'bin', 'sherpa-onnx-offline-tts')
    os.chmod(exe, 0o644)
    code, ctype, body = tts('Hello there.')
    ok(code == 200 and ctype == 'audio/wav' and os.stat(exe).st_mode & 0o111 and 'execute permission restored' in log_text(),
       'a program without its execute permission gets it back and reads: %s %s' % (code, ctype))

    # ================= 1 (end). a model from the menu: the engine and the model are downloaded
    open_menu(page)
    row(page, 'Hy-MT2-1.8B · Q4_K_M (test)').locator('.pick').click()
    q = page.inner_text('#modelMenu .dl-confirm')
    ok('Скачать «Hy-MT2-1.8B · Q4_K_M (test)»' in q and 'tiny-q4.gguf' in q, 'download question: ' + q.replace('\n', ' | ')[:160])
    page.locator('#modelMenu .dl-confirm button.primary').click()
    page.wait_for_selector('#setupView:not([hidden])', timeout=10000)
    ok(page.is_visible('#dlCancelBtn') and page.is_hidden('#setupSkipBtn'), 'downloading: the progress screen with «Отмена», no «Пропустить»')
    page.click('#dlCancelBtn')
    page.wait_for_selector('body[data-model="nomodel"]', timeout=15000)
    banner = page.inner_text('#bnNoModel')
    ok(page.is_visible('#mainView') and 'Не получилось скачать' in banner and 'отменено' in banner, 'cancelled: back to the main window: ' + banner.replace('\n', ' | '))
    ok(cfg().get('setup_skipped') is True, 'still setup_skipped')
    open_menu(page)
    row(page, 'Hy-MT2-1.8B · Q4_K_M (test)').locator('.pick').click()
    page.locator('#modelMenu .dl-confirm button.primary').click()
    page.wait_for_selector('body[data-model="ready"]', timeout=120000)
    st = state()
    ok(st['phase'] == 'ready' and st['engine']['present'] and st['active_model'] == 'q4', 'the engine and the model are downloaded, the model works')
    ok('setup_skipped' not in cfg(), 'config.json: setup_skipped forgotten')
    ok(page.is_hidden('#modelBanner') and page.inner_text('#modelName') == 'Hy-MT2-1.8B · Q4_K_M (test)', 'no banner; the model is named in the header')
    open_menu(page)
    ok('✓ Hy-MT2-1.8B · Q4_K_M (test)' in page.inner_text('#modelMenu'), 'model menu: ✓ at the working model')
    close_menu(page)
    page.screenshot(path=os.path.join(shots, '7-ready.png'))
    ctx.close()
    b.close()
finally:
    try: post('/api/quit')
    except Exception: pass
    wait(lambda: not alive(), 10)
    for p in procs:
        try: p.kill()
        except Exception: pass

ok(not errs, 'no page errors: %s' % errs[:3])
fails = [r for r in res if r.startswith('FAIL')]
print('\nFAILS: %d of %d' % (len(fails), len(res)))
