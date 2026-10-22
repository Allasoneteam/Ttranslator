# End-to-end test for v0.9.3 (the real sherpa-onnx program, voices served by the local mirror, the UI in Chromium):
#   - a voice made of parts — the model and tokens.txt as separate files and espeak-ng-data from its own archive, as
#     the Spanish es_ES-mls_9972-low came from Hugging Face in 0.9.3: the question lists every address and the files,
#     the progress counts all parts, a cancelled download keeps what has come and resumes, the parts are put
#     together into one folder, the voice reads; deleting it removes the folder;
#   - a voice with a lexicon (the real Chinese zh_CN-chaowen-medium): no espeak-ng-data, reads Chinese text; Chinese
#     text is cut into sentences without spaces (。！？), a long sentence at «，», pieces of up to 80 characters;
#   - the welcome window: moves by its title (not by its buttons), stays inside the program window, is back at its
#     place when opened again; «Выйти» asks once more and then closes the program (this launcher ends — last step).
# Usage: e2e_v093.py <work> <ui_url> <root>   (a ready launcher started with TDOC_TTS_URL and
#        TDOC_TEST_VOICES=voices093.json: es-parts and zh-cw)
import sys, json, os, time, urllib.request, urllib.error
from playwright.sync_api import sync_playwright
S, URL, ROOT = sys.argv[1], sys.argv[2], sys.argv[3]
shots = os.path.join(S, 'shots', 'v093'); os.makedirs(shots, exist_ok=True)
VOICES = os.path.join(ROOT, 'models', 'voices')
res = []
def ok(c, m): res.append(('OK  ' if c else 'FAIL') + ' ' + m); print(res[-1], flush=True)
def api(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(URL.rstrip('/') + path, data=data, method=method,
                                 headers={'Content-Type': 'application/json', 'Origin': URL.rstrip('/')})
    try:
        r = urllib.request.urlopen(req, timeout=120); return r.status, r.headers.get('Content-Type', ''), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get('Content-Type', ''), e.read()
def state():
    return json.load(urllib.request.urlopen(URL.rstrip('/') + '/api/state'))
def voice(vid):
    return next(v for v in state()['tts']['voices'] if v['id'] == vid)
def wait_voice(vid, t=240, seen=None):
    end = time.time() + t
    while time.time() < end:
        st = state()['tts']
        v = next(v for v in st['voices'] if v['id'] == vid)
        if seen is not None and st['download']['active']: seen.append(dict(st['download']))
        if v['present'] and not st['download']['active']: return True
        if not st['download']['active'] and st['download'].get('error'): return False
        time.sleep(0.3)
    return False

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={'width': 1180, 'height': 860}, locale='ru-RU')
    ctx.add_init_script("try { sessionStorage.setItem('tdoc.window', '1'); sessionStorage.setItem('tdoc.welcome', 'done') } catch (e) {}")
    page = ctx.new_page(); errs = []
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'status of 4' not in m.text else None)
    page.goto(URL); page.wait_for_selector('body[data-model="ready"]', timeout=30000)
    def toast(): return page.inner_text('#toast')
    def open_menu():
        if page.is_hidden('#modelMenu'): page.click('#modelBtn')
        page.wait_for_selector('#modelMenu:not([hidden])')
    def voice_row(label):
        return page.locator('#modelMenu .mitem', has=page.locator('.title', has_text=label))

    # ================= a voice made of parts: the question names every file and address
    es = voice('es-parts')
    files = [p['file'] for p in es['parts']]
    ok(files == ['es_ES-test-low.onnx', 'tokens.txt', 'espeak-ng-data.tar.bz2'] and es['size'] == sum(p['size'] for p in es['parts']) and not es['present'],
       'state: the Spanish voice has three parts, its size is their sum: %s' % files)
    ok(len(voice('zh-cw')['parts']) == 1 and voice('zh-cw')['parts'][0]['file'] == 'vits-piper-zh_CN-chaowen-medium.tar.bz2', 'an archive voice: one part, the archive')
    open_menu()
    sub = voice_row('Испанский · Parts').locator('.sub').inner_text()
    ok('нужно скачать' in sub and 'женский голос' in sub and 'CC BY 4.0' in sub, 'voice row: ' + sub)
    ok('мужской голос' in voice_row('Китайский · Chaowen').locator('.sub').inner_text(), 'the Chinese voice: male')
    voice_row('Испанский · Parts').locator('.pick').click()
    q = page.inner_text('#modelMenu .dl-confirm')
    ok(q.count('Откуда:') == 4 and all(p['url'] in q for p in es['parts']) and 'Файлы:' in q and 'es_ES-test-low.onnx, tokens.txt, espeak-ng-data.tar.bz2' in q
       and VOICES in q, 'the question lists the three addresses and the files (and the speech program): ' + q[:300].replace('\n', ' | '))
    page.screenshot(path=os.path.join(shots, '1-parts-question.png'))

    # ================= download, cancel in the middle of the model: what has come stays; then it resumes
    page.locator('#modelMenu .dl-confirm button.primary').click()
    seen = []
    end = time.time() + 120
    while time.time() < end:
        d = state()['tts']['download']; seen.append(d)
        if d.get('active') and d.get('item') == 'voice' and d.get('done', 0) > 4_000_000: break
        time.sleep(0.2)
    api('POST', '/api/voice-cancel'); time.sleep(1.0)
    st = state()['tts']; v = voice('es-parts')
    stage = os.path.join(VOICES, 'vits-piper-es_ES-test-low.download')
    ok(not st['download']['active'] and st['download']['error'] == 'скачивание отменено' and v['partial'] > 4_000_000 and not v['present']
       and os.path.exists(os.path.join(stage, 'es_ES-test-low.onnx.part')), 'cancelled: %d bytes kept in %s' % (v['partial'], os.path.basename(stage)))
    voice_dl = [d for d in seen if d.get('active') and d.get('item') == 'voice']
    ok(voice_dl and all(d['total'] == es['size'] and d['done'] <= d['total'] for d in voice_dl), 'progress of the voice: of all parts together (%s)' % ({d['total'] for d in voice_dl},))
    open_menu()
    sub = voice_row('Испанский · Parts').locator('.sub').inner_text()
    ok('скачано' in sub and '%' in sub, 'the menu shows the part already downloaded: ' + sub)
    page.click('header .brand')
    seen = []
    code, _, _ = api('POST', '/api/voice', {'id': 'es-parts'})
    ok(code == 200 and wait_voice('es-parts', seen=seen), 'download resumed and finished')
    early = [d['done'] for d in seen if d.get('item') == 'voice' and 0 < d['done'] < 3_500_000]
    ok(seen and not early, 'resumed, not from the start (no progress below the part kept: %s)' % early[:3])
    vd = os.path.join(VOICES, 'vits-piper-es_ES-test-low')
    ok(all(os.path.isfile(os.path.join(vd, f)) for f in ('es_ES-test-low.onnx', 'tokens.txt', 'espeak-ng-data/phontab')) and not os.path.exists(stage)
       and not os.path.exists(os.path.join(VOICES, 'espeak-ng-data.tar.bz2')), 'the parts are put together in one folder, the download folder is gone: %s' % sorted(os.listdir(vd)))
    code, ctype, body = api('POST', '/api/tts', {'lang': 'es', 'text': 'Hola, ¿qué tal? El cielo es azul.'})
    ok(code == 200 and ctype == 'audio/wav' and body[:4] == b'RIFF' and len(body) > 20000, 'the voice of parts reads Spanish text: %d, %d bytes' % (code, len(body)))
    cfg = json.load(open(os.path.join(ROOT, 'config.json'), encoding='utf-8'))
    ok(cfg.get('voices', {}).get('es') == 'es-parts', 'chosen for Spanish in config.json: %s' % cfg.get('voices'))

    # ================= the Chinese voice: a lexicon and rules instead of espeak-ng-data
    code, _, _ = api('POST', '/api/voice', {'id': 'zh-cw'})
    ok(code == 200 and wait_voice('zh-cw'), 'the Chinese voice downloaded')
    zd = os.path.join(VOICES, 'vits-piper-zh_CN-chaowen-medium')
    ok(all(os.path.isfile(os.path.join(zd, f)) for f in ('lexicon.txt', 'phone.fst', 'date.fst', 'number.fst')) and not os.path.exists(os.path.join(zd, 'espeak-ng-data')),
       'its folder: lexicon and rules, no espeak-ng-data')
    t0 = time.time()
    code, ctype, body = api('POST', '/api/tts', {'lang': 'zh', 'text': '你好，世界。今天是2026年10月22日。'})
    ok(code == 200 and ctype == 'audio/wav' and body[:4] == b'RIFF' and len(body) > 40000, 'Chinese text read: %d, %d bytes in %.1f s' % (code, len(body), time.time() - t0))
    # pieces of Chinese text: sentences without spaces, a long sentence at «，», not longer than 80
    page.evaluate('refreshState()'); page.wait_for_timeout(300)
    zh_text = '今天天气很好。我们去公园散步吧！你觉得怎么样？' + '这是一个很长的句子，' * 12 + '结束。'
    page.select_option('#srcSel', 'zh'); page.select_option('#tgtSel', 'ru')
    page.fill('#src', zh_text); page.wait_for_timeout(400)
    ok('no-voice' not in (page.get_attribute('#srcSpeak', 'class') or '') and 'Chaowen' in page.get_attribute('#srcSpeak', 'title'), 'the 🔊 button reads Chinese: ' + page.get_attribute('#srcSpeak', 'title'))
    page.click('#srcSpeak')
    page.wait_for_function("speech && speech.audio && !speech.audio.paused && speech.audio.currentTime > 0", timeout=60000)
    chunks = page.evaluate('speech.chunks')
    ok(chunks[0] == '今天天气很好。我们去公园散步吧！你觉得怎么样？' and all(len(c) <= 80 for c in chunks) and ''.join(chunks) == zh_text
       and len(chunks) == 3 and chunks[1].endswith('，'), 'Chinese pieces: %s' % [len(c) for c in chunks])
    page.screenshot(path=os.path.join(shots, '2-chinese-speaking.png'))
    page.keyboard.press('Escape'); page.wait_for_timeout(200)
    other = page.evaluate("speechChunks('One sentence. Two sentences here.', 'en')")
    ok(other == ['One sentence. Two sentences here.'], 'other languages unchanged: %s' % other)

    # ================= deleting the voice of parts
    open_menu()
    row = voice_row('Испанский · Parts')
    row.locator('button.icon').click(); page.wait_for_timeout(100)
    row.locator('button.icon').click(); page.wait_for_timeout(800)
    ok(not voice('es-parts')['present'] and not os.path.exists(vd) and not os.path.exists(stage), 'the voice of parts deleted with its folder')
    page.click('header .brand')

    # ================= the welcome window: moves by its title, not by its buttons
    page.evaluate('openWelcome(false)'); page.wait_for_selector('#welcomeView:not([hidden])')
    panel = page.locator('#welcomeView .panel.welcome')
    b0 = panel.bounding_box()
    ok(page.is_visible('#welcomeQuit') and page.inner_text('#welcomeQuit') == 'Выйти' and page.evaluate("$('#welcomeView .panel.welcome').style.transform") == '',
       'the welcome window has «Выйти», at its usual place: %s' % b0)
    btns = page.locator('#welcomeView .welcome-btns button')
    ok([btns.nth(i).inner_text() for i in range(btns.count())] == ['Начать работу', 'Выйти', 'О программе'], 'buttons: %s' % [btns.nth(i).inner_text() for i in range(btns.count())])
    head = page.locator('#welcomeView .about-head').bounding_box()
    ok(page.evaluate("getComputedStyle($('#welcomeView .about-head')).cursor") == 'move', 'the title shows the move cursor')
    def drag(x, y, dx, dy):
        page.mouse.move(x, y); page.mouse.down(); page.mouse.move(x + dx / 2, y + dy / 2, steps=4); page.mouse.move(x + dx, y + dy, steps=4); page.mouse.up()
    hx, hy = head['x'] + head['width'] - 30, head['y'] + head['height'] / 2
    drag(hx, hy, 160, 90)
    b1 = panel.bounding_box()
    ok(abs(b1['x'] - b0['x'] - 160) <= 1 and abs(b1['y'] - b0['y'] - 90) <= 1 and abs(b1['width'] - b0['width']) <= 1 and abs(b1['height'] - b0['height']) <= 1,
       'dragged by the title: moved by (%.0f, %.0f), same size' % (b1['x'] - b0['x'], b1['y'] - b0['y']))
    page.screenshot(path=os.path.join(shots, '3-welcome-moved.png'))
    # an empty place of the window moves it too; a button does not (and is not pressed)
    h3 = page.locator('#welcomeNewTitle').bounding_box()
    drag(h3['x'] + h3['width'] + 20, h3['y'] + h3['height'] / 2, -60, -40)
    b2 = panel.bounding_box()
    ok(abs(b2['x'] - b1['x'] + 60) <= 1 and abs(b2['y'] - b1['y'] + 40) <= 1, 'dragged by an empty place: (%.0f, %.0f)' % (b2['x'] - b1['x'], b2['y'] - b1['y']))
    mode_before = state()['settings']['launch_mode']
    sb = page.locator('#welcomeModeSeg button[data-v=tab]').bounding_box()
    drag(sb['x'] + sb['width'] / 2, sb['y'] + sb['height'] / 2, 120, 60)
    b3 = panel.bounding_box()
    ok(abs(b3['x'] - b2['x']) <= 1 and abs(b3['y'] - b2['y']) <= 1 and state()['settings']['launch_mode'] == mode_before, 'a button does not move the window and is not pressed')
    # not out of the program window
    head = page.locator('#welcomeView .about-head').bounding_box()
    drag(head['x'] + 40, head['y'] + head['height'] / 2, -3000, -2000)
    b4 = panel.bounding_box()
    ok(abs(b4['x'] + b4['width'] - 80) <= 1 and abs(b4['y']) <= 1, 'stays inside: right edge at %.0f, top at %.0f' % (b4['x'] + b4['width'], b4['y']))
    head = page.locator('#welcomeView .about-head').bounding_box()   # only its right end is still visible
    drag(head['x'] + head['width'] - 30, head['y'] + head['height'] / 2, 5000, 3000)
    b5 = panel.bounding_box()
    vw, vh = page.evaluate('[document.documentElement.clientWidth, document.documentElement.clientHeight]')
    ok(abs(b5['x'] - (vw - 80)) <= 1 and abs(b5['y'] - (vh - 60)) <= 1, 'stays inside: left edge at %.0f, top at %.0f (window %dx%d)' % (b5['x'], b5['y'], vw, vh))
    # opened again: back at its place
    page.keyboard.press('Escape'); page.wait_for_timeout(200)
    ok(page.is_hidden('#welcomeView'), 'Esc closes the welcome window')
    page.evaluate('openWelcome(false)'); page.wait_for_selector('#welcomeView:not([hidden])')
    b6 = panel.bounding_box()
    ok(abs(b6['x'] - b0['x']) <= 1 and abs(b6['y'] - b0['y']) <= 1, 'opened again: at its usual place (%.0f, %.0f)' % (b6['x'], b6['y']))

    # ================= «Выйти» in the welcome window: once more to confirm, then the program closes
    page.click('#welcomeQuit')
    ok(page.inner_text('#welcomeQuit') == 'Выйти?' and 'confirm' in (page.get_attribute('#welcomeQuit', 'class') or '') and page.is_visible('#welcomeView'),
       'first press asks: ' + page.inner_text('#welcomeQuit'))
    page.screenshot(path=os.path.join(shots, '4-welcome-quit-confirm.png'))
    page.wait_for_timeout(4300)
    ok(page.inner_text('#welcomeQuit') == 'Выйти' and 'confirm' not in (page.get_attribute('#welcomeQuit', 'class') or ''), 'after 4 seconds the question is gone')
    ok(not errs, 'no console errors: %s' % errs[:3])
    page.click('#welcomeQuit'); page.click('#welcomeQuit')
    page.wait_for_selector('#byeView:not([hidden])', timeout=10000)
    ok(page.is_hidden('#welcomeView') and page.get_attribute('body', 'data-model') == 'bye', 'second press: the program closes, the welcome window is gone')
    page.screenshot(path=os.path.join(shots, '5-bye.png'))
    gone = False
    for i in range(40):
        try: urllib.request.urlopen(URL.rstrip('/') + '/api/ping', timeout=1)
        except Exception: gone = True; break
        time.sleep(0.25)
    ok(gone, 'the launcher has ended')
    b.close()

print('FAILS:', sum(1 for x in res if x.startswith('FAIL')), 'of', len(res))
