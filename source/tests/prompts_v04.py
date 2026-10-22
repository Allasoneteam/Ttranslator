# Exact prompts with the glossary and the «?» questions, with canned engine replies (fixtures written for the test).
# Usage: prompts_v04.py <work> <ui_url> <root>  (models/my-custom-model.gguf must exist in the root)
import sys, json, os, time, urllib.request, urllib.parse
from playwright.sync_api import sync_playwright
S, URL, ROOT = sys.argv[1], sys.argv[2], sys.argv[3]
EN1 = 'Our approach includes, as a particular case, the perturbation theory, but generally does not require inside any small parameters and unperturbed solutions.'
RU_OUT = 'Наш метод включает как частный случай теорию возмущений.'
reqs = []
def sse(text):
    return 'data: ' + json.dumps({'choices': [{'delta': {'content': text}}]}) + '\n\ndata: ' + json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}], 'timings': {'predicted_per_second': 20}}) + '\n\ndata: [DONE]\n\n'
def reply(route):
    body = json.loads(route.request.post_data); reqs.append(body)
    m = body['messages']
    if m[0]['role'] == 'system': out = 'Ответ модели.'
    elif 'into Russian' in m[0]['content']: out = RU_OUT
    else: out = 'Our method includes perturbation theory.'
    route.fulfill(status=200, headers={'Content-Type': 'text/event-stream'}, body=sse(out))
def post(path, body):
    req = urllib.request.Request(URL.rstrip('/') + path, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'Origin': URL.rstrip('/')})
    return json.load(urllib.request.urlopen(req, timeout=10))
def put(name, text):
    req = urllib.request.Request(URL.rstrip('/') + '/api/glossary/' + urllib.parse.quote(name), data=text.encode('utf-8'), method='PUT', headers={'Origin': URL.rstrip('/')})
    return json.load(urllib.request.urlopen(req, timeout=10))
def wait_ready():
    for i in range(80):
        st = json.load(urllib.request.urlopen(URL.rstrip('/') + '/api/state'))
        if st['phase'] == 'ready': return st
        time.sleep(0.5)
res = []
def ok(c, m): res.append(('OK  ' if c else 'FAIL') + ' ' + m)
put('Тест.tsv', '﻿Английский\tРусский\tПримечание\r\nperturbation theory\tтеория возмущений\t\r\nunperturbed solution\tневозмущённое решение\tиз статьи\r\nclosed-form\tв замкнутой форме\t\r\n')
post('/api/model', {'id': 'q4'}); wait_ready()
with sync_playwright() as pw:
    b = pw.chromium.launch(); ctx = b.new_context(viewport={'width': 1180, 'height': 780}, locale='ru-RU')
    # the start languages of a new window (0.6.1) are tested in e2e_v061.py; here the window is an "old" one
    ctx.add_init_script("try { sessionStorage.setItem('tdoc.window', '1'); sessionStorage.setItem('tdoc.welcome', 'done') } catch (e) {}")
    page = ctx.new_page(); errs = []
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.route('**/v1/chat/completions', reply)
    page.goto(URL); page.wait_for_selector('body[data-model="ready"]', timeout=15000)
    page.wait_for_function("document.querySelector('#glossFile').options.length > 0", timeout=10000)
    page.click('#tabGloss'); page.select_option('#glossFile', 'Тест.tsv'); page.wait_for_timeout(500)
    page.check('#glossOn'); page.select_option('#srcSel', 'auto'); page.select_option('#tgtSel', 'auto')
    for _ in range(10):   # leave only the neutral variant (chips are redrawn after each click)
        extra = page.locator('#chips .chip[aria-pressed="true"]:not(.fixed)')
        if not extra.count(): break
        extra.first.click()

    # Hy-MT2: the terminology template from its README
    page.fill('#src', EN1); page.wait_for_timeout(300)
    page.click('#goBtn'); page.wait_for_selector('#goBtn:not([hidden])')
    p0 = reqs[-1]['messages'][0]['content']
    want = ('Reference the following translations:\nperturbation theory translates to теория возмущений\n'
            'unperturbed solution translates to невозмущённое решение\n\nTranslate the following text into Russian. '
            'Note that you should only output the translated result without any additional explanation:\n\n' + EN1)
    ok(p0 == want, 'Hy-MT2 prompt with terms:\n' + p0[:200])

    # universal model (Gemma, own files): a glossary block before the instruction
    post('/api/model', {'id': 'file:my-custom-model.gguf'}); wait_ready()
    page.wait_for_function("document.querySelector('#modelName').textContent.includes('my-custom-model')", timeout=20000)
    page.wait_for_selector('body[data-model="ready"]', timeout=20000)
    reqs.clear()
    page.click('#goBtn'); page.wait_for_selector('#goBtn:not([hidden])')
    p1 = reqs[-1]['messages'][0]['content']
    want = ('Glossary: translate these terms as given, adapting their grammatical form to the sentence.\n'
            'perturbation theory → теория возмущений\nunperturbed solution → невозмущённое решение\n\n'
            'Translate the following English text into Russian. Output only the translation, without any comments.\n\n' + EN1)
    ok(p1 == want, 'chat prompt with terms:\n' + p1[:200])

    # back-translation uses the glossary in the other direction
    reqs.clear()
    page.locator('.card').first.locator('[data-act=back]').click(); page.wait_for_selector('#goBtn:not([hidden])'); page.wait_for_timeout(200)
    p2 = reqs[-1]['messages'][0]['content']
    ok(p2.startswith('Glossary: translate these terms as given, adapting their grammatical form to the sentence.\nтеория возмущений → perturbation theory\n\nTranslate the following Russian text into English.'), 'back-translation reversed: ' + p2[:150])

    # «?» → «Как сказать точнее?»: the question text
    reqs.clear()
    page.locator('.card').first.locator('[data-act=ask]').click()
    page.locator('#popMenu .mi', has_text='Как сказать точнее?').click()
    page.wait_for_selector('#askLog .msg.bot .msg-meta', timeout=10000)
    q = reqs[-1]['messages'][-1]['content']
    want = (f'Как точнее перевести на русский текст «{EN1}»? Сейчас перевод такой: «{RU_OUT}». Предложи 2–3 более точных варианта и коротко объясни разницу. '
            'Термины взяты из словаря пользователя: perturbation theory → теория возмущений; unperturbed solution → невозмущённое решение.')
    ok(q == want, 'question sent:\n' + q[:220])
    ok(reqs[-1]['messages'][0]['role'] == 'system', 'question goes through the chat (system prompt first)')

    # academic-style card: the style is mentioned in «Почему так?»
    page.locator('#chips .chip', has_text='Научный').click()
    page.click('#goBtn'); page.wait_for_selector('#goBtn:not([hidden])')
    reqs.clear()
    cards = page.locator('.card')
    target = None
    for i in range(cards.count()):
        if cards.nth(i).locator('.card-label').inner_text().startswith('Научный'): target = cards.nth(i)
    if target is None:
        target = page.locator('.card').first   # same text as neutral: merged into the first card
        ok('Научный' in target.locator('.card-label').inner_text(), 'academic merged into first card')
    else:
        target.locator('[data-act=ask]').click()
        page.locator('#popMenu .mi', has_text='Почему так?').click()
        page.wait_for_function("document.querySelectorAll('#askLog .msg-meta').length >= 2", timeout=10000)
        q = reqs[-1]['messages'][-1]['content']
        ok('Стиль варианта: научный.' in q, 'style named in the question')

    # same-language editing: no glossary block
    reqs.clear()
    page.select_option('#tgtSel', 'en'); page.wait_for_timeout(200)
    page.click('#goBtn'); page.wait_for_selector('#goBtn:not([hidden])')
    ok(all('Glossary' not in r['messages'][0]['content'] for r in reqs if r['messages'][0]['role'] == 'user'), 'no glossary block in editing prompts')
    page.select_option('#tgtSel', 'auto')

    # glossary off: plain prompt
    page.click('#tabGloss'); page.uncheck('#glossOn'); reqs.clear()
    page.click('#goBtn'); page.wait_for_selector('#goBtn:not([hidden])')
    ok(reqs[0]['messages'][0]['content'].startswith('Translate the following English text into Russian.'), 'glossary off → plain prompt')
    page.check('#glossOn')
    ok(not errs, 'no page errors %s' % errs[:2])
    b.close()
print('\n'.join(res))
print('FAILS:', sum(1 for x in res if x.startswith('FAIL')), 'of', len(res))
