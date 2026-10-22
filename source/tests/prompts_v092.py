# v0.9.2: «Учебный пример» — the strict request (title or question first, answer or tip last, low temperature), the
# kinds taking turns, topics without stress and pronunciation; the check before the lesson is shown (a second request
# with temperature 0: «OK» keeps the lesson, a corrected lesson replaces it, a comment or a text in another language is
# ignored), the check box in the ▾ window, the note «возможны неточности и ошибки» with «Уточнить»; «О программе»:
# voices for reading aloud. Canned engine replies (fixtures written for the test, not model output).
# Usage: prompts_v092.py <work> <ui_url>   (a launcher past the first run; models/my-custom-model.gguf must exist in the root)
import sys, json, os, re, time, urllib.request
from playwright.sync_api import sync_playwright
S, URL = sys.argv[1], sys.argv[2]
shots = os.path.join(S, 'shots', 'v092'); os.makedirs(shots, exist_ok=True)
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
    # every text the note under the field shows
    page.evaluate("window.__notes = []; new MutationObserver(() => __notes.push($('#cleanNote').textContent)).observe($('#cleanNote'), { childList: true, characterData: true, subtree: true })")
    def idle(): page.wait_for_selector('#goBtn:not([hidden])', timeout=15000)
    def content(p): return p['messages'][0]['content']
    def lesson(replies):
        queue[:] = replies
        page.fill('#src', ''); n = len(prompts)
        page.click('#lessonBtn'); idle()
        return prompts[n:]
    page.select_option('#srcSel', 'ru'); page.select_option('#tgtSel', 'en')

    # ================= the strict request, low temperature, safer topics
    ok(W['sampling']['temperature'] == 0.2 and W['checkSampling']['temperature'] == 0 and W['selfCheck'] is True, 'temperatures: lesson 0.2, check 0; the check is on by default')
    all_topics = [x['en'] for v in W['topics'].values() for x in v]
    ok(not any(t in all_topics for t in ('stress in words', 'pronunciation', 'idioms', 'tones', 'liaison')), 'no topics with stress, pronunciation, idioms, tones, liaison')
    ok(len(W['kinds']) == 4 and not any('curious' in k['what'] for k in W['kinds']) and all(k['body'] and k['last'] for k in W['kinds']), 'four kinds, no «curious fact»: %s' % [k['what'] for k in W['kinds']])

    # ================= the check finds nothing: «OK» keeps the lesson
    A = 'Предлоги «в» и «на»\nВ — внутри: Книга в сумке.\nНа — на поверхности: Книга на столе.\nСовет: спросите себя, внутри предмет или сверху.'
    ps = lesson([A, 'OK'])
    ok(len(ps) == 2, 'two requests: the lesson and its check (%d)' % len(ps))
    c = content(ps[0])
    lines = c.split('\n')
    ok(lines[0] == 'You are an experienced, careful teacher of Russian. Write a short lesson for intermediate (B1–B2) learners of Russian.'
       and lines[1].startswith('Topic: ') and lines[2].startswith('Type: ') and 'Accuracy is more important than originality:' in c
       and 'Use only standard rules and facts of Russian, as in school textbooks, that you are completely sure of.' in c
       and 'Do not invent words, rules, exceptions or facts.' in c and '- first line: a short title or question;' in c and 'No Markdown, no translation, no other comments.' in c,
       'the lesson request: ' + c.replace('\n', ' | ')[:260])
    ok(ps[0]['temperature'] == 0.2 and ps[0]['top_k'] == 40, 'the lesson is asked with temperature 0.2')
    k = content(ps[1])
    ok(k.startswith('You are a strict proofreader and an expert teacher of Russian. Check the lesson below, written for intermediate (B1–B2) learners of Russian:')
       and 'If everything is correct, reply with the single word OK.' in k and k.endswith('Lesson:\n' + A), 'the check request: ' + k.replace('\n', ' | ')[:200])
    ok(ps[1]['temperature'] == 0 and ps[1]['top_k'] == 1 and ps[1]['seed'] == 1, 'the check: temperature 0, the most likely words: %s' % {x: ps[1][x] for x in ('temperature', 'top_k', 'seed')})
    ok(page.input_value('#src') == A, '«OK»: the lesson is shown as it was')
    ok('Проверяю пример…' in page.evaluate('__notes'), 'while checking, the note says «Проверяю пример…»')
    note = page.inner_text('#cleanNote')
    ok(note.startswith('Пример придуман моделью — возможны неточности и ошибки') and page.inner_text('#lessonCheck') == 'Уточнить'
       and page.get_attribute('#cleanNote', 'title') == 'Модель проверила пример и ошибок не нашла', 'the note «возможны неточности и ошибки» with «Уточнить»; hint: %s' % page.get_attribute('#cleanNote', 'title'))
    page.screenshot(path=os.path.join(shots, '1-lesson-checked.png'))

    # ================= the check corrects the lesson
    B = 'Винительный падеж\nЯ читаю интересный книга.\nОтвет: винительный падеж, «книга».'
    B2 = 'Винительный падеж\nЯ читаю интересную книгу.\nОтвет: винительный падеж, «книгу».'
    lesson([B, B2])
    ok(page.input_value('#src') == B2 and page.get_attribute('#cleanNote', 'title') == 'Модель проверила пример и исправила его', 'a corrected lesson replaces the first one')
    # a comment before the corrected lesson is dropped
    C = 'Глаголы движения\nОн идёт в школа каждый день.\nОтвет: идёт.'
    C2 = 'Глаголы движения\nОн ходит в школу каждый день.\nОтвет: ходит — регулярное движение.'
    lesson([C, 'В примере ошибка: нужно «в школу» и «ходит».\nИсправленный пример:\n' + C2])
    ok(page.input_value('#src') == C2, 'the text after «Исправленный пример:» is taken: %r' % page.input_value('#src'))
    # a comment instead of a lesson, or a text in another language: the lesson stays as it was
    D = 'Мягкий знак\nКонь — кони, день — дни.\nСовет: ь показывает мягкость согласного.'
    lesson([D, 'Это хороший урок, но можно было бы добавить побольше заданий для самостоятельной практики.'])
    ok(page.input_value('#src') == D and page.get_attribute('#cleanNote', 'title') == '', 'a comment is not taken: the lesson stays (no hint)')
    E = 'Частицы не и ни\nНе — отрицание: Я не знаю.\nНи — усиление: Ни одного облака.\nСовет: «ни» усиливает отрицание.'
    lesson([E, 'The lesson is mostly correct, but the second example should use a full sentence with a verb.'])
    ok(page.input_value('#src') == E, 'an answer in another language is not taken: the lesson stays')
    F = 'Род существительных\nСтол — он, лампа — она, окно — оно.\nСовет: смотрите на окончание.'
    lesson([F, '**OK**'])
    ok(page.input_value('#src') == F and page.get_attribute('#cleanNote', 'title') == 'Модель проверила пример и ошибок не нашла', '«**OK**» with Markdown is «OK» too')

    # ================= the kinds take turns (with a low temperature, the same topic gives different lessons)
    page.click('#lessonMore'); page.wait_for_selector('#popMenu:not([hidden])')
    page.select_option('#lessonTopicSel', 'prepositions')
    ok(page.is_checked('#lessonSelfCheck') and 'Проверять пример перед показом' in page.inner_text('#popMenu'), 'the check box in the ▾ window: on')
    page.uncheck('#lessonSelfCheck')
    ok(page.evaluate("localStorage.getItem('tdoc.lessonSelfCheck')") == 'false', 'the check box is remembered')
    page.keyboard.press('Escape')
    kinds = []
    for i in range(3):
        ps = lesson(['Предлоги места номер %d\nКнига в сумке.\nСовет: внутри — «в».' % i])
        ok(len(ps) == 1, 'without the check: one request (%d)' % len(ps)) if i == 0 else None
        kinds.append(re.search(r'\nType: (.+)\.\n', content(ps[0])).group(1))
    ok(len(set(kinds)) == 3 and all('Topic: prepositions.' in content(p) for p in prompts[-3:]), 'three lessons on one topic, three different kinds: %s' % kinds)
    page.click('#lessonMore'); page.wait_for_selector('#popMenu:not([hidden])')
    page.select_option('#lessonTopicSel', ''); page.check('#lessonSelfCheck'); page.keyboard.press('Escape')

    # ================= «О программе»: models for reading aloud
    f = page.evaluate('ABOUT.ru.features')
    i = next((j for j, x in enumerate(f) if x.startswith('Выбор различных LLM-моделей')), -1)
    ok(i >= 0 and f[i + 1] == 'Выбор различных моделей для чтения вслух.', 'About: «Выбор различных моделей для чтения вслух.» after the LLM models: %s' % f)
    ok(page.evaluate('ABOUT.en.features').count('A choice of different models for reading aloud.') == 1 and page.evaluate('ABOUT.de.features').count('Auswahl verschiedener Modelle zum Vorlesen.') == 1, 'About: in English and German too')
    page.click('#aboutBtn') if page.is_visible('#aboutBtn') else page.evaluate("showPane('about')")
    page.wait_for_timeout(300)
    ok('Выбор различных моделей для чтения вслух.' in page.inner_text('body'), 'About shows the new line')

    ok(not errs, 'no console errors: %s' % errs[:3])
    b.close()

print('FAILS:', sum(1 for x in res if x.startswith('FAIL')), 'of', len(res))
