# v0.9.1: «Учебный пример» — the ▾ window (level, topic from the list of the language or your own), the exercise in
# «Спросить модель» (items without answers, the model checks your answers), «Проверить» (a second request that
# checks the lesson), with canned engine replies (fixtures written for the test, not model output).
# Usage: prompts_v091.py <work> <ui_url>   (a launcher past the first run; models/my-custom-model.gguf must exist in the root)
import sys, json, os, re, time, urllib.request
from playwright.sync_api import sync_playwright
S, URL = sys.argv[1], sys.argv[2]
shots = os.path.join(S, 'shots', 'v091'); os.makedirs(shots, exist_ok=True)
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
    ctx.add_init_script("try { sessionStorage.setItem('tdoc.window', '1'); sessionStorage.setItem('tdoc.welcome', 'done') } catch (e) {}")
    page = ctx.new_page(); errs = []
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.on('console', lambda m: errs.append(m.text) if m.type == 'error' and 'status of 503' not in m.text else None)
    page.route('**/v1/chat/completions', reply)
    page.goto(URL); page.wait_for_selector('body[data-model="ready"]', timeout=20000)
    page.wait_for_function("document.querySelector('#modelName').textContent.includes('my-custom-model')", timeout=20000)
    W = page.evaluate('LESSON')
    topics = lambda code: [x['en'] for x in W['topics']['all'] + W['topics'].get(code, [])]
    def idle(): page.wait_for_selector('#goBtn:not([hidden])', timeout=15000)
    def wait_request(n):
        for i in range(150):
            if len(prompts) > n: return True
            page.wait_for_timeout(100)
        return False
    def chat_idle(n):
        wait_request(n)
        page.wait_for_function("document.querySelector('#askSend').textContent === 'Ввод' && !document.querySelector('#askLog .msg.pending')", timeout=15000)
    def last_user(p): return p['messages'][-1]['content']
    def menu_items(): return page.locator('#popMenu .mi > span:first-child').all_inner_texts()
    def open_menu():
        if not page.is_hidden('#popMenu'): page.keyboard.press('Escape')
        page.click('#lessonMore'); page.wait_for_selector('#popMenu:not([hidden])')

    page.select_option('#srcSel', 'ru'); page.select_option('#tgtSel', 'en'); page.fill('#src', '')

    # ================= the ▾ window
    ok(page.is_visible('#lessonMore') and 'уровень, тема' in page.get_attribute('#lessonMore', 'title'), 'the ▾ button next to «Учебный пример»: ' + str(page.get_attribute('#lessonMore', 'title')))
    open_menu()
    chips = page.locator('#popMenu .seg button')
    ok(chips.all_inner_texts() == ['Начальный', 'Средний', 'Продвинутый'] and chips.nth(1).get_attribute('aria-pressed') == 'true'
       and chips.nth(0).get_attribute('title') == 'A1–A2', 'levels; «Средний» is the default: %s' % chips.all_inner_texts())
    opts = page.locator('#lessonTopicSel option')
    labels = opts.all_inner_texts()
    ok(page.inner_text('#popMenu .lo-label >> nth=1') == 'Тема (русский)' and opts.count() == 1 + len(W['topics']['all']) + len(W['topics']['ru']) + 1
       and labels[0] == 'Любая (каждый раз другая)' and 'Падежи существительных' in labels and labels[-1] == 'Своя тема…',
       'topics of the language of the text, in the interface language: %d, %s' % (opts.count(), labels[:3]))
    ok(page.is_hidden('#lessonOwnTopic'), 'the field for your own topic is hidden until «Своя тема…»')
    ok(menu_items() == ['Пример в поле текста', 'Упражнение в «Спросить модель»'], 'actions without a lesson in the field: %s' % menu_items())
    chips.nth(0).click()
    ok(not page.is_hidden('#popMenu') and chips.nth(0).get_attribute('aria-pressed') == 'true' and chips.nth(1).get_attribute('aria-pressed') == 'false'
       and page.evaluate("localStorage.getItem('tdoc.lessonLevel')") == '"beginner"', 'a level is chosen and remembered; the window stays open')
    page.select_option('#lessonTopicSel', 'prepositions')
    ok(page.evaluate("localStorage.getItem('tdoc.lessonTopic')") == '"prepositions"', 'a topic is chosen and remembered')
    page.screenshot(path=os.path.join(shots, '1-menu.png'))

    # ================= «Пример в поле текста» with the level and the topic
    LESSON1 = 'Предлог «в» — внутри: в доме. Предлог «на» — на поверхности: на столе.'
    queue[:] = [LESSON1]
    n = len(prompts); page.locator('#popMenu .mi', has_text='Пример в поле текста').click(); idle()
    c = prompts[-1]['messages'][0]['content']
    m = re.fullmatch(r'Write (.+) about prepositions, for beginner \(A1–A2\) learners of Russian\. Write everything in Russian only, in very simple words and short sentences, in at most five short lines\. Do not add a title, a translation, Markdown formatting or any other comments\.', c)
    ok(bool(m) and m.group(1) in W['kinds'] and len(prompts) == n + 1 and page.is_hidden('#popMenu'), 'request with the level and the topic: ' + c)
    ok(page.input_value('#src') == LESSON1 and page.inner_text('#lessonCheck') == 'Проверить', 'the lesson is in the field, «Проверить» under it')

    # ================= «Проверить»: the second request, in «Спросить модель»
    page.click('#tabGloss')
    CHECK = 'Всё верно: «в доме», «на столе».'
    queue[:] = [CHECK]
    n = len(prompts); page.click('#lessonCheck'); chat_idle(n)
    p = prompts[-1]
    want = 'Проверь этот учебный пример (язык — русский): верны ли правило, примеры и ответы? Если что-то неверно, объясни ошибку и напиши исправленный вариант.\n\n' + LESSON1
    ok(page.is_visible('#askPane') and p['messages'][0]['role'] == 'system' and last_user(p) == want and len(p['messages']) == 2, 'the check question: %r' % last_user(p)[:120])
    ok(p['temperature'] == W['checkSampling']['temperature'] == 0.2, 'the check is asked with a low temperature: %s' % p['temperature'])
    ok(page.locator('#askLog .msg.user').last.inner_text() == want and CHECK in page.locator('#askLog .msg.bot').last.inner_text(), 'question and answer are in the chat')

    # the window remembers the choice and offers the check while the lesson is in the field
    open_menu()
    ok(chips.nth(0).get_attribute('aria-pressed') == 'true' and page.input_value('#lessonTopicSel') == 'prepositions', 'the window shows the remembered level and topic')
    ok(menu_items()[-1] == 'Проверить пример в поле', 'with a lesson in the field the window offers the check: %s' % menu_items())
    page.keyboard.press('Escape')
    page.type('#src', '!')
    ok(page.inner_text('#cleanNote') == '', 'changing the text removes the note and «Проверить»')
    open_menu()
    ok('Проверить пример в поле' not in menu_items(), 'no check of a changed text: %s' % menu_items())

    # ================= your own topic
    page.select_option('#lessonTopicSel', '*')
    ok(page.is_visible('#lessonOwnTopic') and page.evaluate('document.activeElement.id') == 'lessonOwnTopic', '«Своя тема…» shows the field and focuses it')
    page.fill('#lessonOwnTopic', 'дроби и проценты')
    ok(page.evaluate("localStorage.getItem('tdoc.lessonOwnTopic')") == '"дроби и проценты"', 'your own topic is remembered')
    page.keyboard.press('Escape'); page.fill('#src', ''); open_menu()
    ok(page.input_value('#lessonTopicSel') == '*' and page.input_value('#lessonOwnTopic') == 'дроби и проценты', 'your own topic is shown again')
    queue[:] = ['Половина — это одна вторая: 1/2.']
    n = len(prompts); page.press('#lessonOwnTopic', 'Enter'); idle()
    ok(len(prompts) == n + 1 and ' about дроби и проценты, for beginner (A1–A2) learners of Russian.' in prompts[-1]['messages'][0]['content'], 'Enter in the field: a lesson on your own topic')

    # ================= the exercise in «Спросить модель»
    EX = '1. Одна ___ (вторая) пирога.\n2. Пятьдесят ___ (процент).'
    queue[:] = [EX]
    open_menu()
    n = len(prompts); page.locator('#popMenu .mi', has_text='Упражнение в «Спросить модель»').click(); chat_idle(n)
    p = prompts[-1]
    want = 'Дай мне короткое упражнение. Язык — русский, уровень — начальный, тема — дроби и проценты. Напиши 3–5 пронумерованных заданий: вставить пропущенное слово или выбрать правильную форму. Задания — на этом языке, объяснения — по-русски. Ответов не показывай: я отвечу, а ты проверишь каждый ответ и коротко объяснишь ошибки.'
    ok(last_user(p) == want, 'the exercise question: %r' % last_user(p))
    ok(p['temperature'] == W['sampling']['temperature'] and len(p['messages']) == 4, 'varied (temperature %s), after the earlier check in the same chat (%d messages)' % (p['temperature'], len(p['messages'])))
    ok(page.input_value('#src') == 'Половина — это одна вторая: 1/2.', 'the exercise does not touch the text field')
    page.screenshot(path=os.path.join(shots, '2-exercise.png'))
    # your answers: an ordinary chat question, the model sees the exercise
    queue[:] = ['1 — верно. 2 — правильно «процентов».']
    page.fill('#askInput', '1. вторая 2. процента')
    n = len(prompts); page.press('#askInput', 'Enter'); chat_idle(n)
    p = prompts[-1]
    ok(last_user(p) == '1. вторая 2. процента' and p['messages'][-3]['content'] == want and p['messages'][-2]['content'] == EX
       and p['temperature'] == page.evaluate('ASK.sampling.temperature'), 'the answers go with the exercise, usual chat settings')

    # ================= topics of another language; a topic of one language is not used for another
    page.select_option('#srcSel', 'de'); open_menu()
    ok(page.inner_text('#popMenu .lo-label >> nth=1') == 'Тема (немецкий)' and 'Trennbare' not in ''.join(opts.all_inner_texts())
       and 'Глаголы с отделяемыми приставками' in opts.all_inner_texts(), 'German: its own topics')
    page.select_option('#lessonTopicSel', 'separable verbs')
    page.locator('#popMenu .seg button', has_text='Продвинутый').click()
    queue[:] = ['Ich rufe dich morgen an.']
    page.keyboard.press('Escape'); page.fill('#src', '')
    n = len(prompts); page.click('#lessonBtn'); idle()
    c = prompts[-1]['messages'][0]['content']
    ok(' about separable verbs, for advanced (C1–C2) learners of German. Write everything in German only, in clear, natural language, ' in c, 'German, advanced: ' + c[:150])
    page.select_option('#srcSel', 'ru'); open_menu()
    ok(page.input_value('#lessonTopicSel') == '', 'Russian: the German topic is not in the list, «Любая» is shown')
    page.keyboard.press('Escape')
    seen = []
    for i in range(4):
        page.fill('#src', ''); queue[:] = ['Пример номер %d.' % i]
        page.click('#lessonBtn'); idle()
        m = re.search(r'.* about (.+), for advanced \(C1–C2\) learners of Russian\.', prompts[-1]['messages'][0]['content'])
        seen.append(m.group(1) if m else None)
    ok(all(x in topics('ru') for x in seen) and len(set(seen)) == 4, 'random topics of the language, no repeats in a row: %s' % seen)

    # ================= without a model: the usual hint, no request
    post('/api/unload'); page.evaluate('refreshState()'); page.wait_for_selector('body[data-model="unloaded"]', timeout=10000)
    page.fill('#src', ''); open_menu()
    n = len(prompts); page.locator('#popMenu .mi', has_text='Упражнение в «Спросить модель»').click(); page.wait_for_timeout(300)
    ok(len(prompts) == n and 'Please load a model.' in page.inner_text('#toast'), 'exercise without a model: Please load a model.')
    post('/api/load'); wait_phase('ready'); page.evaluate('refreshState()'); page.wait_for_selector('body[data-model="ready"]', timeout=20000)

    # ================= the window type «Окно Ttranslator (проба)»: the reason why it did not open (state of the launcher)
    page.evaluate("STATE.window = { available: true, error: 'нет веб-движка системы', pages: 0 }; showPane('settings'); renderSettings()")
    ok(page.is_visible('#modeErr') and page.inner_text('#modeErr') == 'Своё окно не открылось: нет веб-движка системы. Открыто окно Edge или Chrome.', 'settings show why the own window did not open: ' + page.inner_text('#modeErr'))
    page.evaluate("STATE.window = { available: true, error: '', pages: 0 }; renderSettings()")
    ok(page.is_hidden('#modeErr') and page.is_enabled('#modeSeg button[data-v="window"]'), 'no reason, the choice is available')
    page.evaluate("showPane('results')")

    # help
    page.click('#helpBtn'); page.wait_for_timeout(200)
    h = page.inner_text('#helpBody')
    ok('Стрелка ▾ у кнопки «Учебный пример»' in h and 'Кнопка «Проверить» под полем' in h, 'help describes the level, the topic, the exercise and the check')
    page.click('#closeHelpBtn')
    ok(not errs, 'no console errors: %s' % errs[:3])
    b.close()

print('FAILS:', sum(1 for x in res if x.startswith('FAIL')), 'of', len(res))
