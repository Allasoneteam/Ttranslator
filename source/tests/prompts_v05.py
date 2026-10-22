# v0.5: the «Случайно» button (request text, cleaning of the model's answer, repeats, confirmation, Stop)
# and the "Please load a model." answer of the launcher, with canned engine replies
# (fixtures written for the test, not model output).
# Usage: prompts_v05.py <work> <ui_url>   (a launcher past the first run; models/my-custom-model.gguf must exist in the root)
import sys, json, os, re, time, urllib.request
from playwright.sync_api import sync_playwright
S, URL = sys.argv[1], sys.argv[2]
shots = os.path.join(S, 'shots', 'v05'); os.makedirs(shots, exist_ok=True)
res = []
def ok(c, m): res.append(('OK  ' if c else 'FAIL') + ' ' + m)
def post(path, body):
    req = urllib.request.Request(URL.rstrip('/') + path, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'Origin': URL.rstrip('/')})
    return json.load(urllib.request.urlopen(req, timeout=10))
def wait_ready():
    for i in range(80):
        if json.load(urllib.request.urlopen(URL.rstrip('/') + '/api/state'))['phase'] == 'ready': return
        time.sleep(0.5)

queue = []                  # replies for the next requests; the last one repeats
prompts = []                # bodies of the requests
mode = {'error': None}
def reply(route):
    body = json.loads(route.request.post_data); prompts.append(body)
    if mode['error']:
        route.fulfill(status=503, content_type='application/json', body=json.dumps({'error': {'code': 503, 'message': mode['error'], 'type': 'unavailable_error'}}))
        return
    out = queue.pop(0) if len(queue) > 1 else queue[0]
    words = out.split(' ')
    chunks = ''.join('data: ' + json.dumps({'choices': [{'delta': {'content': (w if i == 0 else ' ' + w)}}]}) + '\n\n' for i, w in enumerate(words))
    chunks += 'data: ' + json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}], 'timings': {'predicted_n': 12, 'predicted_per_second': 9.5}}) + '\n\ndata: [DONE]\n\n'
    route.fulfill(status=200, headers={'Content-Type': 'text/event-stream'}, body=chunks)

post('/api/model', {'id': 'file:my-custom-model.gguf'}); wait_ready()
with sync_playwright() as pw:
    b = pw.chromium.launch(); ctx = b.new_context(viewport={'width': 1180, 'height': 820}, locale='ru-RU')
    # the start languages of a new window (0.6.1) are tested in e2e_v061.py; here the window is an "old" one
    ctx.add_init_script("try { sessionStorage.setItem('tdoc.window', '1'); sessionStorage.setItem('tdoc.welcome', 'done') } catch (e) {}")
    page = ctx.new_page(); errs = []
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'status of 503' not in m.text else None)
    page.on('response', lambda r: errs.append('HTTP %d %s' % (r.status, r.url)) if r.status in (404, 500) else None)
    page.route('**/v1/chat/completions', reply)
    page.goto(URL); page.wait_for_selector('body[data-model="ready"]', timeout=20000)
    page.wait_for_function("document.querySelector('#modelName').textContent.includes('my-custom-model')", timeout=20000)
    words = page.evaluate('({kinds: RANDOM.kinds, topics: RANDOM.topics, tries: RANDOM.tries})')
    def idle(): page.wait_for_selector('#goBtn:not([hidden])', timeout=15000)
    def toast(): return page.inner_text('#toast')
    def clear_toast(): page.evaluate("document.querySelector('#toast').textContent = ''")
    def press_random(confirm=False):
        """Press «Случайно» (twice when the field is not empty) and wait for the answer to be processed."""
        page.click('#randomBtn')
        if confirm: page.click('#randomBtn')
        idle()

    # request text, parameters, insertion into the field
    queue[:] = ['«Семь раз отмерь, один раз отрежь.»']
    page.select_option('#srcSel', 'ru'); page.select_option('#tgtSel', 'en'); page.fill('#src', '')
    press_random()
    p = prompts[-1]; content = p['messages'][0]['content']
    m = re.fullmatch(r'Give one well-known (\w+) in Russian about ([a-z ]+)\. Output only the (\w+) itself in Russian, without a translation, an explanation, quotation marks or any other comments\.', content)
    ok(bool(m) and m.group(1) == m.group(3) and m.group(1) in words['kinds'] and m.group(2) in words['topics'], 'request text: ' + content)
    ok(p['stream'] is True and p['temperature'] == 1.0 and p['top_k'] == 64 and p['top_p'] == 0.95 and p['max_tokens'] == 120 and isinstance(p['seed'], int), 'generation parameters: %s' % {k: p[k] for k in ('temperature', 'top_k', 'top_p', 'max_tokens', 'seed')})
    ok(len(p['messages']) == 1 and p['messages'][0]['role'] == 'user', 'one user message')
    ok(page.input_value('#src') == 'Семь раз отмерь, один раз отрежь.', 'quotes removed, text inserted: ' + page.input_value('#src'))
    ok(page.inner_text('#counter') == '33 из 1000' and page.inner_text('#cleanNote') == '' and page.inner_text('#modeBadge') == 'русский → английский', 'counter and badge updated: %s / %s' % (page.inner_text('#counter'), page.inner_text('#modeBadge')))
    ok(len(prompts) == 1 and page.locator('.card').count() == 0, 'translation is not started by itself')
    page.screenshot(path=os.path.join(shots, '5-random.png'))

    # a text in the field is replaced only after a second press
    n = len(prompts)
    page.click('#randomBtn')
    ok(page.inner_text('#randomLabel') == 'Заменить текст?' and len(prompts) == n and page.input_value('#src').startswith('Семь раз'), 'field is not empty: asks to confirm, no request')
    page.wait_for_timeout(3800)
    ok(page.inner_text('#randomLabel') == 'Случайно', 'confirmation expires by itself')
    page.click('#randomBtn'); page.keyboard.press('Escape')
    ok(page.inner_text('#randomLabel') == 'Случайно' and len(prompts) == n, 'Esc cancels the confirmation')
    queue[:] = ['Тише едешь — дальше будешь.']
    press_random(confirm=True)
    ok(len(prompts) == n + 1 and page.input_value('#src') == 'Тише едешь — дальше будешь.' and page.inner_text('#randomLabel') == 'Случайно', 'second press replaces the text')

    # the language of the request follows the language of the text
    for code, name in (('de', 'German'), ('zh', 'Simplified Chinese'), ('la', 'Latin'), ('el', 'Greek')):
        page.select_option('#srcSel', code); page.fill('#src', '')
        queue[:] = ['Text ' + code]
        press_random()
        ok((' in %s about ' % name) in prompts[-1]['messages'][0]['content'] and page.input_value('#src') == 'Text ' + code, 'language %s → "%s"' % (code, name))
    page.select_option('#srcSel', 'auto'); page.fill('#src', 'We present a closed-form solution for the recurrence.'); page.wait_for_timeout(400)
    queue[:] = ['A stitch in time saves nine.']
    press_random(confirm=True)
    ok(' in English about ' in prompts[-1]['messages'][0]['content'], 'Авто: language of the text in the field')
    page.fill('#src', ''); page.wait_for_timeout(300)
    queue[:] = ['Better late than never.']
    press_random()
    ok(' in English about ' in prompts[-1]['messages'][0]['content'], 'Авто with an empty field: the last detected language')
    page.select_option('#srcSel', 'ru')

    # cleaning of the answer
    cases = [
        ('"Time flies."', 'Time flies.'),
        ('1. Tempus fugit.', 'Tempus fugit.'),
        ('**Proverb:** Haste makes waste', 'Haste makes waste'),
        ('Here is a proverb:\n\nAn apple a day keeps the doctor away.', 'An apple a day keeps the doctor away.'),
        ('<think>Let me think</think>\nНе всё то золото, что блестит.', 'Не всё то золото, что блестит.'),
        ('Fortune favours the bold.\n\n(Удача благоволит смелым.)', 'Fortune favours the bold.'),
        ('- «Волков бояться — в лес не ходить»', 'Волков бояться — в лес не ходить'),
        ("'Practice makes perfect.'", 'Practice makes perfect.'),
    ]
    for raw, want in cases:
        page.fill('#src', ''); queue[:] = [raw]
        press_random()
        ok(page.input_value('#src') == want, 'cleaned %r → %r (got %r)' % (raw[:40], want, page.input_value('#src')))

    # repeats: a repeated answer is asked for again, but not more than RANDOM.tries times
    page.fill('#src', ''); queue[:] = ['Dup one.', 'Dup one.', 'Dup two.']
    press_random()
    n = len(prompts); page.fill('#src', '')
    press_random()
    ok(len(prompts) - n == 2 and page.input_value('#src') == 'Dup two.', 'repeated answer is replaced by a new request (2 requests): %s' % page.input_value('#src'))
    n = len(prompts); page.fill('#src', '')
    press_random()
    ok(len(prompts) - n == words['tries'] and page.input_value('#src') == 'Dup two.', 'a model that keeps repeating is asked %d times, then its answer is used' % words['tries'])

    # unusable answers: nothing is inserted
    for raw, what in (('x' * 400, 'too long'), ('', 'empty')):
        page.fill('#src', ''); clear_toast(); queue[:] = [raw]; n = len(prompts)
        press_random()
        ok(page.input_value('#src') == '' and 'не придумала' in toast() and len(prompts) - n == words['tries'], '%s answer: field stays empty, hint "%s", %d requests' % (what, toast(), len(prompts) - n))

    # busy state and Stop
    page.fill('#src', '')
    # the request hangs until the page gives up (a stand-in for fetch inside the page: no pending route is left behind)
    page.evaluate("""() => { window.__fetch = window.fetch; window.fetch = (u, o) => String(u).includes('/v1/chat/completions')
        ? new Promise((res, rej) => o.signal.addEventListener('abort', () => rej(new DOMException('Aborted', 'AbortError')))) : window.__fetch(u, o); }""")
    page.click('#randomBtn'); page.wait_for_selector('#stopBtn:not([hidden])', timeout=5000)
    ok(page.is_hidden('#goBtn') and page.is_disabled('#randomBtn') and page.inner_text('#cleanNote') == 'Придумываю…', 'while the model thinks: Stop instead of Перевести, button locked, note shown')
    page.click('#stopBtn'); idle(); page.evaluate('() => { window.fetch = window.__fetch; }')
    ok(page.input_value('#src') == '' and page.is_enabled('#randomBtn') and page.inner_text('#cleanNote') == '' and page.inner_text('#formError') == '', 'after Стоп: nothing inserted, button free, no error')

    # "Please load a model." from the launcher is shown as it is
    page.fill('#src', 'Привет, мир'); page.wait_for_timeout(300)
    mode['error'] = 'Please load a model.'
    page.click('#goBtn'); idle()
    ok(page.locator('.card.err .card-text').first.inner_text() == 'Please load a model.' and page.inner_text('#formError') == 'Please load a model.', 'launcher 503 is shown without a prefix: ' + page.inner_text('#formError'))
    mode['error'] = 'Loading model'
    page.click('#goBtn'); idle()
    ok(page.inner_text('#formError') == 'Ошибка движка: Loading model', 'other 503 keeps the prefix: ' + page.inner_text('#formError'))
    mode['error'] = None
    # the same through «Случайно»
    page.fill('#src', ''); mode['error'] = 'Please load a model.'
    press_random()
    ok(page.inner_text('#formError') == 'Please load a model.' and page.input_value('#src') == '', '«Случайно» when the launcher refuses: ' + page.inner_text('#formError'))
    mode['error'] = None
    ok(not errs, 'no page errors %s' % errs[:2])

    # Hy-MT2 only translates: a one-time hint, same request text
    post('/api/model', {'id': 'q4'}); wait_ready()
    page.evaluate('refreshState()'); page.wait_for_function("document.querySelector('#modelName').textContent.includes('Hy-MT2')", timeout=20000)
    page.wait_for_selector('body[data-model="ready"]', timeout=20000)
    page.fill('#src', ''); queue[:] = ['Hymt answer one']; clear_toast()
    press_random()
    ok(prompts[-1]['messages'][0]['content'].startswith('Give one well-known ') and 'Hy-MT2' in toast(), 'Hy-MT2: same request, one-time hint: ' + toast())
    page.fill('#src', ''); queue[:] = ['Hymt answer two']; clear_toast()
    press_random()
    ok(toast() == '' and page.input_value('#src') == 'Hymt answer two', 'the hint is shown only once')
    b.close()
print('\n'.join(res))
print('FAILS:', sum(1 for x in res if x.startswith('FAIL')), 'of', len(res))
