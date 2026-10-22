# End-to-end test for v0.9.4: the Spanish voice of the catalogue — the female speaker (F, sid 1) of the two-speaker
# model es_ES-sharvard-medium — with the real sherpa-onnx program and the real voice archive, served by the local
# mirror. The voice's entry (id, folder, model, speaker, size, SHA-256) is the one of tts.go (run_all.sh takes it
# through TestDumpVoiceCatalog); only the address is the mirror's.
#   - the model menu: «Испанский · Sharvard», female, CC BY 3.0; no MLS 9972 anywhere;
#   - download (and sherpa-onnx the first time), the voice is chosen for Spanish in config.json;
#   - /api/tts reads Spanish with speaker F: a female pitch (speaker M of the same model is about 120 Hz, F about
#     200 Hz) and a normal length (es_ES-mls_9972-low of 0.9.3 read «Hola, ¿cómo estás?» in 4–6 s instead of ~1 s);
#   - the 🔊 button of the text field reads Spanish text; deleting the voice removes its folder and the choice.
# Usage: e2e_v094.py <work> <ui_url> <root>   (a ready launcher started with TDOC_TTS_URL and
#        TDOC_TEST_VOICES=voices094.json)
import io, json, os, sys, time, urllib.error, urllib.request, wave
import numpy as np
from playwright.sync_api import sync_playwright
S, URL, ROOT = sys.argv[1], sys.argv[2], sys.argv[3]
shots = os.path.join(S, 'shots', 'v094'); os.makedirs(shots, exist_ok=True)
res = []
def ok(c, m): res.append(('OK  ' if c else 'FAIL') + ' ' + m); print(res[-1], flush=True)
def state():
    return json.load(urllib.request.urlopen(URL.rstrip('/') + '/api/state'))
def tts(text, lang='es'):
    req = urllib.request.Request(URL.rstrip('/') + '/api/tts', data=json.dumps({'lang': lang, 'text': text}).encode(), method='POST',
                                 headers={'Content-Type': 'application/json', 'Origin': URL.rstrip('/')})
    try:
        r = urllib.request.urlopen(req, timeout=120)
        return r.status, r.headers.get('Content-Type', ''), r.headers.get('X-Voice', ''), r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get('Content-Type', ''), '', e.read()
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

with sync_playwright() as pw:
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={'width': 1180, 'height': 860}, locale='ru-RU')
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
    def voice_row(label):
        return page.locator('#modelMenu .mitem', has=page.locator('.title', has_text=label))

    # ================= the catalogue entry
    vs = state()['tts']['voices']
    v = vs[0] if vs else {}
    ok(len(vs) == 1 and v.get('id') == 'es-sharvard-f' and v.get('lang') == 'es' and v.get('name') == 'Sharvard' and v.get('gender') == 'female'
       and v.get('license') == 'CC BY 3.0' and not v.get('nc') and not v.get('present'), 'the Spanish voice: %s' % {k: v.get(k) for k in ('id', 'name', 'gender', 'license', 'nc')})
    ok(v.get('file') == 'vits-piper-es_ES-sharvard-medium.tar.bz2' and len(v.get('parts', [])) == 1, 'one archive, as the other voices: %s' % v.get('file'))
    ok('mls' not in json.dumps(state()['tts']).lower(), 'no MLS voice in /api/state')
    open_menu()
    menu = page.inner_text('#modelMenu')
    sub = voice_row('Испанский · Sharvard').locator('.sub').inner_text()
    ok(voice_row('Испанский · Sharvard').count() == 1 and 'женский голос' in sub and 'CC BY 3.0' in sub and 'MLS' not in menu, 'model menu: ' + sub)

    # ================= download (sherpa-onnx too) and choice for Spanish
    voice_row('Испанский · Sharvard').locator('.pick').click()
    q = page.inner_text('#modelMenu .dl-confirm')
    ok('vits-piper-es_ES-sharvard-medium.tar.bz2' in q and os.path.join(ROOT, 'models', 'voices') in q and 'huggingface' not in q.lower(), 'question: ' + q[:140].replace('\n', ' | '))
    page.locator('#modelMenu .dl-confirm button.primary').click()
    end = time.time() + 300
    while time.time() < end:
        st = state()['tts']
        if st['voices'][0]['present'] and not st['download']['active']: break
        if not st['download']['active'] and st['download'].get('error'): break
        time.sleep(0.5)
    st = state()['tts']
    ok(st['voices'][0]['present'] and st['voices'][0]['active'] and st['engine']['present'], 'voice and sherpa-onnx downloaded: %s' % st['download'])
    cfg = json.load(open(os.path.join(ROOT, 'config.json'), encoding='utf-8'))
    ok(cfg.get('voices') == {'es': 'es-sharvard-f'}, 'chosen for Spanish in config.json: %s' % cfg.get('voices'))
    vd = os.path.join(ROOT, 'models', 'voices', 'vits-piper-es_ES-sharvard-medium')
    ok(all(os.path.exists(os.path.join(vd, f)) for f in ('es_ES-sharvard-medium.onnx', 'tokens.txt', 'espeak-ng-data')), 'voice folder: ' + ', '.join(sorted(os.listdir(vd)) if os.path.isdir(vd) else []))
    page.click('header .brand'); page.wait_for_timeout(200)

    # ================= speaker F, normal length
    code, ctype, xv, body = tts('Hola, ¿cómo estás?')
    ok(code == 200 and ctype == 'audio/wav' and xv == 'es-sharvard-f', '/api/tts: %s %s %s' % (code, ctype, xv))
    if code == 200:
        sr, x = wav(body); sec = len(x) / sr; f0 = pitch(sr, x)
        ok(0.5 < sec < 2.5, '«Hola, ¿cómo estás?» lasts %.2f s (normal ~1 s; MLS 9972 read it in 4–6 s)' % sec)
        ok(f0 > 160, 'female speaker F (sid 1): median pitch %.0f Hz (speaker M is about 120 Hz)' % f0)
    code, ctype, xv, body = tts('Mañana vamos a visitar a mis abuelos en el campo.')
    if code == 200:
        sr, x = wav(body); sec = len(x) / sr
        ok(1.5 < sec < 4.5, 'a longer sentence (49 characters) lasts %.2f s' % sec)
    else:
        ok(False, 'longer sentence: %s %s' % (code, body[:200]))

    # ================= the 🔊 button of the text field reads Spanish
    page.select_option('#srcSel', 'es'); page.select_option('#tgtSel', 'ru')
    page.fill('#src', 'El gato duerme en la casa.'); page.wait_for_timeout(400)
    ok('no-voice' not in (page.get_attribute('#srcSpeak', 'class') or '') and page.get_attribute('#srcSpeak', 'title') == 'Прочитать вслух (Испанский · Sharvard)', 'the 🔊 button: ' + (page.get_attribute('#srcSpeak', 'title') or ''))
    n = len(tts_bodies)
    page.click('#srcSpeak')
    page.wait_for_function("speech && speech.audio && !speech.audio.paused && speech.audio.currentTime > 0", timeout=30000)
    body = tts_bodies[n] if len(tts_bodies) > n else {}
    ok(body.get('lang') == 'es' and body.get('text') == 'El gato duerme en la casa.', 'request: %s' % body)
    page.screenshot(path=os.path.join(shots, '1-spanish-speaking.png'))
    page.wait_for_function("!document.querySelector('#srcSpeak').classList.contains('speaking')", timeout=60000)
    ok('не удалось' not in toast().lower(), 'no error: ' + toast())

    # ================= delete the voice
    open_menu()
    trash = voice_row('Испанский · Sharvard').locator('button[title="Удалить голос"]')
    trash.click(); page.wait_for_timeout(200)
    ok('ещё раз' in voice_row('Испанский · Sharvard').locator('.sub').inner_text(), 'deleting asks for a second click')
    trash.click()
    end = time.time() + 20
    while time.time() < end and os.path.exists(vd): time.sleep(0.3)
    cfg = json.load(open(os.path.join(ROOT, 'config.json'), encoding='utf-8'))
    ok(not os.path.exists(vd) and not cfg.get('voices', {}).get('es'), 'deleted: folder gone, choice forgotten (%s)' % cfg.get('voices'))
    ok(not errs, 'no page errors: %s' % errs[:3])
    b.close()

fails = [r for r in res if r.startswith('FAIL')]
print('\nFAILS: %d of %d' % (len(fails), len(res)))
