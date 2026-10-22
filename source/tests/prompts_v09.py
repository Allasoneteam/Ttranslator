# v0.9: examples in the empty «Свой» style and «Контекст» fields (double-click inserts them), the test panel text,
# the «Учебный пример» button (request text, language, cleaning of the answer, confirmation, repeats, the note
# under the field), with canned engine replies (fixtures written for the test, not model output).
# Usage: prompts_v09.py <work> <ui_url>   (a launcher past the first run; models/my-custom-model.gguf must exist in the root)
import sys, json, os, re, time, urllib.request
from playwright.sync_api import sync_playwright
S, URL = sys.argv[1], sys.argv[2]
shots = os.path.join(S, 'shots', 'v09'); os.makedirs(shots, exist_ok=True)
res = []
def ok(c, m): res.append(('OK  ' if c else 'FAIL') + ' ' + m); print(res[-1], flush=True)
def post(path, body=None):
    req = urllib.request.Request(URL.rstrip('/') + path, data=json.dumps(body or {}).encode(), headers={'Content-Type': 'application/json', 'Origin': URL.rstrip('/')})
    return json.load(urllib.request.urlopen(req, timeout=10))
def phase():
    return json.load(urllib.request.urlopen(URL.rstrip('/') + '/api/state'))['phase']
def wait_phase(p):
    for i in range(120):
        if phase() == p: return True
        time.sleep(0.5)
    return False

queue = []                  # replies for the next requests; the last one repeats
prompts = []                # bodies of the requests
def reply(route):
    body = json.loads(route.request.post_data); prompts.append(body)
    out = queue.pop(0) if len(queue) > 1 else queue[0]
    parts = re.split(r'( )', out)
    chunks = ''.join('data: ' + json.dumps({'choices': [{'delta': {'content': w}}]}) + '\n\n' for w in parts if w)
    chunks += 'data: ' + json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}], 'timings': {'predicted_n': 12, 'predicted_per_second': 9.5}}) + '\n\ndata: [DONE]\n\n'
    route.fulfill(status=200, headers={'Content-Type': 'text/event-stream'}, body=chunks)

post('/api/model', {'id': 'file:my-custom-model.gguf'}); wait_phase('ready')
with sync_playwright() as pw:
    b = pw.chromium.launch(); ctx = b.new_context(viewport={'width': 1180, 'height': 820}, locale='ru-RU')
    # an "old" window: the start languages and the welcome window are tested elsewhere
    ctx.add_init_script("try { sessionStorage.setItem('tdoc.window', '1'); sessionStorage.setItem('tdoc.welcome', 'done') } catch (e) {}")
    page = ctx.new_page(); errs = []
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'status of 503' not in m.text else None)
    page.route('**/v1/chat/completions', reply)
    page.goto(URL); page.wait_for_selector('body[data-model="ready"]', timeout=20000)
    page.wait_for_function("document.querySelector('#modelName').textContent.includes('my-custom-model')", timeout=20000)
    def idle(): page.wait_for_selector('#goBtn:not([hidden])', timeout=15000)
    def content(p): return p['messages'][0]['content']

    # ================= examples in the empty fields
    ok(page.get_attribute('#ctx', 'placeholder') == 'например: текст научно-популярной статьи' and 'Двойной щелчок' in page.get_attribute('#ctx', 'title'),
       'context: placeholder and hint: %s' % page.get_attribute('#ctx', 'placeholder'))
    if page.is_hidden('#customStyle'): page.locator('#chips .chip', has_text='Свой').click()
    ok(page.is_visible('#customStyle') and page.get_attribute('#customStyle', 'placeholder') == 'например: художественно-литературный', 'custom style: placeholder %s' % page.get_attribute('#customStyle', 'placeholder'))
    page.fill('#customStyle', ''); page.dblclick('#customStyle')
    ok(page.input_value('#customStyle') == 'художественно-литературный' and page.evaluate("document.activeElement.id") == 'customStyle', 'double-click inserts the example into the empty style field')
    ok(page.evaluate("JSON.parse(localStorage.getItem('tdoc.customStyle'))") == 'художественно-литературный', 'the inserted style is remembered like a typed one')
    page.fill('#customStyle', 'как в сказке'); page.dblclick('#customStyle')
    ok(page.input_value('#customStyle') == 'как в сказке', 'double-click does not replace a written style')
    page.fill('#customStyle', ''); page.dblclick('#customStyle')
    page.fill('#ctx', ''); page.dblclick('#ctx')
    ok(page.input_value('#ctx') == 'текст научно-популярной статьи', 'double-click inserts the context example')
    page.select_option('#srcSel', 'en'); page.select_option('#tgtSel', 'ru')
    page.fill('#src', 'The sky is blue.'); page.wait_for_timeout(300)
    queue[:] = ['Небо голубое.', 'Небо синее.', 'Небо лазурное.', 'Небо голубого цвета.', 'Синее небо.']
    n = len(prompts); page.click('#goBtn'); idle()
    styled = [content(p) for p in prompts[n:] if 'Follow this style' in content(p)]
    ok(len(styled) == 1 and styled[0].startswith('Context: текст научно-популярной статьи\n\n') and 'Follow this style: художественно-литературный.' in styled[0],
       'the request has the context and the style: %s' % (styled[0][:160] if styled else prompts[n:]))
    page.locator('#chips .chip', has_text='Свой').click()
    page.fill('#ctx', '')

    # ================= the test panel names its styles
    page.click('#testBtn'); page.wait_for_timeout(300)
    intro = page.inner_text('#testIntro')
    ok('в стилях «Нейтральный», «Разговорный»' in intro and 'Пар фраз: 2' in intro and 'Ещё 2 перевода фраз с формулами LaTeX' in intro, 'test intro: ' + intro[:200])
    ok(page.evaluate('TEST_STYLES') == ['neutral', 'casual'] and page.evaluate('MATH_TESTS.length') == 1, 'test styles and phrases with formulas')
    page.click('#closeTestBtn')

    # ================= «Учебный пример»
    words = page.evaluate('LESSON')
    ok('Маленькие модели иногда ошибаются в правилах' in page.get_attribute('#lessonBtn', 'title') and page.inner_text('#lessonLabel') == 'Учебный пример', 'button and its hint about mistakes')
    LESSON1 = '**Правило:** после шипящих пишется «и».\n\n\n* Пример: жи, ши.\n* Упражнение: маш_на.\n## Ответ: машина.'
    queue[:] = [LESSON1]
    page.select_option('#srcSel', 'ru'); page.select_option('#tgtSel', 'en'); page.fill('#src', '')
    n = len(prompts); page.click('#lessonBtn'); idle()
    p = prompts[-1]; c = content(p)
    topics = lambda code: [x['en'] for x in words['topics']['all'] + words['topics'].get(code, [])]
    m = re.fullmatch(r'Write (.+) about (.+), for intermediate \(B1–B2\) learners of Russian\. Write everything in Russian only, in simple words, in at most five short lines\. Do not add a title, a translation, Markdown formatting or any other comments\.', c)
    ok(bool(m) and m.group(1) in words['kinds'] and m.group(2) in topics('ru'), 'request text (the default level is intermediate): ' + c)
    ok(p['temperature'] == 0.9 and p['max_tokens'] == 320 and isinstance(p['seed'], int) and len(p['messages']) == 1, 'generation parameters: %s' % {k: p[k] for k in ('temperature', 'max_tokens', 'seed')})
    want = 'Правило: после шипящих пишется «и».\n\n– Пример: жи, ши.\n– Упражнение: маш_на.\nОтвет: машина.'
    ok(page.input_value('#src') == want, 'Markdown removed, text in the field: %r' % page.input_value('#src'))
    ok(page.inner_text('#cleanNote').startswith('Пример придуман моделью — в правилах возможны ошибки') and page.inner_text('#lessonCheck') == 'Проверить', 'the note under the field with «Проверить»: ' + page.inner_text('#cleanNote'))
    ok(len(prompts) == n + 1, 'one request, no translation started')
    page.screenshot(path=os.path.join(shots, '1-lesson.png'))
    page.type('#src', ' ')
    ok(page.inner_text('#cleanNote') == '', 'the note disappears when the text is changed')

    # the field is not empty: a second press replaces the text
    n = len(prompts)
    page.click('#lessonBtn')
    ok(page.inner_text('#lessonLabel') == 'Заменить текст?' and len(prompts) == n, 'asks before replacing the text, no request')
    page.keyboard.press('Escape')
    ok(page.inner_text('#lessonLabel') == 'Учебный пример', 'Esc cancels the confirmation')
    page.click('#randomBtn')
    page.click('#lessonBtn')
    ok(page.inner_text('#randomLabel') == 'Случайно' and page.inner_text('#lessonLabel') == 'Заменить текст?', 'one confirmation at a time («Случайно» is reset)')
    queue[:] = ['Слово «кофе» — мужского рода: чёрный кофе.']
    page.click('#lessonBtn'); idle()
    ok(page.input_value('#src') == 'Слово «кофе» — мужского рода: чёрный кофе.' and len(prompts) == n + 1, 'second press replaces the text')

    # the language of the text: the left list, or the detected language with «Авто»
    page.select_option('#srcSel', 'de'); page.fill('#src', '')
    queue[:] = ['Der Artikel von „Mädchen“ ist „das“: das Mädchen.']
    page.click('#lessonBtn'); idle()
    c = content(prompts[-1]); m = re.search(r'.* about (.+), for intermediate \(B1–B2\) learners of German\. Write everything in German only', c)
    ok(bool(m) and m.group(1) in topics('de'), 'German: ' + c[:120])
    page.select_option('#srcSel', 'auto'); page.fill('#src', 'We have been living here for ten years and we like it very much.'); page.wait_for_timeout(400)
    queue[:] = ['Use "for" with a period of time: for ten years.']
    page.click('#lessonBtn'); page.click('#lessonBtn'); idle()
    ok('learners of English. Write everything in English only' in content(prompts[-1]), '«Авто»: the language of the text in the field')
    page.select_option('#srcSel', 'zh'); page.fill('#src', '')
    queue[:] = ['量词：一本书。']
    page.click('#lessonBtn'); idle()
    ok('learners of Simplified Chinese' in content(prompts[-1]), 'Chinese: the form for the model')

    # repeats and answers that are too long
    page.select_option('#srcSel', 'ru'); page.fill('#src', '')
    queue[:] = ['Ударение: звонИт.']
    page.click('#lessonBtn'); idle()
    page.fill('#src', '')
    n = len(prompts); page.click('#lessonBtn'); idle()
    ok(len(prompts) == n + words['tries'], 'the same example again: asked %d times' % (len(prompts) - n))
    page.fill('#src', '')
    queue[:] = ['Очень длинный ответ. ' * 60]
    n = len(prompts); page.click('#lessonBtn'); idle()
    ok(page.input_value('#src') == '' and page.inner_text('#toast') == 'Модель не придумала подходящий пример. Нажмите ещё раз.' and len(prompts) == n + words['tries'],
       'too long answer: not inserted, a hint: ' + page.inner_text('#toast'))

    # without a model: the usual hint, no request
    post('/api/unload'); page.evaluate('refreshState()'); page.wait_for_selector('body[data-model="unloaded"]', timeout=10000)
    n = len(prompts); page.click('#lessonBtn'); page.wait_for_timeout(200)
    ok(len(prompts) == n and 'Please load a model.' in page.inner_text('#toast'), 'unloaded model: Please load a model.')
    post('/api/load'); wait_phase('ready'); page.evaluate('refreshState()'); page.wait_for_selector('body[data-model="ready"]', timeout=20000)

    # help
    page.click('#helpBtn'); page.wait_for_timeout(200)
    h = page.inner_text('#helpBody')
    ok('«Учебный пример»' in h and 'ошибаются в правилах' in h and 'Двойной щелчок' in h and 'Чтение вслух' in h, 'help describes the new buttons')
    page.click('#closeHelpBtn')
    ok(not errs, 'no console errors: %s' % errs[:3])
    b.close()

print('FAILS:', sum(1 for x in res if x.startswith('FAIL')), 'of', len(res))
