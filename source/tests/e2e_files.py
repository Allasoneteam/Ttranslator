# 1.3 (the author's choice of 18.11.2026: pictures and scans first): a document — a picture, a PDF or a text file —
# with the text of each page and its translation side by side (the «Файл» button).
#   - the PDF.js files are served with JavaScript and WebAssembly types;
#   - a picture (PNG): one page; «Распознать» asks to download the picture file of the model (from the mirror; where
#     from, where to, which file) — then the engine restarts with it (here a stand-in: TDOC_TEST_VISION, the engine is
#     not given the file) and the page goes to the model as a JPEG with the transcription request (temperature 0);
#   - «Перевести»: by paragraphs (two parts for a long page), the same translation request as the main window;
#     a changed text makes the translation out of date; «Сохранить .txt» (with the original);
#   - a PDF of two pages: the text page is read by PDF.js (no model), the scan page by the model; small pictures of
#     the pages; a PDF made of a photo; a text file in UTF-8 and one in Windows-1251; a picture pasted (Ctrl+V) and a
#     file dropped into the window;
#   - «Стоп» while the real engine translates; the model menu shows the picture file (✓ while in use); deleting it —
#     the engine restarts without it, and «Распознать» asks again;
#   - the second test model has a broken picture file that the real engine is given: it cannot load it and stops —
#     the launcher starts it again without the file, the window says so (with the engine's words) and translates.
# Usage: e2e_files.py <work> <ui_url> <root>   (the launcher runs with TDOC_TEST_VISION, see run_all.sh)
import sys, json, os, io, time, base64, hashlib, struct, zlib, urllib.request
from playwright.sync_api import sync_playwright
from PIL import Image, ImageDraw
W, URL, ROOT = sys.argv[1], sys.argv[2].rstrip('/'), sys.argv[3]
shots = os.path.join(W, 'shots', 'files'); os.makedirs(shots, exist_ok=True)
fx = os.path.join(W, 'files-fixtures'); os.makedirs(fx, exist_ok=True)
res = []
def ok(c, m): res.append(('OK  ' if c else 'FAIL') + ' ' + m); print(res[-1], flush=True)
def get(path):
    with urllib.request.urlopen(URL + path, timeout=10) as r: return r.status, r.headers.get('Content-Type', ''), r.read()
def state(): return json.loads(get('/api/state')[2])
def api(method, path, body=None):
    req = urllib.request.Request(URL + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={'Content-Type': 'application/json', 'Origin': URL})
    try:
        with urllib.request.urlopen(req, timeout=10) as r: return r.status, json.loads(r.read() or b'{}')
    except urllib.error.HTTPError as e: return e.code, {}

# ---------------------------------------------------------------- fixtures
def page_png(path, lines, size=(900, 1200)):
    im = Image.new('RGB', size, 'white'); d = ImageDraw.Draw(im)
    for i, l in enumerate(lines): d.text((60, 80 + 40 * i), l, fill='black')
    im.save(path)
    return im
png = os.path.join(fx, 'scan.png')
im = page_png(png, ['A scanned page', 'with two lines of text'])
jpg = io.BytesIO(); im.convert('RGB').save(jpg, 'JPEG', quality=80); jpg = jpg.getvalue()
photo_pdf = os.path.join(fx, 'photo.pdf')
Image.open(png).convert('RGB').save(photo_pdf)   # a PDF that is only a picture — as a scanner makes it

def two_page_pdf(path):
    # page 1: real text (Helvetica, two paragraphs); page 2: a JPEG picture only (a scan)
    text = ('BT /F1 14 Tf 72 720 Td 18 TL (The first paragraph of the text page) Tj T* (continues on this line.) Tj '
            '0 -40 Td (A second paragraph after a gap.) Tj ET')
    objs = [b'<< /Type /Catalog /Pages 2 0 R >>',
            b'<< /Type /Pages /Kids [3 0 R 4 0 R] /Count 2 >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 5 0 R >> >> /Contents 6 0 R >>',
            b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /XObject << /Im1 7 0 R >> >> /Contents 8 0 R >>',
            b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>',
            b'<< /Length %d >>\nstream\n' % len(text) + text.encode() + b'\nendstream',
            b'<< /Type /XObject /Subtype /Image /Width 900 /Height 1200 /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length %d >>\nstream\n' % len(jpg) + jpg + b'\nendstream',
            None]
    draw = b'q 612 0 0 792 0 0 cm /Im1 Do Q'
    objs[7] = b'<< /Length %d >>\nstream\n' % len(draw) + draw + b'\nendstream'
    out = b'%PDF-1.4\n'
    offs = []
    for i, o in enumerate(objs):
        offs.append(len(out)); out += b'%d 0 obj\n' % (i + 1) + o + b'\nendobj\n'
    x = len(out)
    out += b'xref\n0 %d\n0000000000 65535 f \n' % (len(objs) + 1) + b''.join(b'%010d 00000 n \n' % o for o in offs)
    out += b'trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n' % (len(objs) + 1, x)
    open(path, 'wb').write(out)
mixed_pdf = os.path.join(fx, 'mixed.pdf'); two_page_pdf(mixed_pdf)
txt8 = os.path.join(fx, 'заметка.txt')
open(txt8, 'w', encoding='utf-8').write('Первый абзац текстового файла.\nОн продолжается на второй строке.\n\nВторой абзац.\n')
txt1251 = os.path.join(fx, 'old-1251.txt')
open(txt1251, 'wb').write('Старый текст в кодировке Windows-1251: ёлка, щука, Москва.'.encode('cp1251'))

OCR = ('Отсканированная страница: первый абзац текста, который модель прочитала с картинки.\n\n'
       + 'Второй абзац — длинный. ' + 'Это предложение повторяется, чтобы страница не поместилась в один кусок перевода. ' * 14
       + '\n\nТретий абзац с формулой $E = mc^2$.')
calls = []
def sse(text):
    words = text.split(' ')
    body = ''.join('data: ' + json.dumps({'choices': [{'delta': {'content': (w if i == 0 else ' ' + w)}}]}) + '\n\n' for i, w in enumerate(words))
    body += 'data: ' + json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}],
                                   'timings': {'prompt_n': 1130, 'prompt_ms': 9000, 'predicted_n': 300, 'predicted_ms': 21000, 'predicted_per_second': 14.3}}) + '\n\ndata: [DONE]\n\n'
    return body
hold = {'on': False, 'routes': []}
def reply(route):
    body = json.loads(route.request.post_data)
    calls.append(body)
    content = body['messages'][0]['content']
    if isinstance(content, list):   # a page as a picture
        route.fulfill(status=200, headers={'Content-Type': 'text/event-stream'}, body=sse(OCR)); return
    if hold['on']:                  # the model «thinks»: no answer until the test lets it go
        hold['routes'].append(route); return
    src = content.split('\n\n')[-1]
    route.fulfill(status=200, headers={'Content-Type': 'text/event-stream'}, body=sse('EN[' + str(len(src)) + '] ' + src[:30]))

# ---------------------------------------------------------------- the PDF.js files
st, ct, b = get('/pdfjs/pdf.min.mjs')
ok(st == 200 and ct.startswith('text/javascript') and b'GlobalWorkerOptions' in b, 'pdf.min.mjs: %s %s, %d bytes' % (st, ct, len(b)))
st, ct, b = get('/pdfjs/pdf.worker.min.mjs')
ok(st == 200 and ct.startswith('text/javascript') and len(b) > 500000, 'pdf.worker.min.mjs: %s %s' % (st, ct))
st, ct, b = get('/pdfjs/wasm/jbig2.wasm')
ok(st == 200 and ct == 'application/wasm' and b[:4] == b'\0asm', 'jbig2.wasm: %s %s' % (st, ct))
s0 = state()
v0 = s0.get('vision') or {}
ok(v0.get('current') == 'mm-test' and not v0.get('loaded') and not v0.get('on') and v0['files'][0]['present'] is False and v0.get('tokens') == 1120,
   'the picture file of the test model: not downloaded, not in use: %s' % {k: v0.get(k) for k in ('current', 'on', 'loaded')})

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
    b = pw.chromium.launch()
    ctx = b.new_context(viewport={'width': 1280, 'height': 900}, locale='ru-RU', accept_downloads=True)
    ctx.add_init_script("try { sessionStorage.setItem('tdoc.window', '1'); sessionStorage.setItem('tdoc.welcome', 'done') } catch (e) {}")
    page = ctx.new_page(); errs = []
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.route('**/v1/chat/completions', reply)
    page.goto(URL + '/'); page.wait_for_selector('body[data-model="ready"]', timeout=20000)
    page.evaluate('() => { window.showSaveFilePicker = undefined; }')   # «Сохранить .txt»: a download instead of the dialog
    ok(page.locator('#fileBtn').is_visible() and page.inner_text('#fileLabel') == 'Файл', 'the «Файл» button under the text field')

    # ================= a picture: one page, the model needs its picture file
    page.set_input_files('#fileInput', png)
    page.wait_for_selector('#docView:not([hidden]) .doc-page')
    ok(page.locator('.doc-page').count() == 1 and page.inner_text('#docName') == 'scan.png' and page.evaluate("document.body.classList.contains('doc-open')"),
       'the document view, full width, one page')
    ok(page.get_attribute('.doc-page .doc-img img', 'src').startswith('data:image/jpeg') and 'картинка' in page.inner_text('.doc-page .doc-meta'),
       'a small picture of the page; «картинка»')
    ok(page.is_visible('#docReadBtn') and 'ещё один файл' in page.inner_text('#docNote'), 'hint: the model needs one more file: ' + page.inner_text('#docNote'))
    page.screenshot(path=os.path.join(shots, '1-picture.png'))
    page.click('#docReadBtn')
    page.wait_for_selector('#docView .dl-confirm')
    cf = page.inner_text('#docView .dl-confirm')
    ok('Test · картинки и речь' in cf and 'http://127.0.0.1:18080/mmproj-test.gguf' in cf and 'mmproj-test.gguf' in cf and '0,6 ГБ' in cf,
       'asks first: where from, where to, which file: ' + cf.replace('\n', ' | ')[:200])
    page.screenshot(path=os.path.join(shots, '2-confirm.png'))
    page.locator('#docView .dl-confirm button.primary').click()
    ok(wait(lambda: any(isinstance(c['messages'][0]['content'], list) for c in calls), 60), 'downloaded, the engine restarted, the page went to the model')
    st1 = state()
    ok(st1['vision']['loaded'] and st1['vision']['on'] and st1['vision']['files'][0]['present'] and st1['engine_info']['vision'],
       'the engine reads pictures now: %s' % {k: st1['vision'].get(k) for k in ('on', 'loaded')})
    log = open(os.path.join(ROOT, 'data', 'logs', 'launcher.log'), encoding='utf-8', errors='replace').read()
    ok('picture file installed: mmproj-test.gguf' in log and 'engine restarts to read pictures' in log, 'the launcher log: installed, restarted')
    req = [c for c in calls if isinstance(c['messages'][0]['content'], list)][0]
    parts = req['messages'][0]['content']
    ok(parts[0]['type'] == 'image_url' and parts[0]['image_url']['url'].startswith('data:image/jpeg;base64,') and parts[1]['text'].startswith('Transcribe all the text in this picture')
       and req['temperature'] == 0 and req['top_k'] == 1 and req['max_tokens'] == 2600, 'the request: a JPEG and the transcription prompt, temperature 0, 2600 tokens')
    jpeg = base64.b64decode(parts[0]['image_url']['url'].split(',', 1)[1])
    pim = Image.open(io.BytesIO(jpeg))
    ok(max(pim.size) == 1200 and pim.format == 'JPEG', 'the picture as it is (not enlarged): %s' % (pim.size,))
    page.wait_for_function("document.querySelector('.doc-page .doc-src').value.startsWith('Отсканированная страница')")
    page.wait_for_selector('#docTransBtn:not([hidden])')
    ok(page.is_hidden('#docReadBtn'), '«Распознать» at the top is gone: no page is left without text')
    h = page.evaluate("document.querySelector('.doc-page .doc-src').offsetHeight")
    ok(h > 250, 'the text field of the page grows with the text (the whole page is seen): %d px' % h)
    meta = page.inner_text('.doc-page .doc-meta')
    ok('распознано за' in meta and 'картинка 9,0 с, текст 21,0 с' in meta and '1 293 знака' in meta.replace('\u00a0', ' '), 'the page meta: ' + meta)
    ok(page.input_value('.doc-page .doc-src').count('\n\n') == 2, 'three paragraphs in the text of the page')
    page.screenshot(path=os.path.join(shots, '3-recognized.png'))

    # ================= translation by parts; an edit makes it out of date; save
    calls.clear()
    page.click('#docTransBtn')
    page.wait_for_function("document.querySelector('.doc-page .doc-tgt').textContent.startsWith('EN[')")
    page.wait_for_selector('#docTransBtn:not([hidden])')
    tr = [c for c in calls if isinstance(c['messages'][0]['content'], str)]
    nchunks = page.evaluate("docChunks(DOC.pages[0].src).length")
    ok(nchunks >= 3 and len(tr) == nchunks and all('into English' in c['messages'][0]['content'] for c in tr),
       'by parts, with the translation prompt of the main window: %d requests, %d parts' % (len(tr), nchunks))
    ok(all(len(c['messages'][0]['content'].split('\n\n', 1)[1]) <= 900 + 200 for c in tr), 'parts of up to 900 characters')
    ok('{F1}' in tr[-1]['messages'][0]['content'] and '$E = mc^2$' not in tr[-1]['messages'][0]['content'], 'the formula goes to the model as a mark')
    tgt = page.inner_text('.doc-page .doc-tgt')
    ok(tgt.count('EN[') == nchunks and '\n\n' in tgt and 'переведено за' in page.inner_text('.doc-page .doc-meta'), 'the translation: all parts, joined; meta')
    page.fill('.doc-page .doc-src', page.input_value('.doc-page .doc-src') + ' Ещё.')
    ok('перевод устарел' in page.inner_text('.doc-page .doc-meta'), 'an edit: the translation is out of date')
    page.check('#docWithSrc')
    with page.expect_download() as dl:
        page.click('#docSaveBtn')
    d = dl.value
    data = open(d.path(), 'rb').read().decode('utf-8-sig')
    ok(d.suggested_filename == 'scan (английский).txt' and data.startswith('Отсканированная страница') and 'EN[' in data and '\r\n' in data,
       'saved: %s, %d characters' % (d.suggested_filename, len(data)))

    # ================= a PDF: a text page (PDF.js, no model) and a scan page (the model)
    calls.clear()
    page.set_input_files('#fileInput', mixed_pdf)
    page.wait_for_function("document.querySelectorAll('.doc-page').length === 2", timeout=20000)
    pg = page.locator('.doc-page')
    t1 = pg.nth(0).locator('.doc-src').input_value()
    ok(t1 == 'The first paragraph of the text page continues on this line.\n\nA second paragraph after a gap.', 'page 1: the text of the PDF, two paragraphs: %r' % t1)
    ok('текст из PDF' in pg.nth(0).locator('.doc-meta').inner_text() and pg.nth(0).locator('button', has_text='Распознать').is_hidden()
       and 'картинка' in pg.nth(1).locator('.doc-meta').inner_text() and pg.nth(1).locator('.doc-src').input_value() == '',
       'page 2: a scan, no text yet')
    ok(wait(lambda: page.evaluate("[...document.querySelectorAll('.doc-page .doc-img img')].every(i => (i.getAttribute('src') || '').startsWith('data:image/jpeg'))"), 20),
       'small pictures of both pages (PDF.js draws them)')
    ok(not calls, 'opening a PDF asks the model nothing')
    page.click('#docReadBtn')
    page.wait_for_function("document.querySelectorAll('.doc-page .doc-src')[1].value.startsWith('Отсканированная')", timeout=20000)
    page.wait_for_selector('#docTransBtn:not([hidden])')
    ocr = [c for c in calls if isinstance(c['messages'][0]['content'], list)]
    ok(len(ocr) == 1 and not page.locator('#docView .dl-confirm').count(), 'only the scan page went to the model (the file is there: no question)')
    pim = Image.open(io.BytesIO(base64.b64decode(ocr[0]['messages'][0]['content'][0]['image_url']['url'].split(',', 1)[1])))
    ok(max(pim.size) == 1600, 'the scan page drawn at 1600 pixels: %s' % (pim.size,))
    page.screenshot(path=os.path.join(shots, '4-pdf.png'), full_page=True)
    # «Стоп» while the model translates
    hold['on'] = True
    page.click('#docTransBtn')
    page.wait_for_selector('#docStopBtn:not([hidden])')
    ok(wait(lambda: hold['routes'], 10), 'a translation request is under way')
    page.click('#docStopBtn')
    page.wait_for_selector('#docTransBtn:not([hidden])', timeout=10000)
    ok(page.evaluate('() => docCtl === null') and page.is_hidden('#docStopBtn') and not page.locator('.doc-page.working').count(), '«Стоп»: stopped, the buttons are back')
    hold['on'] = False
    for r in hold['routes']:
        try: r.abort()
        except Exception: pass

    # ================= a PDF made of a photo; text files; paste and drop
    page.set_input_files('#fileInput', photo_pdf)
    page.wait_for_function("document.querySelectorAll('.doc-page').length === 1 && document.querySelector('.doc-page .doc-meta').textContent.includes('картинка')", timeout=20000)
    ok(True, 'a PDF made of a photo: one scan page')
    page.set_input_files('#fileInput', txt8)
    page.wait_for_function("(() => { const e = document.querySelector('.doc-page .doc-src'); return document.querySelector('#docName').textContent === 'заметка.txt' && !!e && !!e.value; })()")
    ok(page.input_value('.doc-page .doc-src') == 'Первый абзац текстового файла. Он продолжается на второй строке.\n\nВторой абзац.'
       and page.locator('.doc-page .doc-img').count() == 0 and page.inner_text('#docName') == 'заметка.txt', 'a text file in UTF-8: the lines of a paragraph joined')
    page.set_input_files('#fileInput', txt1251)
    page.wait_for_function("(() => { const e = document.querySelector('.doc-page .doc-src'); return !!e && e.value.includes('Москва'); })()")
    ok(page.input_value('.doc-page .doc-src') == 'Старый текст в кодировке Windows-1251: ёлка, щука, Москва.', 'a text file in Windows-1251')
    page.click('#closeDocBtn')
    ok(page.is_hidden('#docView') and page.inner_text('#fileLabel') == 'Документ', 'back to the main window; «Файл» became «Документ»')
    page.click('#fileBtn')
    ok(page.is_visible('#docView') and page.inner_text('#docName') == 'old-1251.txt', '«Документ» returns to it')
    page.click('#closeDocBtn')
    b64 = base64.b64encode(open(png, 'rb').read()).decode()
    page.evaluate("""(b) => { const bytes = Uint8Array.from(atob(b), c => c.charCodeAt(0));
      const dt = new DataTransfer(); dt.items.add(new File([bytes], 'clip.png', { type: 'image/png' }));
      document.querySelector('#src').dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true })); }""", b64)
    page.wait_for_function("document.querySelector('#docName').textContent === 'Снимок экрана.png' && document.querySelectorAll('.doc-page').length === 1", timeout=15000)
    ok(page.is_visible('#docView') and page.locator('.doc-page .doc-img').count() == 1, 'a pasted picture opens as a document')
    page.evaluate("""() => { const dt = new DataTransfer(); dt.items.add(new File(['Перетащенный текст.'], 'drop.txt', { type: 'text/plain' }));
      document.body.dispatchEvent(new DragEvent('drop', { dataTransfer: dt, bubbles: true, cancelable: true })); }""")
    page.wait_for_function("document.querySelector('#docName').textContent === 'drop.txt'")
    ok(page.input_value('.doc-page .doc-src') == 'Перетащенный текст.', 'a dropped file opens')
    ok('.pdf' in page.get_attribute('#fileInput', 'accept') and 'image/*' in page.get_attribute('#fileInput', 'accept'), 'the file picker offers pictures, PDF, text')

    # ================= the model menu; deleting the picture file
    page.click('#closeDocBtn')
    page.click('#modelBtn'); page.wait_for_selector('#modelMenu:not([hidden])')
    menu = page.inner_text('#modelMenu')
    ok('Картинки и речь для Gemma 4 (файлы mmproj)' in menu and '✓ Test · картинки и речь' in menu and 'работает: модель читает картинки' in menu,
       'the model menu: the picture file, in use')
    page.screenshot(path=os.path.join(shots, '5-menu.png'))
    page.keyboard.press('Escape')
    code, _ = api('DELETE', '/api/vision/mm-test')
    ok(code == 200 and wait(lambda: state()['phase'] == 'ready' and not state()['vision']['loaded'], 40), 'deleted: the engine works again without it')
    ok(not os.path.exists(os.path.join(ROOT, 'models', 'mmproj-test.gguf')), 'the file is gone')
    page.set_input_files('#fileInput', png)
    page.wait_for_selector('#docView:not([hidden]) .doc-page')
    page.wait_for_function("STATE && STATE.vision && !STATE.vision.loaded", timeout=15000)
    calls.clear()
    page.click('#docReadBtn')
    page.wait_for_selector('#docView .dl-confirm')
    page.locator('#docView .dl-confirm button', has_text='Отмена').click()
    page.wait_for_selector('#docReadBtn:not([hidden])')
    ok(not calls and not page.locator('#docView .dl-confirm').count(), '«Распознать» asks again; «Отмена» — nothing is sent')

    # ================= a picture file the engine cannot load: the model goes on without pictures
    code, _ = api('POST', '/api/model', {'id': 'q8'})
    ok(code == 200 and wait(lambda: state()['phase'] == 'ready' and state()['active_model'] == 'q8', 90), 'the second test model is ready')
    page.wait_for_function("STATE && STATE.phase === 'ready' && STATE.vision && STATE.vision.current === 'mm-broken'", timeout=30000)
    page.set_input_files('#fileInput', png)
    page.wait_for_function("document.querySelector('#docName').textContent === 'scan.png' && document.querySelectorAll('.doc-page').length === 1", timeout=15000)
    calls.clear()
    page.click('#docReadBtn')
    page.wait_for_selector('#docView .dl-confirm')
    page.locator('#docView .dl-confirm button.primary').click()
    page.wait_for_function("document.querySelector('#docNote').textContent.includes('Сообщение движка')", timeout=60000)
    note = page.inner_text('#docNote')
    ok('не смогла работать с файлом для картинок' in note and 'GGUF' in note, 'the window says why: ' + note[:220])
    st = state()
    log = open(os.path.join(ROOT, 'data', 'logs', 'launcher.log'), encoding='utf-8', errors='replace').read()
    ok(not st['vision']['on'] and 'GGUF' in st['vision']['error'] and 'it starts again without it' in log and '--mmproj' in log,
       'the real engine was given the broken file, failed, and starts without it: %s' % st['vision']['error'][:120])
    ok(wait(lambda: state()['phase'] == 'ready' and not state()['engine_info']['vision'], 40), 'the engine works again, without pictures')
    ok(not calls and page.input_value('.doc-page .doc-src') == '' and page.is_visible('#docReadBtn'), 'nothing went to the model; the page is still to be read')
    page.click('#closeDocBtn')
    page.fill('#src', 'Проверка после сбоя.')
    page.click('#goBtn')
    ok(wait(lambda: any(isinstance(c['messages'][0]['content'], str) for c in calls), 30), 'translation works after it')
    ok(not errs, 'no page errors: %s' % errs[:3])
    b.close()

print('FAILS: %d of %d' % (sum(r.startswith('FAIL') for r in res), len(res)))
