# v0.3 prompts for the new languages and the chat requests, with canned engine replies (fixtures written for the test).
# Usage: prompts_v03.py <work> <ui_url>  (models/my-custom-model.gguf must exist in the root)
import sys, json, os, time, urllib.request
from playwright.sync_api import sync_playwright
S, URL = sys.argv[1], sys.argv[2]
shots = os.path.join(S, 'shots', 'v03'); os.makedirs(shots, exist_ok=True)
MD_REPLY = '**Коротко:** обычно говорят «теория возмущений».\n\n- perturbation theory — теория возмущений\n- perturbation — возмущение\n\nПример: `perturbation theory` в квантовой механике.\n\n1. первый\n2. второй'
reqs = []
state = {'overflow_next': False}
def sse(text):
    words = text.split(' ')
    chunks = ''.join('data: ' + json.dumps({'choices': [{'delta': {'content': (w if i == 0 else ' ' + w)}}]}) + '\n\n' for i, w in enumerate(words))
    return chunks + 'data: ' + json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}], 'timings': {'predicted_n': 40, 'predicted_per_second': 21.5}}) + '\n\ndata: [DONE]\n\n'
def reply(route):
    body = json.loads(route.request.post_data)
    reqs.append(body)
    msgs = body['messages']
    if msgs[0]['role'] == 'system':
        if state['overflow_next']:
            state['overflow_next'] = False
            route.fulfill(status=400, headers={'Content-Type': 'application/json'}, body=json.dumps({'error': {'code': 400, 'message': 'request (5000 tokens) exceeds the available context size (4096 tokens), try increasing it', 'type': 'exceed_context_size_error', 'n_prompt_tokens': 5000, 'n_ctx': 4096}}))
            return
        route.fulfill(status=200, headers={'Content-Type': 'text/event-stream'}, body=sse(MD_REPLY))
        return
    route.fulfill(status=200, headers={'Content-Type': 'text/event-stream'}, body=sse('Пример перевода.'))
def post(path, body):
    req = urllib.request.Request(URL.rstrip('/') + path, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'Origin': URL.rstrip('/')})
    return json.load(urllib.request.urlopen(req, timeout=10))
res = []
def ok(c, m): res.append(('OK  ' if c else 'FAIL') + ' ' + m)
post('/api/model', {'id': 'file:my-custom-model.gguf'})
for i in range(60):
    st = json.load(urllib.request.urlopen(URL.rstrip('/') + '/api/state'))
    if st['phase'] == 'ready': break
    time.sleep(0.5)
with sync_playwright() as pw:
    b = pw.chromium.launch(); ctx = b.new_context(viewport={'width': 1180, 'height': 780}, locale='ru-RU')
    # the start languages of a new window (0.6.1) are tested in e2e_v061.py; here the window is an "old" one
    ctx.add_init_script("try { sessionStorage.setItem('tdoc.window', '1'); sessionStorage.setItem('tdoc.welcome', 'done') } catch (e) {}")
    page = ctx.new_page(); errs = []
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.route('**/v1/chat/completions', reply)
    page.goto(URL); page.wait_for_selector('body[data-model="ready"]', timeout=15000)
    page.select_option('#srcSel', 'auto'); page.select_option('#tgtSel', 'auto')

    # translation prompts for the new languages (chat family)
    page.fill('#src', 'Wir stellen eine geschlossene Lösung für das n-te Glied vor.'); page.wait_for_timeout(300)
    page.click('#goBtn'); page.wait_for_selector('#goBtn:not([hidden])')
    p0 = reqs[0]['messages'][0]['content']
    ok(p0.startswith('Translate the following German text into Russian. Output only the translation'), 'de → ru prompt: ' + p0[:70])
    ok(reqs[0]['max_tokens'] == min(2048, round(len('Wir stellen eine geschlossene Lösung für das n-te Glied vor.') * 1.5) + 64), 'max_tokens for translation: %s' % reqs[0]['max_tokens'])
    reqs.clear()
    page.fill('#src', 'Мы представляем точное решение.'); page.select_option('#tgtSel', 'zh'); page.wait_for_timeout(300)
    page.click('#goBtn'); page.wait_for_selector('#goBtn:not([hidden])')
    ok(reqs[0]['messages'][0]['content'].startswith('Translate the following Russian text into Simplified Chinese.'), 'ru → zh prompt names Simplified Chinese')
    reqs.clear()
    page.select_option('#srcSel', 'la'); page.select_option('#tgtSel', 'el'); page.fill('#src', 'Gallia est omnis divisa in partes tres.'); page.wait_for_timeout(300)
    ok(page.inner_text('#modeBadge') == 'латынь → греческий', 'badge la → el: ' + page.inner_text('#modeBadge'))
    page.click('#goBtn'); page.wait_for_selector('#goBtn:not([hidden])')
    ok(reqs[0]['messages'][0]['content'].startswith('Translate the following Latin text into Greek.'), 'la → el prompt')
    reqs.clear()
    page.select_option('#tgtSel', 'la'); page.wait_for_timeout(300)
    ok(page.inner_text('#modeBadge').startswith('правка: латынь'), 'Latin editing badge: ' + page.inner_text('#modeBadge'))
    page.click('#goBtn'); page.wait_for_selector('#goBtn:not([hidden])')
    ok(reqs[0]['messages'][0]['content'].startswith('Correct the spelling, grammar and punctuation of the following Latin text.'), 'Latin correction prompt')
    page.select_option('#srcSel', 'auto'); page.select_option('#tgtSel', 'auto')
    page.fill('#src', 'Мы представляем точное решение.')
    page.wait_for_timeout(400)
    ok(page.inner_text('#modeBadge') == 'русский → английский', 'badge after fill: ' + page.inner_text('#modeBadge'))

    # chat request structure
    reqs.clear()
    page.fill('#askInput', 'Как перевести perturbation theory?'); page.click('#askSend')
    page.wait_for_selector('#askLog .msg.bot .msg-meta', timeout=10000)
    r = reqs[-1]; m = r['messages']
    ok(m[0]['role'] == 'system' and 'translator' in m[0]['content'] and m[1] == {'role': 'user', 'content': 'Как перевести perturbation theory?'} and len(m) == 2, 'first chat request: system + question')
    ok(r['temperature'] == 0.6 and r['top_k'] == 64 and r['stream'] is True and 'seed' not in r, 'chat sampling: t=%s k=%s seed=%s' % (r['temperature'], r['top_k'], r.get('seed')))
    ok(128 <= r['max_tokens'] <= 1024, 'chat max_tokens %s' % r['max_tokens'])
    bot = page.locator('#askLog .msg.bot').last
    ok(bot.locator('strong').first.inner_text() == 'Коротко:', 'markdown: bold')
    ok(bot.locator('ul li').count() == 2 and bot.locator('ol li').count() == 2, 'markdown: lists %d/%d' % (bot.locator('ul li').count(), bot.locator('ol li').count()))
    ok(bot.locator('code').first.inner_text() == 'perturbation theory', 'markdown: inline code')
    ok('22 ток/с' in bot.locator('.msg-meta').inner_text(), 'answer meta: ' + bot.locator('.msg-meta').inner_text())
    page.fill('#askInput', 'А как сказать короче?'); page.press('#askInput', 'Enter')
    page.wait_for_function("document.querySelectorAll('#askLog .msg-meta').length == 2", timeout=10000)
    m = reqs[-1]['messages']
    ok([x['role'] for x in m] == ['system', 'user', 'assistant', 'user'], 'second request carries the history: %s' % [x['role'] for x in m])
    ok(m[2]['content'].startswith('**Коротко:**'), 'assistant turn sent back as plain text')

    # the engine reports a context overflow: the oldest pair is dropped and the request repeated
    state['overflow_next'] = True
    n_before = len(reqs)
    page.fill('#askInput', 'Третий вопрос'); page.click('#askSend')
    page.wait_for_function("document.querySelectorAll('#askLog .msg-meta').length == 3", timeout=10000)
    a1, a2 = reqs[n_before]['messages'], reqs[n_before + 1]['messages']
    ok(len(a1) == 6 and len(a2) == 4 and a2[1]['content'] == 'А как сказать короче?', 'retry after overflow drops the oldest pair: %d → %d messages' % (len(a1), len(a2)))
    page.wait_for_timeout(100)
    ok(page.evaluate("(() => { const l = document.querySelector('#askLog'); return l.scrollHeight - l.scrollTop - l.clientHeight; })()") < 2, 'chat scrolled to the end of the new answer')
    ok(page.locator('#askLog .msg.old').count() == 2, 'forgotten messages are faded: %d' % page.locator('#askLog .msg.old').count())
    ok(page.inner_text('#askInfo') == 'начало переписки забыто', 'chat head notes forgotten start')
    ok(page.inner_text('#modeBadge') == 'русский → английский', 'badge after chat: ' + page.inner_text('#modeBadge') + ' ' + json.dumps(page.evaluate('LS')))
    page.screenshot(path=os.path.join(shots, 'mock-chat.png'))

    # «Обновить»: the next request starts from scratch
    page.click('#askReset')
    page.fill('#askInput', 'Новый вопрос'); page.click('#askSend')
    page.wait_for_selector('#askLog .msg.bot .msg-meta', timeout=10000)
    m = reqs[-1]['messages']
    ok(len(m) == 2 and m[1]['content'] == 'Новый вопрос', 'after Обновить only the new question is sent')
    ok(page.inner_text('#askInfo') == '', 'forgotten note cleared')

    # copy button on the answer
    page.locator('#askLog .msg.bot .msg-meta button:not(.speak)').click(); page.wait_for_timeout(200)
    clip = page.evaluate('navigator.clipboard.readText()') if False else None
    ok(not page.is_visible('#askNote'), 'no Hy-MT note for a chat-family model')

    # source box grows with the text but keeps the chat at least 230 px
    page.fill('#src', 'Длинный текст. ' * 66); page.wait_for_timeout(200)
    h = page.evaluate("[document.querySelector('#src').getBoundingClientRect().height, document.querySelector('#askBox').getBoundingClientRect().height, document.querySelector('.left').scrollHeight - document.querySelector('.left').clientHeight]")
    ok(h[0] > 115 and h[1] >= 229 and h[2] <= 1, 'long text: source %d px, chat %d px, column overflow %d' % tuple(h))
    page.fill('#src', 'Коротко.'); page.wait_for_timeout(200)
    h2 = page.evaluate("[document.querySelector('#src').getBoundingClientRect().height, document.querySelector('#askBox').getBoundingClientRect().height]")
    ok(h2[0] <= 111 and h2[1] > h[1], 'short text: source %d px, chat %d px' % tuple(h2))
    page.screenshot(path=os.path.join(shots, 'mock-short.png'))
    page.emulate_media(color_scheme='dark'); page.wait_for_timeout(150)
    page.screenshot(path=os.path.join(shots, 'mock-dark.png'))
    ok(not errs, 'no page errors %s' % errs[:2])
    b.close()
print('\n'.join(res))
print('FAILS:', sum(1 for x in res if x.startswith('FAIL')), 'of', len(res))
