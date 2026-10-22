# v0.2 prompts and same-language editing, with canned engine replies (fixtures written for the test, not model output).
# Usage: prompts_v02.py <work> <ui_url>  (models/my-custom-model.gguf must exist in the root)
import sys, json, os, time, urllib.request
from playwright.sync_api import sync_playwright
S, URL = sys.argv[1], sys.argv[2]
shots = os.path.join(S, 'shots', 'v02'); os.makedirs(shots, exist_ok=True)
EN = 'Our approach includes, as a particular case, the perturbation theory, but generally does not require inside any small parameters and unperturbed solutions.'
EN_FIXED = 'Our approach includes, as a particular case, perturbation theory, but generally does not require any small parameters or unperturbed solutions.'
EN_PARA = 'Perturbation theory is a special case of our approach, which in general needs neither small parameters nor unperturbed solutions.'
EN_COMMENTS = '1. "require inside any small parameters" — the word "inside" is superfluous.\n2. "small parameters and unperturbed solutions" — "or" fits the negation better than "and".'
prompts = []
def reply(route):
    body = json.loads(route.request.post_data)
    p = body['messages'][0]['content']; prompts.append((p, body))
    if 'Check the following' in p: out = EN_COMMENTS
    elif 'Correct the spelling' in p: out = EN_FIXED
    else: out = EN_PARA
    words = out.split(' ')
    chunks = ''.join('data: ' + json.dumps({'choices': [{'delta': {'content': (w if i == 0 else ' ' + w)}}]}) + '\n\n' for i, w in enumerate(words))
    chunks += 'data: ' + json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}], 'timings': {'predicted_n': 40, 'predicted_per_second': 12.5}}) + '\n\ndata: [DONE]\n\n'
    route.fulfill(status=200, headers={'Content-Type': 'text/event-stream'}, body=chunks)
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
    b = pw.chromium.launch(); ctx = b.new_context(viewport={'width': 1180, 'height': 820}, locale='ru-RU')
    # the start languages of a new window (0.6.1) are tested in e2e_v061.py; here the window is an "old" one
    ctx.add_init_script("try { sessionStorage.setItem('tdoc.window', '1'); sessionStorage.setItem('tdoc.welcome', 'done') } catch (e) {}")
    page = ctx.new_page(); errs = []
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.route('**/v1/chat/completions', reply)
    page.goto(URL); page.wait_for_selector('body[data-model="ready"]', timeout=15000)
    # chat-family translation prompts
    page.fill('#src', 'Привет, мир'); page.wait_for_timeout(300)
    page.click('#goBtn'); page.wait_for_selector('#goBtn:not([hidden])')
    tr = [p for p, _ in prompts]
    ok(tr[0] == 'Translate the following Russian text into English. Output only the translation, without any comments.\n\nПривет, мир', 'chat plain translation prompt')
    ok(any(p.startswith('Translate the following Russian text into English. Use a formal academic style of a peer-reviewed scientific paper. Output only') for p in tr), 'chat style translation prompt')
    ok(prompts[0][1]['temperature'] == 0.3 and prompts[0][1]['top_k'] == 64, 'chat sampling params')
    # editing mode in English with comments
    prompts.clear()
    page.select_option('#tgtSel', 'en'); page.fill('#src', EN); page.wait_for_timeout(300)
    page.locator('#chips .chip', has_text='Замечания').click()
    page.fill('#ctx', 'аннотация статьи')
    page.click('#goBtn'); page.wait_for_selector('#goBtn:not([hidden])')
    ed = [p for p, _ in prompts]
    ok(ed[0].startswith('Context: аннотация статьи\n\nCorrect the spelling, grammar and punctuation of the following English text.'), 'corrected prompt with context')
    ok(any(p.startswith('Context: аннотация статьи\n\nRephrase the following English text in English') for p in ed), 'paraphrase prompt')
    ok(any('Rewrite the following English text in English. Use a formal academic style' in p for p in ed), 'style rewrite prompt')
    ok(any(p.startswith('Context: аннотация статьи\n\nCheck the following English text for logical inconsistencies') and 'Reply in English' in p for p in ed), 'comments prompt')
    ok(prompts[-1][1]['max_tokens'] == 400 + round(len(EN) / 2), 'comments token budget grows with the text')
    first = page.locator('.card').first
    ok(first.locator('.card-diff').is_visible(), 'corrected card shows diff')
    dels = first.locator('.card-diff del').all_inner_texts(); ins = first.locator('.card-diff ins').all_inner_texts()
    ok(any('inside' in d for d in dels) and any('or' in i for i in ins), 'diff marks removed "inside" and added "or": del=%s ins=%s' % (dels, ins))
    ok('правк' in first.locator('.card-meta').inner_text(), 'card meta counts edits: ' + first.locator('.card-meta').inner_text())
    ok(page.locator('.card.comments').count() == 1, 'comments card present')
    page.screenshot(path=os.path.join(shots, 'mock-edit.png'))
    first.locator('[data-act=diff]').click()
    ok(first.locator('.card-text').is_visible() and not first.locator('.card-diff').is_visible(), 'diff toggles to clean text')
    page.emulate_media(color_scheme='dark'); first.locator('[data-act=diff]').click(); page.screenshot(path=os.path.join(shots, 'mock-edit-dark.png'))
    ok(not errs, 'no page errors %s' % errs[:2])
    b.close()
print('\n'.join(res))
