# End-to-end test for 1.3: the Supertonic 3 voice — one archive for 13 languages, the real model and the real sherpa-onnx
# program served by the local mirror (the entries are those of tts.go, taken through TestDumpVoiceCatalog; only the
# address is the mirror's) — and the new translation languages Japanese, Korean and Hindi.
#   - the model menu: one row «Supertonic 3 · все языки, кроме китайского и латыни» (not one per language), OpenRAIL-M;
#     the Piper voice Dmitri as before;
#   - download: the question names the archive of the sherpa-onnx release and the licence; afterwards Supertonic reads
#     all 13 languages (config.json "voices"); under its row — ten speakers;
#   - /api/tts in Japanese, Korean, Hindi, Arabic, Greek: 44.1 kHz speech of a sensible length from supertonic-<lang>;
#     the male speaker M1 (5) speaks lower than F1 (0); a voice of another language is refused;
#   - the speaker until one is chosen: M4 (8, the author's choice of 17.11.2026); the female F1 (0) is stored too;
#   - Dmitri chosen for Russian reads only Russian: the Supertonic row says «12 из 13 … другим голосом: русский» and has
#     no ✓, Dmitri has it (one ✓ for Russian — the author's remark of 17.11.2026); a click on the row — all 13 again,
#     ✓ on the row, and Dmitri says that Supertonic reads Russian now;
#   - a speaker button stores the speaker in config.json and plays a sample with Supertonic in the interface language;
#   - reading a chat answer aloud stops at once when «Обновить» wipes the chat (the author's remark of 17.11.2026), and
#     when the text that is read is taken away from the window;
#   - the new languages: in the lists; «Авто» recognizes Japanese (kana with kanji), Korean, Hindi, and Chinese stays
#     Chinese; reading aloud splits Japanese at 。 and Hindi at ।; the 🔊 button of the text field reads Japanese;
#   - deleting through the row removes the folder for every language; Dmitri stays.
# Usage: e2e_v13.py <work> <ui_url> <root>   (a ready launcher started with TDOC_TTS_URL and TDOC_TEST_VOICES=voices13.json)
import io, json, os, sys, time, urllib.error, urllib.request, wave
import numpy as np
from playwright.sync_api import sync_playwright
S, URL, ROOT = sys.argv[1], sys.argv[2], sys.argv[3]
shots = os.path.join(S, 'shots', 'v13'); os.makedirs(shots, exist_ok=True)
res = []
def ok(c, m): res.append(('OK  ' if c else 'FAIL') + ' ' + m); print(res[-1], flush=True)
def state():
    return json.load(urllib.request.urlopen(URL.rstrip('/') + '/api/state'))
def post(path, body):
    req = urllib.request.Request(URL.rstrip('/') + path, data=json.dumps(body).encode(), method='POST',
                                 headers={'Content-Type': 'application/json', 'Origin': URL.rstrip('/')})
    try:
        r = urllib.request.urlopen(req, timeout=120)
        return r.status, r.headers.get('Content-Type', ''), r.headers.get('X-Voice', ''), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get('Content-Type', ''), '', e.read()
def tts(text, lang, voice=None):
    body = {'lang': lang, 'text': text}
    if voice: body['voice'] = voice
    return post('/api/tts', body)
def wav(b):
    with wave.open(io.BytesIO(b)) as w:
        sr = w.getframerate()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    return sr, x
def pitch(sr, x):
    # median fundamental frequency of the voiced 40 ms frames (autocorrelation, 70–400 Hz)
    fr, hop, f0 = int(0.04 * sr), int(0.01 * sr), []
    for i in range(0, len(x) - fr, hop):
        seg = x[i:i + fr] - x[i:i + fr].mean()
        if np.sqrt((seg ** 2).mean()) < 0.02:
            continue
        ac = np.correlate(seg, seg, 'full')[fr - 1:]
        lo, hi = int(sr / 400), int(sr / 70)
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] > 0.4 * ac[0]:
            f0.append(sr / k)
    return float(np.median(f0)) if f0 else 0.0
def cfg():
    return json.load(open(os.path.join(ROOT, 'config.json'), encoding='utf-8'))
def wait_download(cond, secs=600):
    end = time.time() + secs
    while time.time() < end:
        st = state()['tts']
        if cond(st) and not st['download']['active']: return st
        if not st['download']['active'] and st['download'].get('error'): return st
        time.sleep(0.5)
    return state()['tts']

ST_LANGS = ['ru', 'en', 'de', 'fr', 'es', 'el', 'sv', 'it', 'pt', 'ar', 'ja', 'ko', 'hi']
SAMPLES = {'ja': '電車は朝早く出発して、夕方に東京に着きます。', 'ko': '기차는 아침 일찍 출발해서 저녁에 서울에 도착해요.',
           'hi': 'ट्रेन सुबह जल्दी निकलती है और शाम को दिल्ली पहुँचती है।', 'ar': 'يغادر القطار في الصباح الباكر ويصل إلى القاهرة في المساء.',
           'el': 'Το τρένο φεύγει νωρίς το πρωί και φτάνει στην Αθήνα το βράδυ.'}
STDIR = os.path.join(ROOT, 'models', 'voices', 'sherpa-onnx-supertonic-3-tts-int8-2026-05-11')

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={'width': 1180, 'height': 900}, locale='ru-RU')
    ctx.add_init_script("try { sessionStorage.setItem('tdoc.window', '1'); sessionStorage.setItem('tdoc.welcome', 'done') } catch (e) {}")
    page = ctx.new_page(); errs = []; tts_bodies = []
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'status of 4' not in m.text else None)
    page.on('request', lambda r: tts_bodies.append(json.loads(r.post_data)) if r.url.endswith('/api/tts') else None)
    page.goto(URL); page.wait_for_selector('body[data-model="ready"]', timeout=30000)
    def toast(): return page.inner_text('#toast')
    def open_menu():
        if page.is_hidden('#modelMenu'): page.click('#modelBtn')
        page.wait_for_selector('#modelMenu:not([hidden])')
    def close_menu():
        if not page.is_hidden('#modelMenu'): page.click('header .brand'); page.wait_for_timeout(200)
    def voice_row(label):
        return page.locator('#modelMenu .mitem', has=page.locator('.title', has_text=label))
    st_row = lambda: page.locator('#modelMenu .mitem.supertonic')

    # ================= the catalogue: 13 Supertonic entries in one folder, first; one row in the menu
    vs = state()['tts']['voices']
    st = [v for v in vs if v.get('engine') == 'supertonic']
    ok([v['lang'] for v in st] == ST_LANGS and all(v['id'] == 'supertonic-' + v['lang'] for v in st) and vs[:len(st)] == st,
       'Supertonic entries, first: %s' % [v['lang'] for v in st])
    ok(len({v['file'] for v in st}) == 1 and st[0]['file'] == 'sherpa-onnx-supertonic-3-tts-int8-2026-05-11.tar.bz2' and st[0]['license'] == 'OpenRAIL-M'
       and not st[0]['nc'] and st[0]['size'] == 128774318, 'one archive: %s, %s, %d bytes' % (st[0]['file'], st[0]['license'], st[0]['size']))
    ok(state()['tts'].get('supertonic') == {'speaker': 8, 'speakers': 10} and 'supertonic_speaker' not in cfg(), 'speaker M4 until one is chosen: %s' % state()['tts'].get('supertonic'))
    open_menu()
    titles = page.locator('#modelMenu .mitem .title').all_inner_texts()
    ok(st_row().count() == 1 and sum('Supertonic' in x for x in titles) == 1 and 'Supertonic 3 · все языки, кроме китайского и латыни' in st_row().inner_text(),
       'one Supertonic row: %s' % [x for x in titles if 'Supertonic' in x])
    sub = st_row().locator('.sub').first.inner_text()
    ok('нужно скачать' in sub and 'OpenRAIL-M' in sub and 'один файл на 13 языков' in sub, 'its line: ' + sub)
    ok(voice_row('Русский · Dmitri').count() == 1 and 'Голоса для чтения вслух (Supertonic и Piper' in page.inner_text('#modelMenu'), 'the Piper voice Dmitri and the group title')
    ok(page.locator('#modelMenu .st-speakers').count() == 0, 'no speaker choice before the download')
    page.screenshot(path=os.path.join(shots, '1-menu.png'))

    # ================= download (sherpa-onnx too): Supertonic reads all 13 languages
    st_row().locator('.pick').click()
    q = page.inner_text('#modelMenu .dl-confirm')
    ok('sherpa-onnx-supertonic-3-tts-int8-2026-05-11.tar.bz2' in q and 'Supertonic 3 (все языки, кроме китайского и латыни)' in q and 'OpenRAIL-M' in q
       and os.path.join(ROOT, 'models', 'voices') in q, 'question: ' + q[:220].replace('\n', ' | '))
    page.locator('#modelMenu .dl-confirm button.primary').click()
    tst = wait_download(lambda s: all(v['present'] for v in s['voices'] if v.get('engine') == 'supertonic') and s['engine']['present'])
    ok(all(v['present'] and v['active'] for v in tst['voices'] if v.get('engine') == 'supertonic') and tst['engine']['present'], 'downloaded, all active: %s' % tst['download'])
    ok(cfg().get('voices') == {l: 'supertonic-' + l for l in ST_LANGS}, 'chosen for all 13 in config.json: %s' % cfg().get('voices'))
    ok(all(os.path.exists(os.path.join(STDIR, f)) for f in ('duration_predictor.int8.onnx', 'text_encoder.int8.onnx', 'vector_estimator.int8.onnx',
       'vocoder.int8.onnx', 'tts.json', 'unicode_indexer.bin', 'voice.bin')), 'the folder: %s' % (sorted(os.listdir(STDIR)) if os.path.isdir(STDIR) else []))
    page.wait_for_timeout(1200)
    open_menu()
    ok('читает все эти языки' in st_row().locator('.sub').first.inner_text() and page.locator('#modelMenu .st-speakers .seg button').count() == 10,
       'row: %s; speakers: %d' % (st_row().locator('.sub').first.inner_text(), page.locator('#modelMenu .st-speakers .seg button').count()))
    ok(page.locator('#modelMenu .st-speakers .seg button').all_inner_texts() == ['Ж1', 'Ж2', 'Ж3', 'Ж4', 'Ж5', 'М1', 'М2', 'М3', 'М4', 'М5']
       and page.locator('#modelMenu .st-speakers .seg button[aria-pressed="true"]').inner_text() == 'М4' and 'мужской 4' in page.inner_text('#modelMenu .st-speakers'),
       'speaker buttons, М4 chosen: ' + page.inner_text('#modelMenu .st-speakers'))
    ok(st_row().locator('.title').inner_text().startswith('✓ Supertonic 3'), 'the row has ✓: ' + st_row().locator('.title').inner_text())
    page.screenshot(path=os.path.join(shots, '2-downloaded.png'))
    close_menu()

    # ================= speech in the new languages, Arabic and Greek
    for lang, text in SAMPLES.items():
        t0 = time.time()
        code, ctype, xv, body = tts(text, lang)
        if code == 200:
            sr, x = wav(body); sec = len(x) / sr
            ok(ctype == 'audio/wav' and xv == 'supertonic-' + lang and sr == 44100 and 1.5 < sec < 10,
               '%s: %.2f s of speech in %.1f s (%s)' % (lang, sec, time.time() - t0, xv))
        else:
            ok(False, '%s: %s %s' % (lang, code, body[:300]))
    code, _, _, body = tts('Привет.', 'ru', voice='supertonic-ja')
    ok(code == 409, 'a voice of another language is refused: %s' % code)
    code, _, _, body = tts('你好。', 'zh')
    ok(code == 409, 'Chinese has no voice here: %s' % code)
    # the speaker: F1 (0) and M1 (5)
    f = {}
    for sid in (0, 5):
        post('/api/voice-speaker', {'speaker': sid})
        code, _, xv, body = tts('The train leaves early in the morning and arrives in London in the evening.', 'en')
        f[sid] = pitch(*wav(body)) if code == 200 else 0
    ok(f[0] > 140 and f[5] < 140 and f[0] > f[5] + 30, 'F1 speaks higher than M1: %.0f Hz and %.0f Hz' % (f[0], f[5]))
    post('/api/voice-speaker', {'speaker': 0})
    ok(cfg().get('supertonic_speaker') == 0 and state()['tts']['supertonic']['speaker'] == 0, 'F1 (0) is stored: %s' % cfg().get('supertonic_speaker'))
    ok(post('/api/voice-speaker', {'speaker': 10})[0] == 400, 'speaker 10 is refused')

    # ================= a Piper voice for one language; the Supertonic row brings all back
    open_menu()
    voice_row('Русский · Dmitri').locator('.pick').click()
    page.locator('#modelMenu .dl-confirm button.primary').click()
    tst = wait_download(lambda s: [v for v in s['voices'] if v['id'] == 'ru-dmitri'][0]['present'])
    act = {v['lang']: v['id'] for v in tst['voices'] if v['active']}
    ok(act.get('ru') == 'ru-dmitri' and act.get('ja') == 'supertonic-ja' and act.get('en') == 'supertonic-en', 'Dmitri reads Russian only: %s' % act)
    page.wait_for_timeout(1200); open_menu()
    ok('читает 12 из 13 языков; другим голосом: русский; нажмите, чтобы читал все' in st_row().locator('.sub').first.inner_text(), 'row: ' + st_row().locator('.sub').first.inner_text())
    ok(not st_row().locator('.title').inner_text().startswith('✓') and voice_row('Русский · Dmitri').locator('.title').inner_text().startswith('✓ ')
       and voice_row('Русский · Dmitri').locator('.sub').inner_text().count('читает этот язык') == 1,
       'one ✓ for Russian, on Dmitri: %s | %s' % (st_row().locator('.title').inner_text(), voice_row('Русский · Dmitri').locator('.title').inner_text()))
    page.screenshot(path=os.path.join(shots, '2a-dmitri-for-russian.png'))
    st_row().locator('.pick').click(); page.wait_for_timeout(800)
    act = {v['lang']: v['id'] for v in state()['tts']['voices'] if v['active']}
    ok(act.get('ru') == 'supertonic-ru' and cfg()['voices'].get('ru') == 'supertonic-ru', 'a click on the row — Supertonic for all again: %s' % act.get('ru'))
    open_menu()
    ok(st_row().locator('.title').inner_text().startswith('✓ ') and not voice_row('Русский · Dmitri').locator('.title').inner_text().startswith('✓')
       and 'скачан; сейчас этот язык читает Supertonic — нажмите, чтобы выбрать этот голос' in voice_row('Русский · Dmitri').locator('.sub').inner_text(),
       'the ✓ back on the row; Dmitri: %s' % voice_row('Русский · Dmitri').locator('.sub').inner_text())

    # ================= a speaker button: stored, and a sample in the interface language
    open_menu()
    n = len(tts_bodies)
    page.locator('#modelMenu .st-speakers .seg button').nth(6).click()
    end = time.time() + 30
    while time.time() < end and len(tts_bodies) <= n: page.wait_for_timeout(200)   # (time.sleep would not let the events in)
    smp = tts_bodies[n] if len(tts_bodies) > n else {}
    ok(cfg().get('supertonic_speaker') == 6 and state()['tts']['supertonic']['speaker'] == 6, 'М2 stored: %s' % cfg().get('supertonic_speaker'))
    ok(smp.get('voice') == 'supertonic-ru' and smp.get('lang') == 'ru' and smp.get('text') == 'Здравствуйте! Так звучит этот голос.', 'the sample: %s' % smp)
    page.wait_for_function("!document.querySelector('#modelMenu .st-speakers button.speak') || !document.querySelector('#modelMenu .st-speakers button.speak').classList.contains('speaking')", timeout=60000)
    ok('не удалось' not in toast().lower(), 'no error: ' + toast())
    ok(page.locator('#modelMenu .st-speakers .seg button[aria-pressed="true"]').inner_text() == 'М2' and 'мужской 2' in page.inner_text('#modelMenu .st-speakers'),
       'the chosen speaker is marked: ' + page.inner_text('#modelMenu .st-speakers'))
    page.screenshot(path=os.path.join(shots, '3-speaker.png'))
    close_menu()

    # ================= the new languages of translation
    opts = page.locator('#srcSel option').all_inner_texts()
    ok(opts[-3:] == ['Японский', 'Корейский', 'Хинди'] and page.locator('#tgtSel option').all_inner_texts()[-3:] == ['Японский', 'Корейский', 'Хинди'], 'lists: %s' % opts[-4:])
    det = page.evaluate("""() => [detectLang('猫は家のソファーで寝ています。'), detectLang('고양이가 집에서 소파 위에 자고 있어요.'),
      detectLang('बिल्ली घर में सोफ़े पर सो रही है।'), detectLang('猫在家里的沙发上睡觉。'), detectLang('東京大学'), detectLang('Мы читаем статью.')]""")
    ok(det == ['ja', 'ko', 'hi', 'zh', 'zh', 'ru'], '«Авто»: %s' % det)
    # Japanese: chunks as short as Chinese ones, joined without spaces; Hindi: a sentence ends at ।
    ch = page.evaluate("""() => { const j = speechChunks('あ'.repeat(50) + '。' + 'い'.repeat(50) + '。', 'ja');
      const h = speechChunks('क'.repeat(100) + '। ' + 'ख'.repeat(100) + ' ' + 'ग'.repeat(100) + '।', 'hi');
      return [j.length, j[0].endsWith('。'), j.join('').includes(' '), h.length, h[0].endsWith('।'), h[0].length]; }""")
    ok(ch == [2, True, False, 2, True, 101], 'reading aloud: Japanese and Hindi chunks: %s' % ch)
    page.select_option('#srcSel', 'ja'); page.select_option('#tgtSel', 'ru')
    page.fill('#src', '窓を閉めていただけますか。'); page.wait_for_timeout(400)
    ok('no-voice' not in (page.get_attribute('#srcSpeak', 'class') or '') and page.get_attribute('#srcSpeak', 'title') == 'Прочитать вслух (Японский · Supertonic (мужской 2))',
       'the 🔊 button: ' + (page.get_attribute('#srcSpeak', 'title') or ''))
    n = len(tts_bodies)
    page.click('#srcSpeak')
    page.wait_for_function("speech && speech.audio && !speech.audio.paused && speech.audio.currentTime > 0", timeout=60000)
    body = tts_bodies[n] if len(tts_bodies) > n else {}
    ok(body.get('lang') == 'ja' and body.get('text') == '窓を閉めていただけますか。' and not body.get('voice'), 'request: %s' % body)
    page.screenshot(path=os.path.join(shots, '4-japanese-speaking.png'))
    page.wait_for_function("!document.querySelector('#srcSpeak').classList.contains('speaking')", timeout=60000)
    ok('не удалось' not in toast().lower(), 'no error: ' + toast())

    # ================= reading a chat answer: «Обновить» stops it at once; so does taking the text away
    LONG = 'Поезд уходит рано утром и прибывает в город вечером. ' + 'Мы читаем вслух длинный ответ модели, предложение за предложением. ' * 8
    def bot_answer():
        page.evaluate("(t) => { const m = addAskMsg('bot', ''); renderBot(m, t); addBotMeta(m, t, 'test'); }", LONG)
        page.locator('#askLog .msg.bot button.speak').last.click()
        page.wait_for_function("speech && speech.audio && !speech.audio.paused && speech.audio.currentTime > 0", timeout=60000)
    bot_answer()
    ok(page.locator('#askLog .speak-stop').count() == 1, 'the answer is read, ■ is there')
    page.click('#askReset')
    ok(page.evaluate("() => speech === null") and page.locator('#askLog .msg').count() == 0 and page.locator('.speak-stop').count() == 0,
       '«Обновить» stops reading at once')
    bot_answer()
    page.locator('#askLog .msg.bot button.speak').last.click()   # pause, then wipe: no hidden reading left behind
    page.wait_for_function("speech && speech.paused")
    page.click('#askReset')
    ok(page.evaluate("() => speech === null"), '«Обновить» also ends a paused reading')
    bot_answer()
    page.evaluate("() => document.querySelector('#askLog .msg.bot').remove()")
    try:
        page.wait_for_function("speech === null", timeout=3000); gone = True
    except Exception:
        gone = False
    ok(gone, 'the text taken away from the window: reading stops within a moment')
    page.click('#askReset')

    # ================= delete through the row: every language forgets it, Dmitri stays
    open_menu()
    trash = st_row().locator('button[title="Удалить голос"]')
    trash.click(); page.wait_for_timeout(200)
    ok('ещё раз' in st_row().locator('.sub').first.inner_text(), 'deleting asks for a second click')
    trash.click()
    end = time.time() + 20
    while time.time() < end and os.path.exists(STDIR): time.sleep(0.3)
    act = {v['lang']: v['id'] for v in state()['tts']['voices'] if v['active']}
    ok(not os.path.exists(STDIR) and not any(str(x).startswith('supertonic-') for x in cfg().get('voices', {}).values()) and act == {'ru': 'ru-dmitri'},
       'deleted for all languages; Dmitri stays: %s, %s' % (cfg().get('voices'), act))
    ok(not errs, 'no page errors: %s' % errs[:3])
    b.close()

fails = [r for r in res if r.startswith('FAIL')]
print('\nFAILS: %d of %d' % (len(fails), len(res)))
