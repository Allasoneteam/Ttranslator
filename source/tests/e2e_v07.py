# End-to-end test of version 0.7: the welcome window (over the first-start screen and at later starts; the
# interface language chosen there, the window type, «load the chosen model at start», «show this window at start»);
# the first-start screen and the model menu show where a file comes from, the folder it goes to and its name
# before a download; «Свой вариант» below the variants (write, take a variant as a basis, save, replace, remove);
# the start options in «Настройки»; restarts of the launcher: the model not loaded at start, and the welcome
# window's choice applied once, at start.
# Launcher + engine with a stand-in model + UI in Chromium; translations are canned replies (fixtures written for
# the test, not model output).
# Usage: e2e_v07.py <work> <ui_url> <root> <engine_url> <models.json>   (a launcher in a fresh folder BEFORE the
# first run; the test restarts it three times itself, with the same engine address and test models, and ends by
# closing it with Exit)
import sys, json, os, time, subprocess, urllib.request
from playwright.sync_api import sync_playwright
S, URL, ROOT, ENGINE_URL, MODELS = sys.argv[1:6]
BASE = URL.rstrip('/')
PORT = BASE.rsplit(':', 1)[1]
shots = os.path.join(S, 'shots', 'v07'); os.makedirs(shots, exist_ok=True)
log = []
def ok(cond, msg):
    log.append(('OK  ' if cond else 'FAIL') + ' ' + msg); print(log[-1], flush=True)
def cfg():
    return json.load(open(os.path.join(ROOT, 'config.json'), encoding='utf-8'))
def api(path):
    return json.load(urllib.request.urlopen(BASE + path, timeout=5))
def post(path, body=None):
    req = urllib.request.Request(BASE + path, data=json.dumps(body or {}).encode(), method='POST',
                                 headers={'Content-Type': 'application/json', 'Origin': BASE})
    return json.load(urllib.request.urlopen(req, timeout=5))
def alive():
    try:
        urllib.request.urlopen(BASE + '/api/ping', timeout=1); return True
    except Exception:
        return False
def engine_running():
    return bool(subprocess.run(['pgrep', '-f', ROOT + '/engine/'], capture_output=True, text=True).stdout.strip())
def wait(pred, t=10):
    end = time.time() + t
    while time.time() < end:
        try:
            if pred(): return True
        except Exception:
            pass
        time.sleep(0.2)
    return False
def ready(page, t=60000):
    page.wait_for_selector('body[data-model="ready"]', timeout=t)
def toast(page):
    return page.inner_text('#toast')
def texts(page, sel):
    return [x.strip() for x in page.locator(sel).all_inner_texts()]
def pressed(page, seg):
    return page.evaluate("(s) => { const b = document.querySelector(s + ' button[aria-pressed=\"true\"]'); return b ? b.dataset.v : null; }", seg)
def langs(page):
    return page.input_value('#srcSel'), page.input_value('#tgtSel')
def switch_lang(page, sel, lang):
    with page.expect_navigation(timeout=15000):
        page.select_option(sel, lang)
def saved_rows():
    p = os.path.join(ROOT, 'data', 'saved', 'Сохранённые.tsv')
    lines = open(p, encoding='utf-8-sig', newline='').read().split('\r\n')
    return [l.split('\t') for l in lines[1:] if l]
def own_rows():   # entries of «Свой вариант»: [id, time, from, to, style, source, translation, context]
    return [r for r in saved_rows() if r[4] == 'Свой вариант']
def is_on(page, sel):
    return 'on' in (page.get_attribute(sel, 'class') or '').split()

# Russian letters in texts and hints, except user content and the list of interface languages (as in e2e_v06.py)
SCAN = r'''() => {
  const cyr = /[А-Яа-яЁё]/;
  const user = '#src, #ctx, #customStyle, .card-text, .card-back, .card-diff, .msg-body, #glossTable tbody, #savedList .src, #savedList .tr, #uiLangSel, #setupLangSel, #welcomeLangSel, #glossFile, #savedFile, script, style';
  const bad = [];
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (w.nextNode()) {
    const n = w.currentNode, x = n.nodeValue.trim();
    if (x && cyr.test(x) && !n.parentElement.closest(user)) bad.push(x.slice(0, 70));
  }
  for (const e of document.body.querySelectorAll('[title], [placeholder], [aria-label]')) {
    if (e.closest('#glossTable tbody input, .msg-body, .card-text, #savedList .src, #savedList .tr')) continue;
    for (const a of ['title', 'placeholder', 'aria-label']) { const v = e.getAttribute(a); if (v && cyr.test(v)) bad.push(a + ': ' + v.slice(0, 70)); }
  }
  return bad;
}'''

# different texts for the variants: equal variants would be merged into one card
REPLIES = ['The laser pulse is compressed.', 'The laser pulse was compressed.', 'The pulse of the laser is compressed.']
served = []
def reply(route):
    words = REPLIES[len(served) % len(REPLIES)].split(' '); served.append(1)
    out = ''.join('data: ' + json.dumps({'choices': [{'delta': {'content': (w if i == 0 else ' ' + w)}}]}) + '\n\n' for i, w in enumerate(words))
    out += 'data: ' + json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}], 'timings': {'predicted_n': 5, 'predicted_per_second': 9.5}}) + '\n\ndata: [DONE]\n\n'
    route.fulfill(status=200, headers={'Content-Type': 'text/event-stream'}, body=out)
def translate(page, text):
    page.fill('#src', text); page.wait_for_timeout(300)
    page.click('#goBtn'); page.wait_for_selector('#goBtn:not([hidden])', timeout=30000)
    page.wait_for_selector('#cards .card:not(.pending)', timeout=10000)

procs = []
def restart():
    # the running launcher exits (Exit, or by itself once its last window has closed), a new one starts in the
    # same folder with the same engine address and test models
    try: post('/api/quit')
    except Exception: pass
    if not wait(lambda: not alive(), 20): return False
    lf = open(os.path.join(S, 'launcher-v07.log'), 'a')
    env = dict(os.environ, TDOC_ENGINE_URL=ENGINE_URL, TDOC_TEST_MODELS=MODELS)
    procs.append(subprocess.Popen(['./ttranslator', '--no-window', '--port', PORT], cwd=ROOT, env=env, stdout=lf, stderr=lf))
    return wait(alive, 15)

errors = []
def watch(page):
    page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.route('**/v1/chat/completions', reply)
    return page

try:
  with sync_playwright() as p:
      b = p.chromium.launch()
      VERSION = api('/api/ping')['version']
      def window():
          c = b.new_context(viewport={'width': 1180, 'height': 800}, locale='ru-RU', color_scheme='light')
          c.add_init_script('window.close = () => {};')
          c.grant_permissions(['clipboard-read', 'clipboard-write'])
          return c, watch(c.new_page())

      # ================= the welcome window over the first-start screen
      ctx, page = window()
      page.goto(URL)
      page.wait_for_selector('#welcomeView:not([hidden])', timeout=15000)
      ok(page.evaluate('document.body.dataset.model') == 'setup' and page.is_visible('#setupView'), 'first start: the welcome window opens over the first-start screen')
      NEW = page.evaluate('WHATS_NEW')   # «Что нового» меняется с каждой версией
      ok(page.inner_text('#welcomeVersion') == 'Версия ' + VERSION and page.inner_text('#welcomeNewTitle') == 'Что нового в версии ' + NEW['version'] and page.locator('#welcomeNew li').count() == len(NEW['ru']) > 0,
         'version and «Что нового»: %s; %s; %d items' % (page.inner_text('#welcomeVersion'), page.inner_text('#welcomeNewTitle'), page.locator('#welcomeNew li').count()))
      ok(page.input_value('#welcomeLangSel') == 'ru' and texts(page, '#welcomeLangSel option') == ['English', 'Русский', 'Deutsch', 'Español', '中文'], 'interface language: %s' % texts(page, '#welcomeLangSel option'))
      ok(pressed(page, '#welcomeModeSeg') == 'window' and page.is_checked('#welcomeLoad') and page.is_checked('#welcomeShow'), 'defaults: app window, load the model at start, show this window')
      ok(texts(page, '#welcomeModeSeg button') == ['Окно приложения', 'Вкладка браузера'] and page.get_attribute('#welcomeModeSeg button >> nth=0', 'data-v') == 'window',
         'two window types, the app window (own window) first (0.9.2): %s' % texts(page, '#welcomeModeSeg button'))
      ok(page.inner_text('#welcomeModel') == '(Hy-MT2-1.8B · Q4_K_M (test))', 'the chosen model is named: ' + page.inner_text('#welcomeModel'))
      ok(page.evaluate('document.activeElement && document.activeElement.id') == 'welcomeStart', 'focus on «Начать работу»')
      ok(page.is_hidden('#welcomeAbout'), 'no «О программе» over the first-start screen (it is a panel of the work window)')
      page.screenshot(path=os.path.join(shots, '1-welcome.png'))
      page.click('#welcomeModeSeg button[data-v="tab"]')
      ok(wait(lambda: cfg().get('launch_mode') == 'tab' and pressed(page, '#welcomeModeSeg') == 'tab'), 'window type «Вкладка браузера» saved in config.json')

      # the interface language from the welcome window: it stays open, the start languages follow
      switch_lang(page, '#welcomeLangSel', 'en')
      page.wait_for_selector('#welcomeView:not([hidden])', timeout=15000)
      ok(page.inner_text('#welcomeNewTitle') == 'What’s new in version ' + NEW['version'] and page.inner_text('#welcomeStart') == 'Get started' and cfg()['ui_language'] == 'en',
         'English chosen in the welcome window: it opens again, in English')
      ok(page.inner_text('#welcomeNew li') == NEW['en'][0] and pressed(page, '#welcomeModeSeg') == 'tab', 'what is new in English, choices kept')
      ok(langs(page) == ('en', 'ru'), 'start languages follow the new interface language: %s → %s' % langs(page))
      bad = page.evaluate(SCAN)
      ok(not bad, 'no Russian in the welcome window and the first-start screen: %s' % bad[:5])
      page.screenshot(path=os.path.join(shots, '2-welcome-en.png'))
      switch_lang(page, '#welcomeLangSel', 'ru')
      page.wait_for_selector('#welcomeView:not([hidden])', timeout=15000)
      ok(page.inner_text('#welcomeStart') == 'Начать работу' and langs(page) == ('ru', 'en'), 'back to Russian: %s → %s' % langs(page))
      page.uncheck('#welcomeLoad')
      ok(wait(lambda: cfg().get('load_model_at_start') is False), '«Загружать выбранную модель при запуске» off: saved')
      page.check('#welcomeLoad')
      ok(wait(lambda: cfg().get('load_model_at_start') is True), '...and on again')
      page.click('#welcomeStart')
      ok(page.is_hidden('#welcomeView') and page.is_visible('#setupView') and page.evaluate("sessionStorage.getItem('tdoc.welcome')") == 'done', '«Начать работу»: the first-start screen')
      ok(wait(lambda: api('/api/state')['start_done'] is True), 'the start is over for other windows')

      # ================= the first-start screen: from, to, file
      st = api('/api/state')
      am = next(m for m in st['models'] if m['id'] == st['active_model'])
      items = page.inner_text('#dlItems')
      ok(items.count('Откуда:') == 2 and items.count('Куда:') == 2 and items.count('Файл:') == 2, 'first-start screen: from, to and file for the engine and the model')
      ok(ENGINE_URL in items and st['engine']['dir'] in items and ENGINE_URL.rsplit('/', 1)[1] in items, 'engine: address, folder, archive')
      ok(am['url'] in items and st['models_dir'] in items and am['file'] in items, 'model: address, folder, file')
      page.screenshot(path=os.path.join(shots, '3-setup.png'))
      page.click('#dlBtn')
      ready(page, 180000)

      # ================= the model menu: from, to, file before a download
      page.click('#modelBtn'); page.wait_for_selector('#modelMenu:not([hidden])')
      st = api('/api/state')
      q8 = next(m for m in st['models'] if m['id'] == 'q8')
      pick = page.locator('#modelMenu .mitem', has_text='Q8_0').locator('button.pick')
      pick.click(); page.wait_for_selector('#modelMenu .dl-confirm')
      conf = page.inner_text('#modelMenu .dl-confirm')
      ok(conf.startswith('Скачать «%s» (' % q8['name']) and ') и переключиться на неё?' in conf, 'the question: ' + conf.split('\n')[0])
      ok('Откуда:' in conf and q8['url'] in conf and 'Куда:' in conf and st['models_dir'] in conf and 'Файл:' in conf and q8['file'] in conf, 'from, to, file: ' + conf.replace('\n', ' | ')[:200])
      nothing = lambda: not os.path.exists(os.path.join(ROOT, 'models', q8['file'])) and not os.path.exists(os.path.join(ROOT, 'models', q8['file'] + '.part'))
      ok(nothing() and api('/api/state')['active_model'] == 'q4', 'nothing is downloaded before «Скачать»')
      page.screenshot(path=os.path.join(shots, '4-download-confirm.png'))
      page.click('#modelMenu .dl-confirm button:not(.primary)')
      ok(page.locator('#modelMenu .dl-confirm').count() == 0 and page.is_visible('#modelMenu') and nothing(), '«Отмена»: the question is gone, the menu stays open')
      pick.click(); page.wait_for_selector('#modelMenu .dl-confirm'); pick.click()
      ok(page.locator('#modelMenu .dl-confirm').count() == 0, 'a second click on the model hides the question')
      pick.click(); page.click('#modelMenu .dl-confirm button.primary')
      ok(page.is_hidden('#modelMenu'), '«Скачать» closes the menu')
      ok(wait(lambda: (lambda s: s['active_model'] == 'q8' and s['phase'] == 'ready')(api('/api/state')), 120), 'downloaded and switched: ' + api('/api/state')['active_model'])
      ready(page)

      # ================= «Свой вариант»
      ok(page.is_hidden('#ownCard'), 'no «Свой вариант» before a translation')
      SRC = 'Лазерный импульс сжат.'
      translate(page, SRC)
      n = page.locator('#cards .card').count()
      ok(n == 3 and page.is_visible('#ownCard') and page.input_value('#ownText') == '', '«Свой вариант» below the %d variants, empty' % n)
      ok(page.evaluate("document.querySelector('#cards').nextElementSibling.id") == 'ownCard' and page.get_attribute('#ownText', 'placeholder') == 'Напишите свой перевод — его можно сохранить в «Сохранённые»',
         'right after the variants, with a hint: ' + (page.get_attribute('#ownText', 'placeholder') or ''))
      page.click('#ownSave'); page.wait_for_timeout(300)
      ok(toast(page) == 'Сначала напишите свой вариант' and own_rows() == [], 'empty: asks to write first, nothing saved')
      page.evaluate("navigator.clipboard.writeText('before')"); page.click('#ownCopy'); page.wait_for_timeout(200)
      ok(toast(page) == 'Сначала напишите свой вариант' and page.evaluate('navigator.clipboard.readText()') == 'before', 'empty: nothing to copy')
      page.fill('#ownText', 'The laser pulse gets compressed.')
      page.click('#ownSave')
      ok(wait(lambda: [r[2:8] for r in own_rows()] == [['ru', 'en', 'Свой вариант', SRC, 'The laser pulse gets compressed.', '']]), 'saved to «Сохранённые»: %s' % own_rows())
      ok(wait(lambda: is_on(page, '#ownSave') and toast(page) == 'Сохранено в «Сохранённые»' and page.inner_text('#savedCount') == '(1)', 5), 'bookmark filled, toast «%s», counter %s' % (toast(page), page.inner_text('#savedCount')))
      page.click('#ownCopy'); page.wait_for_timeout(200)
      ok(toast(page) == 'Скопировано' and page.evaluate('navigator.clipboard.readText()') == 'The laser pulse gets compressed.', 'copied')
      page.fill('#ownText', 'The laser pulse is being compressed.')
      ok(not is_on(page, '#ownSave'), 'edited: the bookmark is no longer filled')
      page.click('#ownSave')
      ok(wait(lambda: [r[6] for r in own_rows()] == ['The laser pulse is being compressed.']), 'saving the edited text replaces the old entry: %s' % [r[6] for r in own_rows()])
      # a variant of the model as a basis
      page.click('#ownFromBtn'); page.wait_for_selector('#popMenu:not([hidden])')
      labels = texts(page, '#popMenu .mi > span:first-child')
      ok(labels == texts(page, '#cards .card .card-label') and page.inner_text('#popMenu .title') == 'Взять вариант за основу', 'variants to take: %s' % labels)
      second = page.locator('#cards .card .card-text').nth(1).inner_text()
      page.locator('#popMenu .mi').nth(1).click()
      ok(page.input_value('#ownText') == second and page.is_hidden('#popMenu') and not is_on(page, '#ownSave'), 'variant taken as a basis: ' + second)
      page.focus('#ownText'); page.keyboard.press('End'); page.keyboard.type(' Indeed.')
      page.click('#ownSave')
      ok(wait(lambda: [r[6] for r in own_rows()] == [second + ' Indeed.']), 'the edited variant replaces the entry: %s' % [r[6] for r in own_rows()])
      page.screenshot(path=os.path.join(shots, '5-own.png'))
      translate(page, SRC)
      ok(page.input_value('#ownText') == second + ' Indeed.' and is_on(page, '#ownSave'), 'the same text translated again: the own version and its bookmark stay')
      page.click('#savedBtn'); page.wait_for_selector('#savedList .item', timeout=5000)
      ok('Свой вариант' in page.inner_text('#savedList') and (second + ' Indeed.') in page.inner_text('#savedList'), 'the entry in «Сохранённые»')
      page.click('#closeSavedBtn')
      page.click('#ownSave')
      ok(wait(lambda: own_rows() == [] and not is_on(page, '#ownSave') and toast(page) == 'Убрано из сохранённых'), 'pressed again without changes: removed from saved')
      # another text starts with an empty field; editing (same language) has its own hint and no «Замечания» to take
      page.fill('#ownText', 'a draft')
      translate(page, 'Импульс лазера сжат.')
      ok(page.input_value('#ownText') == '' and not is_on(page, '#ownSave'), 'another text: the field is empty again')
      page.select_option('#tgtSel', 'ru'); page.wait_for_timeout(300)
      translate(page, 'Это тестовый текст для правки.')
      ok(page.get_attribute('#ownText', 'placeholder') == 'Напишите свой вариант текста — его можно сохранить в «Сохранённые»', 'editing: ' + (page.get_attribute('#ownText', 'placeholder') or ''))
      page.click('#ownFromBtn'); page.wait_for_selector('#popMenu:not([hidden])')
      ok(not any('Замечания' in x for x in texts(page, '#popMenu .mi > span:first-child')), 'no «Замечания» among variants to take: %s' % texts(page, '#popMenu .mi > span:first-child'))
      page.keyboard.press('Escape')
      ok(page.is_hidden('#popMenu'), 'Esc closes the list')
      page.select_option('#tgtSel', 'en')

      # ================= «Настройки»: at start
      page.click('#settingsBtn'); page.wait_for_selector('#settingsView:not([hidden])')
      ok(page.is_visible('#startRows') and pressed(page, '#modeSeg') == 'tab' and page.is_checked('#setLoad') and page.is_checked('#setWelcome'), 'settings: «При запуске» with the choices made in the welcome window')
      # two window types (0.9.2); «на весь экран» — only for the app window
      ok(texts(page, '#modeSeg button') == ['Окно приложения', 'Вкладка браузера'], 'settings: two window types: %s' % texts(page, '#modeSeg button'))
      ok(page.is_checked('#setMax') and page.is_disabled('#setMax'), '«Окно приложения — на весь экран»: on by default, not for a browser tab')
      page.click('#modeSeg button[data-v="window"]')
      ok(wait(lambda: cfg()['launch_mode'] == 'window' and pressed(page, '#modeSeg') == 'window' and page.is_enabled('#setMax')), 'window type: back to the app window, the check box is available')
      page.uncheck('#setMax')
      ok(wait(lambda: cfg().get('start_maximized') is False), '«на весь экран» off in config.json')
      page.check('#setMax')
      ok(wait(lambda: cfg().get('start_maximized') is True), '...and on again')
      page.uncheck('#setLoad')
      ok(wait(lambda: cfg()['load_model_at_start'] is False), '«Загружать выбранную модель» off')
      page.check('#setLoad')
      ok(wait(lambda: cfg()['load_model_at_start'] is True), '...and on again')
      page.screenshot(path=os.path.join(shots, '6-settings.png'))
      page.click('#openWelcomeBtn'); page.wait_for_selector('#welcomeView:not([hidden])')
      ok(page.is_checked('#welcomeLoad') and pressed(page, '#welcomeModeSeg') == 'window', 'the welcome window from the settings, same choices')
      page.uncheck('#welcomeLoad'); wait(lambda: cfg()['load_model_at_start'] is False)
      page.click('#welcomeStart'); page.wait_for_timeout(1500)
      ok(api('/api/state')['phase'] == 'ready' and engine_running(), 'opened from the settings, it does not unload the model')
      ok(not page.is_checked('#setLoad'), 'the settings show the change made in the welcome window')
      page.check('#setLoad')
      ok(wait(lambda: cfg()['load_model_at_start'] is True), 'on again in the settings')
      page.click('#closeSettingsBtn')

      # ================= when the welcome window opens: at the start of the program only
      page.reload(); ready(page); page.wait_for_timeout(600)
      ok(page.is_hidden('#welcomeView'), 'a reload: no welcome window (this window has seen it)')
      c2, p2 = window(); p2.goto(URL); ready(p2); p2.wait_for_timeout(800)
      ok(p2.is_hidden('#welcomeView'), 'a second window after the start: no welcome window')
      p2.click('#settingsBtn'); p2.wait_for_selector('#settingsView:not([hidden])')
      p2.click('#openWelcomeBtn'); p2.wait_for_selector('#welcomeView:not([hidden])')
      ok(p2.is_visible('#welcomeAbout'), '«О программе» in the welcome window over the work window')
      p2.uncheck('#welcomeLoad'); p2.uncheck('#welcomeShow')
      ok(wait(lambda: cfg()['load_model_at_start'] is False and cfg()['show_welcome'] is False), 'unticked in the second window: saved')
      p2.click('#welcomeAbout'); p2.wait_for_selector('#aboutView:not([hidden])')
      ok(p2.is_hidden('#welcomeView') and 'Версия ' + VERSION in p2.inner_text('#aboutBody'), '«О программе» closes the welcome window and opens About')
      p2.wait_for_timeout(1500)
      ok(api('/api/state')['phase'] == 'ready' and engine_running(), 'a second window does not unload the model: the start is over')
      c2.close()
      page.click('#settingsBtn'); page.wait_for_selector('#settingsView:not([hidden])')
      ok(wait(lambda: not page.is_checked('#setWelcome') and not page.is_checked('#setLoad'), 5), 'the settings show the choices made in the other window')
      page.check('#setWelcome')
      ok(wait(lambda: cfg()['show_welcome'] is True), '«Показывать окно приветствия» on again in the settings')

      # ================= restart: the model is not loaded at start
      ctx.close()
      ok(restart(), 'the program is started again')
      st = api('/api/state')
      ok(st['phase'] == 'unloaded' and st['no_model_at_start'] and not st['start_done'] and not engine_running(), 'not loaded at start: %s, no_model_at_start %s' % (st['phase'], st['no_model_at_start']))
      ctx, page = window(); page.goto(URL)
      page.wait_for_selector('#welcomeView:not([hidden])', timeout=15000)
      ok(not page.is_checked('#welcomeLoad') and page.is_checked('#welcomeShow'), 'the welcome window shows the last choice: do not load the model')
      ok(page.inner_text('#unloadedTitle') == 'Модель не загружена.' and page.inner_text('#unloadedText').startswith('При запуске модель не загружается'), 'banner: %s %s' % (page.inner_text('#unloadedTitle'), page.inner_text('#unloadedText')[:60]))
      ok(page.inner_text('#engineInfo') == 'модель не загружена', 'status line: ' + page.inner_text('#engineInfo'))
      page.screenshot(path=os.path.join(shots, '7-start-without-model.png'))
      page.check('#welcomeLoad')
      ok(wait(lambda: cfg()['load_model_at_start'] is True), 'ticked at start: saved')
      page.click('#welcomeStart'); ready(page)
      ok(api('/api/state')['start_done'] and engine_running(), '«Начать работу» loads the model now')

      # ================= restart: loaded at start, unticked in the welcome window
      ctx.close()
      ok(restart(), 'the program is started again')
      ok(wait(lambda: api('/api/state')['phase'] in ('starting', 'ready')), 'the model loads at start')
      ctx, page = window(); page.goto(URL)
      page.wait_for_selector('#welcomeView:not([hidden])', timeout=15000)
      ok(page.is_checked('#welcomeLoad'), 'the welcome window: load the model (the last choice)')
      page.uncheck('#welcomeLoad'); page.uncheck('#welcomeShow')
      wait(lambda: cfg()['load_model_at_start'] is False and cfg()['show_welcome'] is False)
      page.click('#welcomeStart')
      page.wait_for_selector('body[data-model="unloaded"]', timeout=15000)
      st = api('/api/state')
      ok(st['no_model_at_start'] and st['start_done'] and wait(lambda: not engine_running()), 'unticked at start: «Начать работу» unloads the model')
      ok(page.inner_text('#unloadedTitle') == 'Модель не загружена.', 'banner: ' + page.inner_text('#unloadedTitle'))
      page.click('#loadBtn'); ready(page)
      ok(not api('/api/state')['no_model_at_start'] and engine_running(), '«Загрузить»: loaded')

      # ================= restart: «Показывать это окно при запуске» off
      ctx.close()
      ok(restart(), 'the program is started again')
      ctx, page = window(); page.goto(URL)
      page.wait_for_selector('body[data-model="unloaded"]', timeout=15000); page.wait_for_timeout(800)
      ok(page.is_hidden('#welcomeView') and page.inner_text('#unloadedTitle') == 'Модель не загружена.', 'no welcome window at start; the model is not loaded (as chosen)')
      page.click('#settingsBtn'); page.wait_for_selector('#settingsView:not([hidden])')
      ok(not page.is_checked('#setWelcome') and not page.is_checked('#setLoad'), 'the settings show both choices off')
      page.check('#setWelcome'); page.check('#setLoad')
      ok(wait(lambda: cfg()['show_welcome'] is True and cfg()['load_model_at_start'] is True), 'both on again in the settings')
      page.click('#closeSettingsBtn'); page.click('#loadBtn'); ready(page)
      ok(not errors or all('net::' in e for e in errors), 'no console errors: %s' % errors[:3])
      page.click('#quitBtn'); page.click('#quitBtn')
      ok(wait(lambda: not alive(), 15), 'Exit closes the program')
      b.close()
except Exception as e:
    import traceback; traceback.print_exc()
    ok(False, 'exception: %s' % e)
finally:
    for pr in procs:
        try: pr.wait(timeout=10)
        except Exception: pr.kill()

fails = [l for l in log if l.startswith('FAIL')]
print('ALL OK %d checks' % len(log) if not fails else 'FAILS: %d of %d' % (len(fails), len(log)))
