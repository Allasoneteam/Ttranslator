# v0.8: LaTeX formulas ($…$, $$…$$) are not translated and not damaged. What counts as a formula (currency stays
# text), cleaning of pasted text around formulas, placeholders {F1}… in the requests (the note for the model; none
# for Hy-MT2 translation templates; «Замечания» get the formulas as they are), formulas put back into the variants
# (also from placeholders the model wrote slightly differently), a repeated request when the model lost a
# placeholder and a warning when it never came back, back-translation, glossary terms inside formulas, language
# detection without the letters of formulas, the formulas section of the «Тест» report. Engine replies are canned
# (fixtures written for the test, not model output).
# Usage: prompts_v08.py <work> <ui_url> <root>   (a launcher past the first run; models/my-custom-model.gguf exists)
import sys, json, os, re, time, urllib.request
from playwright.sync_api import sync_playwright
S, URL, ROOT = sys.argv[1], sys.argv[2], sys.argv[3]
BASE = URL.rstrip('/')
shots = os.path.join(S, 'shots', 'v08'); os.makedirs(shots, exist_ok=True)
res = []
def ok(c, m): res.append(('OK  ' if c else 'FAIL') + ' ' + m); print(res[-1], flush=True)
def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), headers={'Content-Type': 'application/json', 'Origin': BASE})
    return json.load(urllib.request.urlopen(req, timeout=10))
def wait_ready():
    for i in range(80):
        if json.load(urllib.request.urlopen(BASE + '/api/state'))['phase'] == 'ready': return
        time.sleep(0.5)

queue = []                  # replies for the next requests; the last one repeats
prompts = []                # bodies of the requests
def reply(route):
    body = json.loads(route.request.post_data); prompts.append(body)
    out = queue.pop(0) if len(queue) > 1 else queue[0]
    words = out.split(' ')
    chunks = ''.join('data: ' + json.dumps({'choices': [{'delta': {'content': (w if i == 0 else ' ' + w)}}]}) + '\n\n' for i, w in enumerate(words))
    chunks += 'data: ' + json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}], 'timings': {'predicted_n': 12, 'predicted_per_second': 9.5}}) + '\n\ndata: [DONE]\n\n'
    route.fulfill(status=200, headers={'Content-Type': 'text/event-stream'}, body=chunks)
def content(p): return p['messages'][0]['content']

E1 = r'$E = \hbar\omega$'; W = r'$\omega$'
SRC = r'The energy %s of a photon, where %s is the frequency.' % (E1, W)
MASKED = 'The energy {F1} of a photon, where {F2} is the frequency.'

post('/api/model', {'id': 'file:my-custom-model.gguf'}); wait_ready()
with sync_playwright() as pw:
    b = pw.chromium.launch(); ctx = b.new_context(viewport={'width': 1180, 'height': 820}, locale='ru-RU')
    ctx.grant_permissions(['clipboard-read', 'clipboard-write'])
    # an "old" window without the welcome window; only the neutral style (and «Замечания» when editing)
    ctx.add_init_script("try { sessionStorage.setItem('tdoc.window', '1'); sessionStorage.setItem('tdoc.welcome', 'done'); "
                        "if (!sessionStorage.getItem('v08')) { localStorage.setItem('tdoc.styles', JSON.stringify(['neutral', 'comments'])); sessionStorage.setItem('v08', '1'); } } catch (e) {}")
    page = ctx.new_page(); errs = []
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)
    page.route('**/v1/chat/completions', reply)
    page.goto(URL); page.wait_for_selector('body[data-model="ready"]', timeout=20000)
    page.wait_for_function("document.querySelector('#modelName').textContent.includes('my-custom-model')", timeout=20000)
    def idle(): page.wait_for_selector('#goBtn:not([hidden])', timeout=15000)
    def go():
        n = len(prompts); page.click('#goBtn'); idle(); return prompts[n:]
    def card_text(i=0): return page.evaluate('(i) => document.querySelectorAll("#cards .card .card-text")[i].textContent', i)
    def card_note(i=0): return page.evaluate('(i) => { const n = document.querySelectorAll("#cards .card .card-note")[i]; return n.hidden ? "" : n.textContent; }', i)
    def setlangs(a, c):
        page.select_option('#srcSel', a); page.select_option('#tgtSel', c); page.wait_for_timeout(100)
    def typed(text): page.fill('#src', text); page.wait_for_timeout(350)

    # ================= what counts as a formula (findMath), placeholders, cleaning
    cases = [
        (SRC, [E1, W]),
        ('costs $5 and $10 today', []),
        ('стоит 5$, а то и 10$', []),
        (r'price \$5 and $x$', ['$x$']),
        ('display $$a_{n+1} = \\alpha a_n$$ done', ['$$a_{n+1} = \\alpha a_n$$']),
        ('$$\n a = b \n$$ and $y$.', ['$$\n a = b \n$$', '$y$']),
        ('unclosed $$ a = b', []), ('unclosed $x and text', []), ('$x $ not', []), ('$ x$ not', []), ('$x$5 not', []),
        ('$n$-th term', ['$n$']), (r'$\text{if $x>0$}$ nested', [r'$\text{if $x>0$}$']), ('$a\n\nb$ two paragraphs', []),
    ]
    got = page.evaluate('(cs) => cs.map(([s]) => findMath(s).map(([a, b]) => s.slice(a, b)))', [[c[0]] for c in cases])
    bad = [(c[0], g) for c, g in zip(cases, got) if g != c[1]]
    ok(not bad, 'formulas found as expected in %d texts: %s' % (len(cases), bad[:3]))
    m = page.evaluate('(s) => maskMath(s)', 'Let $x$ and $y$, again $x$; $$z$$.')
    ok(m['masked'] == 'Let {F1} and {F2}, again {F1}; {F3}.' and m['count'] == 4 and m['list'] == '{F1}, {F2}, {F3}', 'same formulas share a placeholder: %s' % m['masked'])
    u = page.evaluate("([s, t]) => unmaskMath(t, maskMath(s))", ['Let $x$ and $y$, again $x$; $$z$$.', 'Пусть ${F1}$ и `{Ф2}` с { f 1 }; \\{F3\\} и {F9} конец'])
    ok(u['text'] == 'Пусть $x$ и $y$ с $x$; $$z$$ и конец' and u['missing'] == [], 'placeholders written slightly differently still give the formulas back: %s' % u['text'])
    ok(page.evaluate("maskMath('a set {F1} and $x$')") is None, 'a text that already has something like {F1} goes as it is')
    cl = page.evaluate(r"cleanInput('Line one\nline two with $a-\nb$ and ﬁx;   $$ a = b % c\n + d $$ ex-\nample')")
    ok(cl == 'Line one line two with $a-\nb$ and fix; $$ a = b % c\n + d $$ example', 'cleaning of pasted text leaves formulas as they are: %s' % json.dumps(cl, ensure_ascii=False))
    typed(SRC)
    ok(page.inner_text('#counter') == '%d из 1000 · формул: 2' % len(SRC), 'counter: ' + page.inner_text('#counter'))
    typed('It costs $5 and $10.')
    ok(page.inner_text('#counter') == '20 из 1000', 'currency is not a formula: ' + page.inner_text('#counter'))

    # ================= translation: placeholders in the request, formulas back in the variant
    setlangs('en', 'ru'); typed(SRC)
    queue[:] = ['Энергия {F1} фотона, где {F2} — частота.']
    ps = go()
    c0 = content(ps[0]) if ps else ''
    ok(len(ps) == 1 and c0.startswith('The text contains placeholders for mathematical formulas: {F1}, {F2}. Keep every placeholder exactly as written')
       and c0.endswith('\n\n' + MASKED) and '$' not in c0, 'request: the note and the text with placeholders, no formulas: %s' % c0[-120:])
    ok(card_text() == 'Энергия %s фотона, где %s — частота.' % (E1, W) and card_note() == '', 'variant with the formulas: ' + card_text())
    ok(page.inner_text('#runInfo') == 'Формул в тексте: 2 — они не переводятся.', 'above the variants: ' + page.inner_text('#runInfo'))
    page.screenshot(path=os.path.join(shots, '1-formulas.png'))
    # copy gives the formulas
    page.locator('#cards .card').first.locator('button[data-act="copy"]').click(); page.wait_for_timeout(200)
    ok(page.evaluate('navigator.clipboard.readText()') == card_text(), 'copied with the formulas')

    # the model lost a placeholder: the request is repeated with a reminder
    queue[:] = ['Энергия фотона, где {F2} — частота.', 'Энергия {F1} фотона, где {F2} — частота.']
    ps = go()
    ok(len(ps) == 2 and content(ps[1]).startswith('Important: your answer must contain each of these placeholders exactly as written: {F1}.\nThe text contains placeholders')
       and ps[1]['seed'] == ps[0]['seed'] + 1000, 'second request with a reminder and another seed: %s' % (content(ps[1])[:90] if len(ps) > 1 else ps))
    ok(card_text() == 'Энергия %s фотона, где %s — частота.' % (E1, W) and card_note() == '', 'after the repeat: formulas in place, no warning')
    # never came back: a warning on the variant
    queue[:] = ['Энергия фотона, где {F2} — частота.']
    ps = go()
    ok(len(ps) == 3, 'requests: 1 + 2 repeats (MATH.retries): %d' % len(ps))
    ok(card_text() == 'Энергия фотона, где %s — частота.' % W and card_note() == 'В ответе модели потерялись формулы: %s. Проверьте этот вариант.' % E1, 'warning: ' + card_note())
    page.screenshot(path=os.path.join(shots, '2-lost.png'))

    # currency is text; display formula with line breaks stays as it is
    typed('It costs $5 and $10.'); queue[:] = ['Это стоит 5 и 10 долларов.']
    ps = go()
    ok(len(ps) == 1 and 'placeholders' not in content(ps[0]) and content(ps[0]).endswith('\n\nIt costs $5 and $10.') and page.is_hidden('#runInfo'), 'no formulas: the request as before')
    DISP = '$$\na = b + c\n$$'
    typed('Consider %s for all $x$.' % DISP); queue[:] = ['Рассмотрим {F1} для всех {F2}.']
    ps = go()
    ok(content(ps[0]).endswith('\n\nConsider {F1} for all {F2}.') and card_text() == 'Рассмотрим %s для всех $x$.' % DISP, 'display formula with line breaks: %s' % json.dumps(card_text(), ensure_ascii=False))

    # back-translation: placeholders too
    typed(SRC); queue[:] = ['Энергия {F1} фотона, где {F2} — частота.']; go()
    queue[:] = ['The energy {F1} of the photon, where {F2} is its frequency.']
    n = len(prompts); page.locator('#cards .card').first.locator('button[data-act="back"]').click()
    page.wait_for_function("document.querySelector('#cards .card .card-back').textContent.includes('frequency')", timeout=10000); idle()
    bp = content(prompts[n])
    ok(bp.endswith('\n\nЭнергия {F1} фотона, где {F2} — частота.') and 'placeholders for mathematical formulas: {F1}, {F2}' in bp, 'back-translation request with placeholders')
    ok(page.inner_text('#cards .card .card-back') == 'Обратный перевод: The energy %s of the photon, where %s is its frequency.' % (E1, W), 'back-translation with the formulas')

    # glossary: a term inside a formula is not a term of the text
    typed(r'The $\text{decade}$ result holds.'); queue[:] = ['Результат {F1} верен.']
    ps = go()
    ok('Glossary:' not in content(ps[0]), 'term only inside a formula: no glossary block')
    typed(r'A decade later $x$ grew.'); queue[:] = ['Десятилетие спустя {F1} вырос.']
    ps = go()
    ok('decade → десятилетие' in content(ps[0]) and content(ps[0]).startswith('The text contains placeholders'), 'term outside the formula: in the glossary block')

    # ================= editing: placeholders, but «Замечания» see the formulas
    RU = r'Пусть $\alpha = \beta$ и $\gamma$ малы.'
    setlangs('ru', 'ru'); typed(RU)
    queue[:] = ['Пусть {F1} и {F2} малы.', 'Замечаний нет.']
    ps = go()
    ok(len(ps) == 2 and 'placeholders' in content(ps[0]) and content(ps[0]).endswith('\n\nПусть {F1} и {F2} малы.'), 'corrected: with placeholders')
    ok(content(ps[1]).startswith('Check the following Russian text') and content(ps[1]).endswith('\n\n' + RU) and 'placeholders' not in content(ps[1]), '«Замечания»: the formulas as they are')
    ok(page.evaluate('document.querySelector("#cards .card .card-diff").textContent') == RU, 'corrected text: formulas in place, no changes shown')

    # ================= language: letters of formulas do not count
    setlangs('auto', 'auto'); typed(RU)
    ok(page.inner_text('#modeBadge') == 'русский → английский', '«Авто» detects Russian despite Latin letters in formulas: ' + page.inner_text('#modeBadge'))
    setlangs('ru', 'en'); typed(RU)
    ok(page.is_hidden('#langHint'), 'no «Текст похож на английский» hint')
    page.evaluate('MATH.on = false'); typed(RU + ' Да.')
    ok(page.is_visible('#langHint'), 'with MATH.on = false formulas are ordinary text again (the hint shows)')
    queue[:] = ['Let $\\alpha = \\beta$ and $\\gamma$ be small. Yes.']
    ps = go()
    ok(content(ps[0]).endswith('\n\n' + RU + ' Да.') and 'placeholders' not in content(ps[0]), 'MATH.on = false: the request has the formulas')
    page.evaluate('MATH.on = true')

    # ================= Hy-MT2: its official template, the text with placeholders, no note
    post('/api/model', {'id': 'q4'}); wait_ready()
    page.evaluate('refreshState()'); page.wait_for_function("document.querySelector('#modelName').textContent.includes('Hy-MT2')", timeout=20000)
    setlangs('en', 'ru'); typed(SRC); queue[:] = ['Энергия {F1} фотона, где {F2} — частота.']
    ps = go()
    ok(content(ps[0]) == 'Translate the following text into Russian. Note that you should only output the translated result without any additional explanation:\n\n' + MASKED, 'Hy-MT2: official template with placeholders: %s' % content(ps[0])[:100])
    ok(card_text() == 'Энергия %s фотона, где %s — частота.' % (E1, W), 'Hy-MT2: formulas back in the variant')

    # ================= «Тест»: phrases with formulas (the test's own three phrases: MATH_TESTS in the program may change)
    page.evaluate(r'''MATH_TESTS.splice(0, MATH_TESTS.length,
      { en: 'The energy of a photon is $E = \\hbar\\omega$, where $\\omega$ is its angular frequency.',
        ru: 'Энергия фотона равна $E = \\hbar\\omega$, где $\\omega$ — его угловая частота.' },
      { en: 'For $n \\ge 1$ the coefficients satisfy $$a_{n+1} = \\alpha_n a_n + \\beta_n a_{n-1},$$ which defines a three-term recurrence relation.',
        ru: 'При $n \\ge 1$ коэффициенты удовлетворяют соотношению $$a_{n+1} = \\alpha_n a_n + \\beta_n a_{n-1},$$ которое задаёт трёхчленное рекуррентное соотношение.' },
      { en: 'The intensity $I(r) = I_0 \\exp(-2r^2/w_0^2)$ of a Gaussian beam drops to $I_0/e^2$ at $r = w_0$.',
        ru: 'Интенсивность гауссова пучка $I(r) = I_0 \\exp(-2r^2/w_0^2)$ падает до $I_0/e^2$ при $r = w_0$.' })''')
    queue[:] = ['Ответ {F1} и {F2}.']   # the third phrase has three formulas: the third one is always lost
    page.click('#testBtn'); page.wait_for_timeout(300)
    ok('Ещё 6 переводов фраз с формулами LaTeX' in page.inner_text('#testIntro'), 'test intro: ' + page.inner_text('#testIntro')[-120:])
    page.click('#runTestBtn')
    page.wait_for_function("document.querySelector('#testProgressText').textContent.startsWith('Готово')", timeout=120000)
    page.wait_for_function("document.querySelector('#testSummary').textContent.includes('Отчёт сохранён')", timeout=15000)
    summary = page.inner_text('#testSummary')
    ok('Формулы LaTeX на месте: 4 из 6; повторов запроса: 4.' in summary and 'Формулы LaTeX' in page.inner_text('#testSummary table'), 'test summary: %s' % [l for l in summary.splitlines() if 'Формулы' in l])
    rep = sorted(f for f in os.listdir(os.path.join(ROOT, 'data', 'reports')) if f.endswith('.md'))
    md = open(os.path.join(ROOT, 'data', 'reports', rep[-1]), encoding='utf-8').read()
    sec = md.split('## Формулы LaTeX', 1)[1] if '## Формулы LaTeX' in md else ''
    ok(sec.count('### Формулы ') == 6 and '- Формулы: потерялись: $r = w_0$; повторов запроса: 2' in sec and '- Формулы: на месте' in sec, 'report section on formulas')
    ok('- Перевод модели: Ответ $E = \\hbar\\omega$ и $\\omega$.' in sec, 'report: formulas back in the translation')
    js = json.load(open(os.path.join(ROOT, 'data', 'reports', rep[-1][:-3] + '.json'), encoding='utf-8'))
    mres = [r for r in js['results'] if r['kind'] == 'math']
    ok(len(mres) == 6 and all(r['formulas'] >= 2 for r in mres) and sum(len(r['lost']) for r in mres) == 2, 'report data: formulas, lost, tries')
    page.screenshot(path=os.path.join(shots, '3-test.png'))
    page.click('#closeTestBtn')
    ok(not errs, 'no console errors: %s' % errs[:3])
    b.close()

print('FAILS:', sum(1 for x in res if x.startswith('FAIL')), 'of', len(res))
