# End-to-end test for v0.9 reading aloud: the real sherpa-onnx program and real Piper voices (served by the local
# mirror), the launcher and the UI in Chromium. Voices and their download (question with from/to/file, progress,
# licence notes, a failed download), the 🔊 buttons (pale without a voice, green while speaking, pause without the
# highlight, the ■ button, other button, Esc or editing the text stops, formulas not read, long text in pieces), the
# voice of each language, deleting a voice,
# /api/tts itself. Translation and chat answers are canned replies (fixtures written for the test).
# Usage: e2e_v09.py <work> <ui_url> <root>   (a ready launcher started with TDOC_TTS_URL and TDOC_TEST_VOICES;
#        voices: en-lj (works), ru-dm (works, non-commercial licence), de-x (its file is missing on the mirror))
import sys, json, os, re, time, urllib.request, urllib.error
from playwright.sync_api import sync_playwright
S, URL, ROOT = sys.argv[1], sys.argv[2], sys.argv[3]
shots = os.path.join(S, 'shots', 'v09'); os.makedirs(shots, exist_ok=True)
res = []
def ok(c, m): res.append(('OK  ' if c else 'FAIL') + ' ' + m); print(res[-1], flush=True)
def api(method, path, body=None, origin=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(URL.rstrip('/') + path, data=data, method=method,
                                 headers={'Content-Type': 'application/json', 'Origin': origin or URL.rstrip('/')})
    try:
        r = urllib.request.urlopen(req, timeout=120); return r.status, r.headers.get('Content-Type', ''), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get('Content-Type', ''), e.read()
def state():
    return json.load(urllib.request.urlopen(URL.rstrip('/') + '/api/state'))
def voice(vid):
    return next(v for v in state()['tts']['voices'] if v['id'] == vid)
def wait_voice(vid, t=240):
    end = time.time() + t
    while time.time() < end:
        st = state()['tts']
        v = next(v for v in st['voices'] if v['id'] == vid)
        if v['present'] and not st['download']['active']: return True
        if not st['download']['active'] and st['download'].get('error'): return False
        time.sleep(0.5)
    return False

replies = ['Небо голубое.']
def reply(route):
    body = json.loads(route.request.post_data)
    if body.get('messages') and body['messages'][0].get('role') == 'system':
        out = 'Это **ответ** модели. Он читается вслух по-русски.'
    else:
        out = replies[0]
    chunks = 'data: ' + json.dumps({'choices': [{'delta': {'content': out}}]}) + '\n\n'
    chunks += 'data: ' + json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}], 'timings': {'predicted_n': 5, 'predicted_per_second': 9.5}}) + '\n\ndata: [DONE]\n\n'
    route.fulfill(status=200, headers={'Content-Type': 'text/event-stream'}, body=chunks)

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={'width': 1180, 'height': 860}, locale='ru-RU')
    ctx.add_init_script("try { sessionStorage.setItem('tdoc.window', '1'); sessionStorage.setItem('tdoc.welcome', 'done') } catch (e) {}")
    page = ctx.new_page(); errs = []; tts_bodies = []
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'status of 4' not in m.text else None)
    page.on('request', lambda r: tts_bodies.append(json.loads(r.post_data)) if r.url.endswith('/api/tts') else None)
    page.route('**/v1/chat/completions', reply)
    page.goto(URL); page.wait_for_selector('body[data-model="ready"]', timeout=30000)
    def toast(): return page.inner_text('#toast')
    def refresh(): page.evaluate('refreshState()'); page.wait_for_timeout(300)
    def cls(sel): return page.get_attribute(sel, 'class') or ''
    def speaking(sel): return 'speaking' in cls(sel).split()
    def wait_silent(sel, t=60000):
        page.wait_for_function("(s) => !document.querySelector(s).classList.contains('speaking') && !document.querySelector(s).classList.contains('paused')", arg=sel, timeout=t)
    def open_menu():
        if page.is_hidden('#modelMenu'): page.click('#modelBtn')
        page.wait_for_selector('#modelMenu:not([hidden])')
    def voice_row(label):
        return page.locator('#modelMenu .mitem', has=page.locator('.title', has_text=label))

    # ================= no voices yet
    st = state()['tts']
    ok(not st['engine']['present'] and [v['id'] for v in st['voices']] == ['en-lj', 'ru-dm', 'de-x'] and not any(v['present'] for v in st['voices']), 'state: no sherpa-onnx, three voices to download')
    page.select_option('#srcSel', 'en'); page.select_option('#tgtSel', 'ru')
    page.fill('#src', 'The sky is blue.'); page.wait_for_timeout(400)
    ok(page.is_visible('#srcSpeak') and 'no-voice' in cls('#srcSpeak'), 'the 🔊 button of the text field is pale')
    page.click('#srcSpeak'); page.wait_for_timeout(200)
    ok('нет голоса' in toast() and 'меню моделей' in toast() and not tts_bodies, 'without a voice: a hint where to get one, no request: ' + toast())

    # ================= the voices in the model menu; the question before downloading
    open_menu()
    ok('Голоса для чтения вслух' in page.inner_text('#modelMenu') and voice_row('Английский · LJSpeech').count() == 1, 'the voices are in the model menu')
    sub = voice_row('Английский · LJSpeech').locator('.sub').inner_text()
    ok('нужно скачать' in sub and 'женский голос' in sub and 'лицензия: общественное достояние' in sub, 'voice row: ' + sub)
    sub = voice_row('Русский · Dmitri').locator('.sub').inner_text()
    ok('только некоммерческое использование' in sub, 'non-commercial licence shown: ' + sub)
    voice_row('Английский · LJSpeech').locator('.pick').click()
    q = page.inner_text('#modelMenu .dl-confirm')
    ok('Скачать голос «Английский · LJSpeech»' in q and 'Откуда:' in q and 'vits-piper-en_US-ljspeech-medium.tar.bz2' in q and os.path.join(ROOT, 'models', 'voices') in q, 'question with from/to/file: ' + q[:160].replace('\n', ' | '))
    ok('Один раз понадобится и программа озвучки sherpa-onnx' in q and 'sherpa-onnx-v1.13.7-linux-x64-shared.tar.bz2' in q and os.path.join(ROOT, 'engine', 'linux-amd64') in q, 'the speech program is named too')
    page.screenshot(path=os.path.join(shots, '1-voice-question.png'))
    page.locator('#modelMenu .dl-confirm button', has_text='Отмена').click(); page.wait_for_timeout(500)
    ok(not state()['tts']['download']['active'] and page.locator('#modelMenu .dl-confirm').count() == 0, '«Отмена» downloads nothing')
    voice_row('Английский · LJSpeech').locator('.pick').click()
    page.locator('#modelMenu .dl-confirm button.primary').click()
    page.wait_for_function("document.querySelector('#ttsInfo').textContent.includes('LJSpeech')", timeout=15000)
    ok('Английский · LJSpeech: ' in page.inner_text('#ttsInfo'), 'progress at the bottom of the window: ' + page.inner_text('#ttsInfo'))
    ok(page.is_visible('#mainView') and page.get_attribute('body', 'data-model') == 'ready', 'the window keeps working while a voice downloads')
    ok(wait_voice('en-lj'), 'voice and sherpa-onnx downloaded and unpacked')
    page.wait_for_function("document.querySelector('#ttsInfo').textContent === ''", timeout=10000)
    ok('Голос «Английский · LJSpeech» скачан' in toast(), 'message when ready: ' + toast())
    cfg = json.load(open(os.path.join(ROOT, 'config.json'), encoding='utf-8'))
    ok(cfg.get('voices') == {'en': 'en-lj'}, 'the voice is chosen for English in config.json: %s' % cfg.get('voices'))
    ok(os.path.exists(os.path.join(ROOT, 'engine', 'linux-amd64', 'tts.json')) and not os.path.exists(os.path.join(ROOT, 'models', 'voices', 'vits-piper-en_US-ljspeech-medium.tar.bz2')), 'tts.json written, archive removed')
    open_menu()
    t = voice_row('Английский · LJSpeech').inner_text()
    ok('✓' in t and 'читает этот язык' in t, 'the voice is marked ✓: ' + t.replace('\n', ' '))
    page.click('header .brand'); page.wait_for_timeout(200)

    # ================= reading the text field: green while speaking, formulas not read
    page.fill('#src', 'The energy of a photon is $E = \\hbar\\omega$. It is very small.'); page.wait_for_timeout(400)
    ok('no-voice' not in cls('#srcSpeak') and page.get_attribute('#srcSpeak', 'title') == 'Прочитать вслух (Английский · LJSpeech)', 'the button is active: ' + page.get_attribute('#srcSpeak', 'title'))
    n = len(tts_bodies)
    page.click('#srcSpeak'); page.wait_for_timeout(150)
    ok(speaking('#srcSpeak') and 'speaking-host' in cls('#src'), 'speaking: the button and the text are green')
    ok(page.locator('#srcSpeak + button.speak-stop').count() == 1 and page.get_attribute('#srcSpeak + button.speak-stop', 'title') == 'Остановить чтение (Esc)', 'the ■ button appears next to 🔊 (0.9.2)')
    page.wait_for_function("speech && speech.audio && !speech.audio.paused && speech.audio.currentTime > 0", timeout=30000)
    body = tts_bodies[n] if len(tts_bodies) > n else {}
    ok(body.get('lang') == 'en' and '$' not in body.get('text', '') and 'hbar' not in body.get('text', '') and 'It is very small.' in body.get('text', ''), 'request without the formula: %s' % body)
    page.screenshot(path=os.path.join(shots, '2-speaking.png'))
    wait_silent('#srcSpeak')
    ok('speaking-host' not in cls('#src') and 'no-voice' not in cls('#srcSpeak') and page.locator('button.speak-stop').count() == 0, 'after the end: the green highlight and the ■ button are gone')

    # ================= a long text in pieces, pause and continue, Esc stops
    long = ' '.join('Sentence number %d tells a little more about the weather in the mountains today.' % i for i in range(1, 9))
    page.fill('#src', long); page.wait_for_timeout(400)
    n = len(tts_bodies)
    page.click('#srcSpeak')
    page.wait_for_function("speech && speech.audio && !speech.audio.paused && speech.audio.currentTime > 0.3", timeout=30000)
    page.wait_for_timeout(1500)
    chunks = page.evaluate('speech.chunks')
    ok(len(chunks) >= 3 and all(len(c) <= 240 for c in chunks) and ' '.join(chunks) == long, 'pieces by sentences, not longer than 240: %s' % [len(c) for c in chunks])
    ok(len(tts_bodies) - n >= 2, 'the next piece is prepared while the first one sounds (%d requests)' % (len(tts_bodies) - n))
    page.click('#srcSpeak'); page.wait_for_timeout(300)
    t1 = page.evaluate('speech.audio.currentTime'); page.wait_for_timeout(700); t2 = page.evaluate('speech.audio.currentTime')
    ok('paused' in cls('#srcSpeak') and not speaking('#srcSpeak') and page.evaluate('speech.audio.paused') and t1 == t2, 'pause: the sound stops')
    ok('speaking-host' not in cls('#src') and page.locator('#srcSpeak + button.speak-stop').count() == 1, 'pause: the text is not highlighted, the ■ button stays (0.9.2)')
    page.screenshot(path=os.path.join(shots, '3-paused.png'))
    page.click('#srcSpeak'); page.wait_for_timeout(700)
    ok(speaking('#srcSpeak') and 'speaking-host' in cls('#src') and page.evaluate('speech.audio.currentTime') > t2, 'continue: the sound goes on, the text is green again')
    page.click('#srcSpeak + button.speak-stop'); page.wait_for_timeout(200)
    ok(not speaking('#srcSpeak') and 'paused' not in cls('#srcSpeak') and 'speaking-host' not in cls('#src') and page.evaluate('speech') is None
       and page.locator('button.speak-stop').count() == 0, 'the ■ button stops reading')
    page.click('#srcSpeak')
    page.wait_for_function("speech && speech.audio && !speech.audio.paused", timeout=30000)
    page.keyboard.press('Escape'); page.wait_for_timeout(200)
    ok(not speaking('#srcSpeak') and 'speaking-host' not in cls('#src') and page.evaluate('speech') is None, 'Esc stops reading')
    # editing the text stops reading: typing while it sounds; a click into the field while it is paused
    page.click('#srcSpeak')
    page.wait_for_function("speech && speech.audio && !speech.audio.paused", timeout=30000)
    page.focus('#src'); page.keyboard.press('End'); page.keyboard.type(' Yes.'); page.wait_for_timeout(200)
    ok(page.evaluate('speech') is None and not speaking('#srcSpeak') and 'speaking-host' not in cls('#src') and page.input_value('#src').endswith(' Yes.'),
       'typing in the field stops reading')
    page.click('header .brand')
    page.click('#srcSpeak')
    page.wait_for_function("speech && speech.audio && !speech.audio.paused", timeout=30000)
    page.click('#srcSpeak'); page.wait_for_timeout(200)
    ok(page.evaluate('speech && speech.paused') is True, 'paused again')
    page.click('#src'); page.wait_for_timeout(200)
    ok(page.evaluate('speech') is None and 'paused' not in cls('#srcSpeak') and page.locator('button.speak-stop').count() == 0, 'a click into the paused field stops reading: back to editing')

    # ================= variants: the language of the result; a second voice
    page.fill('#src', 'The sky is blue.'); page.wait_for_timeout(300)
    page.click('#goBtn'); page.wait_for_selector('#goBtn:not([hidden])', timeout=30000)
    card = page.locator('#cards .card').first
    ok(card.locator('[data-act=speak]').count() == 1 and 'no-voice' in (card.locator('[data-act=speak]').get_attribute('class') or ''), 'a Russian variant: the 🔊 button is pale (no Russian voice)')
    card.locator('[data-act=speak]').click(); page.wait_for_timeout(200)
    ok('Для языка «русский» нет голоса' in toast(), 'hint for Russian: ' + toast())
    open_menu()
    voice_row('Русский · Dmitri').locator('.pick').click()
    q = page.inner_text('#modelMenu .dl-confirm')
    ok('разрешает только некоммерческое использование' in q and 'программа озвучки' not in q, 'question: licence note, sherpa-onnx is already there')
    page.locator('#modelMenu .dl-confirm button.primary').click()
    ok(wait_voice('ru-dm'), 'Russian voice downloaded')
    refresh()
    ok('no-voice' not in (card.locator('[data-act=speak]').get_attribute('class') or ''), 'the button of the Russian variant is active now')
    page.click('header .brand'); page.wait_for_timeout(200)
    n = len(tts_bodies)
    card.locator('[data-act=speak]').click(); page.wait_for_timeout(150)
    ok('speaking-host' in (card.get_attribute('class') or '') and 'speaking' in card.locator('[data-act=speak]').get_attribute('class'), 'the variant is green while it is read')
    page.wait_for_function("speech && speech.audio && !speech.audio.paused", timeout=30000)
    ok(tts_bodies[n] == {'lang': 'ru', 'text': 'Небо голубое.', 'speed': 1}, 'variant request: %s' % tts_bodies[n])
    page.click('#srcSpeak'); page.wait_for_timeout(200)
    ok('speaking-host' not in (card.get_attribute('class') or '') and speaking('#srcSpeak'), 'another 🔊 button stops the previous reading')
    page.keyboard.press('Escape')

    # ================= «Свой вариант» and the chat answers
    page.fill('#ownText', 'Небо сегодня синее.'); page.wait_for_timeout(100)
    ok('no-voice' not in cls('#ownSpeak'), 'own version (Russian): active')
    page.click('#ownSpeak'); page.wait_for_timeout(150)
    ok(speaking('#ownSpeak') and 'speaking-host' in cls('#ownText'), 'own version is read')
    wait_silent('#ownSpeak')
    page.fill('#askInput', 'Как это сказать по-русски?'); page.click('#askSend')
    page.wait_for_selector('#askLog .msg.bot .msg-meta [data-act=speak]', timeout=20000)
    msg = page.locator('#askLog .msg.bot').last
    n = len(tts_bodies)
    msg.locator('[data-act=speak]').click(); page.wait_for_timeout(150)
    ok('speaking-host' in (msg.get_attribute('class') or ''), 'the chat answer is read and highlighted')
    page.wait_for_function("speech && speech.audio && !speech.audio.paused", timeout=30000)
    ok(len(tts_bodies) > n and tts_bodies[n]['lang'] == 'ru' and '*' not in tts_bodies[n]['text'], 'chat answer: Russian, without Markdown: %s' % tts_bodies[n])
    page.keyboard.press('Escape')

    # ================= a voice whose download fails
    open_menu()
    voice_row('Немецкий · Broken').locator('.pick').click()
    page.locator('#modelMenu .dl-confirm button.primary').click()
    page.wait_for_function("document.querySelector('#toast').textContent.includes('Голос не скачался')", timeout=20000)
    ok('404' in toast(), 'failed download reported: ' + toast())
    open_menu()
    ok('Голос не скачался' in page.inner_text('#modelMenu'), 'the menu shows the error too')
    page.click('header .brand')

    # ================= /api/tts itself
    code, ctype, body = api('POST', '/api/tts', {'lang': 'ru', 'text': 'Проверка.'})
    ok(code == 200 and ctype == 'audio/wav' and body[:4] == b'RIFF' and body[8:12] == b'WAVE' and len(body) > 10000, '/api/tts: WAV (%d, %s, %d bytes)' % (code, ctype, len(body)))
    code, _, body = api('POST', '/api/tts', {'lang': 'de', 'text': 'Hallo.'})
    ok(code == 409 and 'нет скачанного голоса' in body.decode(), 'no German voice: 409')
    code, _, _ = api('POST', '/api/tts', {'lang': 'ru', 'text': ' '})
    ok(code == 400, 'empty text: 400')
    code, _, _ = api('POST', '/api/tts', {'lang': 'ru', 'text': 'Проверка.'}, origin='http://evil.example')
    ok(code == 403, 'a foreign page cannot use it (%d)' % code)
    leftovers = [f for f in os.listdir(os.path.join(ROOT, 'models', 'voices')) if f.endswith('.wav')]
    ok(not leftovers, 'no WAV files left in the voices folder: %s' % leftovers)

    # ================= deleting a voice
    open_menu()
    row = voice_row('Английский · LJSpeech')
    row.locator('button.icon').click(); page.wait_for_timeout(100)
    ok('ещё раз' in row.locator('.sub').inner_text() and voice('en-lj')['present'], 'first click on the trash only asks')
    row.locator('button.icon').click(); page.wait_for_timeout(800)
    ok(not voice('en-lj')['present'] and not os.path.exists(os.path.join(ROOT, 'models', 'voices', 'vits-piper-en_US-ljspeech-medium')), 'voice deleted')
    page.click('header .brand')
    page.fill('#src', 'The sky is blue.'); page.wait_for_timeout(400); refresh()
    ok('no-voice' in cls('#srcSpeak'), 'English text: the button is pale again')
    cfg = json.load(open(os.path.join(ROOT, 'config.json'), encoding='utf-8'))
    ok(cfg.get('voices') == {'ru': 'ru-dm'}, 'config.json keeps only the Russian voice: %s' % cfg.get('voices'))
    page.screenshot(path=os.path.join(shots, '3-after.png'))
    ok(not errs, 'no console errors: %s' % errs[:3])
    b.close()

print('FAILS:', sum(1 for x in res if x.startswith('FAIL')), 'of', len(res))
