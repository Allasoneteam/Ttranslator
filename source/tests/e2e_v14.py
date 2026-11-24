# 1.4 (the author's decision of 24.11.2026: first path A — the Gemma 4 model listens itself, with the same mmproj file
# as for pictures): dictation, speech recordings, the speech test. The model is a stand-in (canned replies); Chromium's
# fake microphone plays a WAV file.
#   - 🎤 at the text field: the first click asks to download the file for pictures and speech (where from, where to,
#     which file) and loads the engine with it — then «Готово: нажмите 🎤 и говорите»; a recording goes to the model as
#     a WAV 16 kHz mono (input_audio) after the transcription prompt, temperature 0; the text goes into the field and,
#     the languages differing («Авто» → «Авто»), is translated at once; under the field: «Речь … → текст за …»;
#   - the same language left and right: only the text, no translation; the language is in the prompt; a dictation
#     after a translation replaces the text, otherwise it goes in at the cursor; Esc cancels a recording;
#   - a speech recording (70 s with pauses) by «Файл»: parts of at most 30 s cut in the pauses, ▶ for each, recognized
#     at once and then translated (the languages differ); «Сохранить .txt» with the parts; a silent recording and an
#     unreadable file — a clear message;
#   - the speech test (Supertonic 3 and sherpa-onnx from the mirror read the phrases): the interface language first,
#     then English; «Стоп» between them, «Продолжить тест речи» goes on; speech-test-<start>.md is rewritten.
# Usage: e2e_v14.py <work> <ui_url> <root>   (the launcher runs with TDOC_TEST_VISION and the test voices)
import sys, json, os, io, re, time, base64, glob, wave, struct, math, urllib.request
from playwright.sync_api import sync_playwright
W, URL, ROOT = sys.argv[1], sys.argv[2].rstrip('/'), sys.argv[3]
shots = os.path.join(W, 'shots', 'v14'); os.makedirs(shots, exist_ok=True)
fx = os.path.join(W, 'v14-fixtures'); os.makedirs(fx, exist_ok=True)
res = []
def ok(c, m): res.append(('OK  ' if c else 'FAIL') + ' ' + m); print(res[-1], flush=True)
def state(): return json.load(urllib.request.urlopen(URL + '/api/state', timeout=10))
def api(path, body):
    req = urllib.request.Request(URL + path, method='POST', data=json.dumps(body).encode(),
                                 headers={'Content-Type': 'application/json', 'Origin': URL})
    try:
        with urllib.request.urlopen(req, timeout=30) as r: return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e: return e.code, {}

# ---------------------------------------------------------------- fixtures
def write_wav(path, rate, x):
    with wave.open(path, 'wb') as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b''.join(struct.pack('<h', int(max(-1, min(1, v)) * 32000)) for v in x))
def voice(rate, sec, t0=0.0):
    # «speech»: two tones with a syllable rhythm (4 Hz), loud enough for the silence trimming of the page
    return [0.35 * (0.6 + 0.4 * math.sin(2 * math.pi * 4 * (t0 + i / rate))) * (math.sin(2 * math.pi * 220 * i / rate) + 0.5 * math.sin(2 * math.pi * 660 * i / rate))
            for i in range(int(rate * sec))]
mic_wav = os.path.join(fx, 'mic.wav')      # the fake microphone (looped by Chromium): 0.6 s quiet, 2.4 s speech
write_wav(mic_wav, 48000, [0.0] * 28800 + voice(48000, 2.4))
long_wav = os.path.join(fx, 'разговор.wav')   # 70 s: 8 s of speech, 1 s of silence, again and again
x = []
while len(x) < 70 * 16000:
    x += voice(16000, 8) + [0.0] * 16000
long_wav_x = x[:70 * 16000]
write_wav(long_wav, 16000, long_wav_x)
quiet_wav = os.path.join(fx, 'тишина.wav')
write_wav(quiet_wav, 16000, [0.0] * 5 * 16000)
bad_mp3 = os.path.join(fx, 'испорчен.mp3')
open(bad_mp3, 'wb').write(b'ID3' + os.urandom(3000))

def wav_info(b64):
    b = base64.b64decode(b64)
    with wave.open(io.BytesIO(b)) as w:
        return w.getframerate(), w.getnchannels(), w.getsampwidth(), w.getnframes() / w.getframerate()

# ---------------------------------------------------------------- the stand-in model
calls = []
asr_next = {'text': 'Проверка диктовки, раз два три.'}
test_phrases = {}   # «Тест речи»: the phrases of each language, from the page
lang_of = {'Russian': 'ru', 'English': 'en'}
def sse(text, prompt_ms=4200, predicted_ms=1300):
    words = text.split(' ')
    body = ''.join('data: ' + json.dumps({'choices': [{'delta': {'content': (w if i == 0 else ' ' + w)}}]}) + '\n\n' for i, w in enumerate(words))
    body += 'data: ' + json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}],
                                   'timings': {'prompt_n': 120, 'prompt_ms': prompt_ms, 'predicted_n': 12, 'predicted_ms': predicted_ms, 'predicted_per_second': 9.2}}) + '\n\ndata: [DONE]\n\n'
    return body
def reply(route):
    body = json.loads(route.request.post_data)
    calls.append(body)
    content = body['messages'][0]['content']
    if isinstance(content, list) and any(p.get('type') == 'input_audio' for p in content):
        prompt = content[0].get('text', '')
        m = re.search(r'speech segment in (\w+) into', prompt)
        lang = lang_of.get(m.group(1)) if m else None
        if lang and test_phrases.get(lang):        # the speech test: the phrase the voice read
            text = test_phrases[lang].pop(0)
        elif asr_next.get('parts'):                 # a recording: the next part
            text = asr_next['parts'].pop(0)
        else:
            text = asr_next['text']
        route.fulfill(status=200, headers={'Content-Type': 'text/event-stream'}, body=sse(text)); return
    src = content.split('\n\n')[-1] if isinstance(content, str) else ''
    route.fulfill(status=200, headers={'Content-Type': 'text/event-stream'}, body=sse('EN[' + str(len(src)) + '] ' + src[:30]))
audio_calls = lambda: [c for c in calls if isinstance(c['messages'][0]['content'], list) and any(p.get('type') == 'input_audio' for p in c['messages'][0]['content'])]
text_calls = lambda: [c for c in calls if isinstance(c['messages'][0]['content'], str)]

def wait(fn, timeout=30):
    # page.wait_for_timeout, not time.sleep: the canned replies (page.route) are answered only while Playwright runs
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            if fn(): return True
        except Exception: pass
        page.wait_for_timeout(250)
    return False

with sync_playwright() as pw:
    b = pw.chromium.launch(args=['--use-fake-ui-for-media-stream', '--use-fake-device-for-media-stream',
                                 '--use-file-for-fake-audio-capture=' + mic_wav, '--autoplay-policy=no-user-gesture-required'])
    ctx = b.new_context(viewport={'width': 1280, 'height': 900}, locale='ru-RU', accept_downloads=True)
    ctx.add_init_script("try { sessionStorage.setItem('tdoc.window', '1'); sessionStorage.setItem('tdoc.welcome', 'done') } catch (e) {}")
    page = ctx.new_page(); errs = []
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.route('**/v1/chat/completions', reply)
    page.goto(URL + '/'); page.wait_for_selector('body[data-model="ready"]', timeout=20000)
    page.evaluate('() => { window.showSaveFilePicker = undefined; }')

    # ================= 🎤: the first click — the file for pictures and speech
    mb = page.locator('#micBtn')
    ok(mb.is_visible() and mb.get_attribute('title').startswith('Диктовка: нажмите и говорите') and mb.locator('svg').count() == 1,
       'the 🎤 button next to 🔊 under the text field')
    ok(page.evaluate("document.querySelector('#micBtn').nextElementSibling.id") == 'srcSpeak', '🎤 stands right before 🔊')
    mb.click()
    page.wait_for_selector('#mainView .dl-confirm')
    cf = page.inner_text('#mainView .dl-confirm')
    ok('Чтобы слушать речь' in cf and 'Test · картинки и речь' in cf and 'mmproj-test.gguf' in cf and 'http://127.0.0.1:18080/mmproj-test.gguf' in cf and '0,6 ГБ' in cf,
       'asks first: where from, where to, which file: ' + cf.replace('\n', ' | ')[:200])
    ok(page.evaluate("document.querySelector('#mainView .dl-confirm').previousElementSibling.id") == 'srcTools', 'the question stands under the row of 🎤')
    page.screenshot(path=os.path.join(shots, '1-confirm.png'))
    page.locator('#mainView .dl-confirm button.primary').click()
    ok(wait(lambda: 'Готово: нажмите 🎤 и говорите' in page.inner_text('#cleanNote'), 90), 'downloaded and loaded: ' + page.inner_text('#cleanNote'))
    st = state()
    ok(st['vision']['loaded'] and st['vision']['on'], 'the engine has the file for pictures and speech')
    ok(not audio_calls(), 'nothing recorded yet — no speech went to the model')

    # ================= 🎤: a recording → text → translation (the languages differ: «Авто» → «Авто»)
    mb.click()
    ok(wait(lambda: 'rec' in mb.get_attribute('class') and 'Запись 0:0' in page.inner_text('#cleanNote'), 10), 'recording: ' + page.inner_text('#cleanNote'))
    page.wait_for_timeout(2600)
    page.screenshot(path=os.path.join(shots, '2-recording.png'))
    mb.click()
    ok(wait(lambda: audio_calls(), 30), 'the recording went to the model')
    req = audio_calls()[-1]
    parts = req['messages'][0]['content']
    ok(parts[0]['type'] == 'text' and parts[0]['text'].startswith('Transcribe the following speech segment in its original language.')
       and 'Only output the transcription, with no newlines.' in parts[0]['text'], 'the prompt (Google, Gemma 4), «Авто» — no language: ' + parts[0]['text'][:80])
    ok(parts[1]['type'] == 'input_audio' and parts[1]['input_audio']['format'] == 'wav', 'the sound: input_audio, WAV')
    sr, ch, sw, sec = wav_info(parts[1]['input_audio']['data'])
    ok(sr == 16000 and ch == 1 and sw == 2 and 0.8 < sec < 3.4, 'WAV 16 kHz, mono, 16 bit, %.2f s (the quiet start cut off)' % sec)
    ok(req['temperature'] == 0 and req['top_k'] == 1 and req['max_tokens'] == 400 and req['repeat_penalty'] == 1.0, 'temperature 0, no repeat penalty, 400 tokens')
    ok(wait(lambda: page.input_value('#src') == 'Проверка диктовки, раз два три.', 10), 'the text is in the field: ' + page.input_value('#src'))
    ok(wait(lambda: text_calls() and page.locator('#cards .card').count() > 0, 30), 'translated at once (Russian → English): %d requests' % len(text_calls()))
    note = page.inner_text('#cleanNote')
    ok(re.search(r'Речь \d+,\d с → текст за \d+,\d с \(звук 4,2 с, текст 1,3 с\)', note) is not None, 'under the field: ' + note)
    ok('rec' not in mb.get_attribute('class'), '🎤 is not red any more')
    cy, my = page.locator('#counter').bounding_box()['y'], mb.bounding_box()['y']
    ok(page.evaluate("document.querySelector('#cleanNote').classList.contains('own-line')") and abs(cy - my) < 12,
       'the long line under the field stands on its own line; the counter stays in the row of 🎤: %.0f / %.0f' % (cy, my))
    page.screenshot(path=os.path.join(shots, '3-translated.png'))
    page.wait_for_selector('#goBtn:not([hidden])', timeout=30000)

    # ================= the same language left and right: only the text; a dictation after a translation replaces it
    page.select_option('#srcSel', 'ru'); page.select_option('#tgtSel', 'ru')
    n0 = len(text_calls())
    asr_next['text'] = 'Второй текст без перевода.'
    mb.click(); page.wait_for_timeout(1500); mb.click()
    ok(wait(lambda: page.input_value('#src') == 'Второй текст без перевода.', 20), 'the translated text is replaced: ' + page.input_value('#src'))
    ok('in Russian into Russian text.' in audio_calls()[-1]['messages'][0]['content'][0]['text'], 'the language of the speech is in the prompt')
    page.wait_for_timeout(1500)
    ok(len(text_calls()) == n0, 'the same language: no translation, only the text in the field')
    # not translated yet — the next dictation goes in at the cursor
    page.fill('#src', 'Начало.')
    page.evaluate("() => { const f = document.querySelector('#src'); f.setSelectionRange(7, 7); }")
    asr_next['text'] = 'Продолжение.'
    mb.click(); page.wait_for_timeout(1500); mb.click()
    ok(wait(lambda: page.input_value('#src') == 'Начало. Продолжение.', 20), 'added at the cursor, with a space: ' + page.input_value('#src'))
    # Esc cancels a recording: nothing goes to the model
    na = len(audio_calls())
    mb.click(); page.wait_for_timeout(800)
    page.keyboard.press('Escape')
    page.wait_for_timeout(1200)
    ok(len(audio_calls()) == na and 'rec' not in mb.get_attribute('class') and page.inner_text('#cleanNote') == '', 'Esc: the recording is cancelled')
    page.select_option('#srcSel', 'auto'); page.select_option('#tgtSel', 'auto')

    # ================= the model menu says the file listens too
    page.click('#modelBtn'); page.wait_for_selector('#modelMenu:not([hidden])')
    menu = page.inner_text('#modelMenu')
    i = menu.find('Картинки и речь')
    ok('работает: модель читает картинки и слушает речь' in menu, 'the model menu: the file reads pictures and listens to speech: ' + menu[i:i + 160].replace('\n', ' | '))
    page.keyboard.press('Escape')

    # ================= a speech recording: parts cut in the pauses, recognized at once, then translated
    calls.clear()
    asr_next['parts'] = ['Первая часть разговора.', 'Вторая часть разговора.', 'Третья часть разговора.']
    page.set_input_files('#fileInput', long_wav)
    page.wait_for_selector('#docView:not([hidden]) .doc-page')
    heads = page.locator('.doc-page .doc-page-head b').all_inner_texts()
    plays = page.locator('.doc-page .doc-audio button').all_inner_texts()
    ok(heads == ['Часть 1', 'Часть 2', 'Часть 3'], 'three parts: %s' % heads)
    ok(len(plays) == 3 and plays[0].strip().startswith('0:00–0:2') and plays[2].strip().endswith('1:10'), '▶ with the time of each part: %s' % plays)
    ok(page.locator('.doc-page.has-audio').count() == 3 and page.locator('.doc-page .doc-img').count() == 0, 'no pictures — ▶ instead')
    ok(wait(lambda: all(page.locator('.doc-page .doc-src').nth(i).input_value() for i in range(3)), 40), 'recognized at once, part after part')
    ac = audio_calls()
    secs = [wav_info(c['messages'][0]['content'][1]['input_audio']['data'])[3] for c in ac]
    ok(len(ac) == 3 and all(s <= 30.0 for s in secs) and abs(sum(secs) - 70) < 3, 'three requests, each at most 30 s: %s' % ['%.1f' % s for s in secs])
    ok(page.locator('.doc-page .doc-src').nth(1).input_value() == 'Вторая часть разговора.', 'the text of part 2')
    ok(wait(lambda: len(text_calls()) >= 3 and all(page.locator('.doc-page .doc-tgt').nth(i).inner_text().startswith('EN[') for i in range(3)), 40),
       'then translated (the languages differ): %d requests' % len(text_calls()))
    meta = page.inner_text('.doc-page .doc-meta >> nth=0')
    ok('часть записи' in meta and 'распознано за' in meta and 'звук 4,2 с, текст 1,3 с' in meta, 'the meta of a part: ' + meta)
    page.screenshot(path=os.path.join(shots, '4-recording-parts.png'))
    pb = page.locator('.doc-page .doc-audio button').nth(0)
    pb.click()
    ok(wait(lambda: 'on' in pb.get_attribute('class'), 5), '▶ plays the part')
    pb.click()
    ok(wait(lambda: 'on' not in pb.get_attribute('class'), 5), 'and stops on the second click')
    with page.expect_download() as dl:
        page.click('#docSaveBtn')
    data = open(dl.value.path(), 'rb').read().decode('utf-8-sig')
    ok(dl.value.suggested_filename == 'разговор (английский).txt' and '— Часть 2 (0:26–0:44) —' in data and data.count('EN[') == 3,
       'saved .txt: %s; parts with their time: %s' % (dl.value.suggested_filename, data[:60].replace('\r\n', ' | ')))
    page.check('#docWithSrc')
    with page.expect_download() as dl:
        page.click('#docSaveBtn')
    data = open(dl.value.path(), 'rb').read().decode('utf-8-sig')
    ok('Вторая часть разговора.' in data, 'with the original: the recognized text too')
    page.uncheck('#docWithSrc')

    # silence and an unreadable file
    page.set_input_files('#fileInput', quiet_wav)
    ok(wait(lambda: 'в файле нет звука' in page.inner_text('#docNote'), 10), 'a silent recording: ' + page.inner_text('#docNote'))
    page.set_input_files('#fileInput', bad_mp3)
    ok(wait(lambda: 'звук этого файла не прочитать' in page.inner_text('#docNote'), 10), 'an unreadable file: ' + page.inner_text('#docNote')[:90])
    page.click('#closeDocBtn')

    # ================= the speech test: Supertonic reads, the model (canned) answers the phrase
    code, _ = api('/api/voice', {'id': 'supertonic-ru'})
    t0 = time.time()
    def tts_ready():
        s = state()['tts']
        return s['engine']['present'] and not s['download']['active'] and all(v['present'] for v in s['voices'] if v.get('engine') == 'supertonic')
    while time.time() - t0 < 600 and not tts_ready():
        time.sleep(1)
    ok(code == 200 and state()['tts']['engine']['present'], 'Supertonic 3 and sherpa-onnx downloaded (from the mirror)')
    page.reload(); page.wait_for_selector('body[data-model="ready"]', timeout=20000)
    phrases = page.evaluate('LISTEN_TEST')
    ok(len(phrases) == 15 and all(len(v) == 4 for v in phrases.values()), 'LISTEN_TEST: four phrases in each of the 15 languages')
    test_phrases['ru'] = list(phrases['ru']); test_phrases['en'] = list(phrases['en'])
    page.click('#testBtn')
    ok(wait(lambda: page.is_visible('#speechTestBtn') and 'Тест речи' in page.inner_text('#testIntro'), 10), 'the test pane: «Тест речи» and its description')
    calls.clear()
    page.click('#speechTestBtn')
    ok(page.inner_text('#speechTestBtn') == 'Остановить', 'the button stops the test while it runs')
    ok(wait(lambda: page.locator('#testSummary table tbody tr').count() >= 1, 180), 'the first language is done')
    page.click('#speechTestBtn')   # stop: during English (or between the languages)
    ok(wait(lambda: page.inner_text('#speechTestBtn') == 'Продолжить тест речи', 30), 'stopped — the button continues: ' + page.inner_text('#speechTestBtn'))
    row = page.inner_text('#testSummary table tbody tr >> nth=0')
    ok(row.startswith('Русский') and '0,0 %' in row and 'Русский · ' not in row, 'the interface language first, no wrong characters: ' + row.replace('\t', ' | '))
    first = audio_calls()[0]['messages'][0]['content']
    sr, ch, sw, sec = wav_info(first[1]['input_audio']['data'])
    ok('in Russian into Russian text.' in first[0]['text'] and sr == 16000 and 2 < sec < 12, 'a phrase read by the voice: 16 kHz, %.1f s' % sec)
    reps = glob.glob(os.path.join(ROOT, 'data', 'reports', 'speech-test-*.md'))
    rep = open(reps[0], encoding='utf-8').read() if len(reps) == 1 else ''
    ok(len(reps) == 1 and '# Тест речи' in rep and '| Русский |' in rep and 'Читал голос:' in rep and os.path.exists(reps[0][:-3] + '.json'),
       'the report after the first language: %s' % [os.path.basename(r) for r in reps])
    page.screenshot(path=os.path.join(shots, '5-speech-test.png'))
    test_phrases['en'] = list(phrases['en'])
    page.click('#speechTestBtn')   # continue: English
    ok(wait(lambda: page.locator('#testSummary table tbody tr').count() >= 2, 180), 'continued: the second language is done')
    page.click('#speechTestBtn')
    ok(wait(lambda: page.inner_text('#speechTestBtn') == 'Продолжить тест речи', 30), 'stopped again')
    rows = page.locator('#testSummary table tbody tr').all_inner_texts()
    ok(rows[1].startswith('Английский') and '0,0 %' in rows[1], 'then English: ' + rows[1].replace('\t', ' | '))
    reps2 = glob.glob(os.path.join(ROOT, 'data', 'reports', 'speech-test-*.md'))
    rep = open(reps2[0], encoding='utf-8').read() if reps2 else ''
    ok(reps2 == reps and '| Английский |' in rep and '| Русский |' in rep, 'the same report, now with two languages')
    j = json.load(open(reps2[0][:-3] + '.json', encoding='utf-8'))
    ok(j['kind'] == 'speech' and [x['lang'] for x in j['langs']][:2] == ['ru', 'en'] and j['sampling']['temperature'] == 0, 'the JSON report: languages and parameters')
    ok(not errs, 'no page errors: %s' % errs[:3])
    b.close()

print('FAILS: %d of %d' % (sum(r.startswith('FAIL') for r in res), len(res)))
