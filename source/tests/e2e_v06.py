# End-to-end test of the v0.6 features: the interface language chosen on the first-start screen and in
# «Настройки» (English, German, back to Russian); the window, the launcher's messages and numbers in that
# language; the first files named in the chosen language; «Справка» and «О программе»; the theme and the font
# size; settings kept in config.json and given to a second window; Exit from the settings.
# Launcher + engine with a stand-in model + UI in Chromium; translations are canned replies (fixtures written
# for the test, not model output).
# Usage: e2e_v06.py <work> <ui_url> <root>   (a launcher in a fresh folder BEFORE the first run: the test chooses
# English on the first-start screen and downloads the files itself; it ends by closing the launcher)
import sys, json, os, re, time, urllib.request, urllib.error
from playwright.sync_api import sync_playwright
S, URL, ROOT = sys.argv[1], sys.argv[2], sys.argv[3]
BASE = URL.rstrip('/')
shots = os.path.join(S, 'shots', 'v06'); os.makedirs(shots, exist_ok=True)
log = []
def ok(cond, msg):
    log.append(('OK  ' if cond else 'FAIL') + ' ' + msg); print(log[-1], flush=True)
def cfg():
    return json.load(open(os.path.join(ROOT, 'config.json'), encoding='utf-8'))
def api(path):
    return json.load(urllib.request.urlopen(BASE + path, timeout=5))
def post_settings(body):
    req = urllib.request.Request(BASE + '/api/settings', data=json.dumps(body).encode(), method='POST',
                                 headers={'Content-Type': 'application/json', 'Origin': BASE})
    try:
        r = urllib.request.urlopen(req, timeout=5); return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
def files(sub):
    d = os.path.join(ROOT, 'data', sub)
    return sorted(os.listdir(d)) if os.path.isdir(d) else []
def ready(page, t=60000):
    page.wait_for_selector('body[data-model="ready"]', timeout=t)
def toast(page):
    return page.inner_text('#toast')
def texts(page, sel):
    return [x.strip() for x in page.locator(sel).all_inner_texts()]
def switch_lang(page, sel, lang):
    with page.expect_navigation(timeout=15000):
        page.select_option(sel, lang)

# Russian letters anywhere in the page — texts (also hidden ones and list options) and hints — except user
# content (the text, the context, variants, chat messages, glossary terms, saved texts, names of files) and the
# list of interface languages, where every language is named in itself.
SCAN = r'''() => {
  const cyr = /[А-Яа-яЁё]/;
  const user = '#src, #ctx, #customStyle, .card-text, .card-back, .card-diff, .msg-body, #glossTable tbody, #savedList .src, #savedList .tr, #uiLangSel, #setupLangSel, #welcomeLangSel, #glossFile, #savedFile, script, style';
  const bad = [];
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (w.nextNode()) {
    const n = w.currentNode, x = n.nodeValue.trim();
    if (x && cyr.test(x) && !n.parentElement.closest(user)) bad.push(x.slice(0, 70));
  }
  // hints of the glossary cells repeat the terms themselves
  for (const e of document.body.querySelectorAll('[title], [placeholder], [aria-label]')) {
    if (e.closest('#glossTable tbody input, .msg-body, .card-text, #savedList .src, #savedList .tr')) continue;
    for (const a of ['title', 'placeholder', 'aria-label']) { const v = e.getAttribute(a); if (v && cyr.test(v)) bad.push(a + ': ' + v.slice(0, 70)); }
  }
  return bad;
}'''

# different texts for the variants: equal variants would be merged into one card
REPLIES = ['Лазерный импульс сжат.', 'Лазерный импульс был сжат.', 'Импульс лазера сжат.']
served, chats = [], []
def reply(route):
    body = json.loads(route.request.post_data or '{}')
    if body.get('messages') and body['messages'][0].get('role') == 'system': chats.append(body)
    words = REPLIES[len(served) % len(REPLIES)].split(' '); served.append(1)
    out = ''.join('data: ' + json.dumps({'choices': [{'delta': {'content': (w if i == 0 else ' ' + w)}}]}) + '\n\n' for i, w in enumerate(words))
    out += 'data: ' + json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}], 'timings': {'predicted_n': 5, 'predicted_per_second': 9.5}}) + '\n\ndata: [DONE]\n\n'
    route.fulfill(status=200, headers={'Content-Type': 'text/event-stream'}, body=out)

def translate(page, text):
    page.fill('#src', text); page.wait_for_timeout(300)
    page.click('#goBtn'); page.wait_for_selector('#goBtn:not([hidden])', timeout=30000)
    page.wait_for_selector('.card:not(.pending)', timeout=10000)

try:
  with sync_playwright() as p:
      b = p.chromium.launch()
      ctx = b.new_context(viewport={'width': 1180, 'height': 780}, locale='ru-RU', color_scheme='light', accept_downloads=True)
      ctx.add_init_script("window.__closeCalls = 0; window.close = () => { window.__closeCalls++; };")
      # the start languages of a new window (0.6.1) are tested in e2e_v061.py; here the window is an "old" one
      ctx.add_init_script("try { sessionStorage.setItem('tdoc.window', '1'); sessionStorage.setItem('tdoc.welcome', 'done') } catch (e) {}")
      page = ctx.new_page()
      errors = []
      page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
      page.on('pageerror', lambda e: errors.append(str(e)))
      page.route('**/v1/chat/completions', reply)
      VERSION = api('/api/ping')['version']
      page.goto(URL)

      # ================= the first-start screen: choose English before downloading
      page.wait_for_selector('#setupView:not([hidden])', timeout=15000)
      ok(page.inner_text('#setupTitle') == 'Первый запуск' and page.input_value('#setupLangSel') == 'ru', 'first start in Russian, language list on the screen')
      ok(texts(page, '#setupLangSel option') == ['Русский', 'English', 'Deutsch'], 'interface languages named in themselves: %s' % texts(page, '#setupLangSel option'))
      ok(page.is_hidden('#settingsBtn') and page.is_hidden('#helpBtn'), 'no Settings and Help buttons before the work window')
      ok(files('saved') == [] and files('glossary') == [], 'no files are created before the work window: %s %s' % (files('saved'), files('glossary')))
      switch_lang(page, '#setupLangSel', 'en')
      page.wait_for_selector('#setupView:not([hidden])', timeout=15000)
      ok(page.evaluate('document.documentElement.lang') == 'en' and page.inner_text('#setupTitle') == 'First start' and page.inner_text('#dlBtn') == 'Download', 'first-start screen in English')
      ok(page.input_value('#setupLangSel') == 'en' and cfg().get('ui_language') == 'en', 'choice kept in config.json: %s' % cfg().get('ui_language'))
      ok(api('/api/state')['settings'] == {'ui_language': 'en', 'theme': 'light', 'font_scale': 100, 'show_welcome': True, 'launch_mode': 'app', 'load_model_at_start': True}, 'state reports the settings')
      page.click('#manualHelp summary')
      bad = page.evaluate(SCAN)
      ok(not bad, 'no Russian on the first-start screen: %s' % bad[:5])
      ok('MB' in page.inner_text('#dlItems') and 'Linux x64, CPU' in page.inner_text('#dlItems'), 'sizes and the launcher\'s platform label in English: %s' % page.inner_text('#dlItems').replace('\n', ' | ')[:160])
      page.screenshot(path=os.path.join(shots, '1-setup-en.png'))
      page.click('#dlBtn')
      ready(page, 180000); page.wait_for_timeout(800)
      ok(files('saved') == ['Saved.tsv'] and files('glossary') == ['My glossary.tsv'], 'first files named in English: %s %s' % (files('saved'), files('glossary')))

      # ================= the work window in English
      ok(page.inner_text('#goLabel') == 'Translate' and page.inner_text('#randomLabel') == 'Random' and page.inner_text('#quitLabel') == 'Exit', 'buttons: Translate, Random, Exit')
      ok(page.inner_text('#savedBtn').startswith('Saved') and page.inner_text('#testBtn').strip() == 'Test' and page.get_attribute('#settingsBtn', 'title') == 'Settings' and page.get_attribute('#helpBtn', 'title') == 'Help', 'header: Saved, Test, Help, Settings')
      ok(texts(page, '#srcSel option')[:4] == ['Auto', 'Russian', 'English', 'German'], 'language lists: %s' % texts(page, '#srcSel option')[:4])
      ok(texts(page, '#chips .chip')[0] == 'Neutral' and 'Custom' in texts(page, '#chips .chip') and page.inner_text('#counter') == '0 of 1000', 'styles and counter: %s, %s' % (texts(page, '#chips .chip'), page.inner_text('#counter')))
      st = api('/api/state')
      ok(st['engine']['platform_label'] == 'Linux x64, CPU' and 'release' in st['engine']['page'] and {m['group'] for m in st['models']} == {'Test models'}, 'launcher state in English: %s; %s' % (st['engine']['page'], {m['group'] for m in st['models']}))
      code, j = post_settings({'theme': 'blue'})
      ok(code == 400 and j.get('error') == 'invalid setting value', 'launcher errors in English: %s %s' % (code, j))
      page.click('#modelBtn'); page.wait_for_selector('#modelMenu:not([hidden])')
      ok('Test models' in page.inner_text('#modelMenu') and 'running now' in page.inner_text('#modelMenu'), 'model menu in English')
      bad = page.evaluate(SCAN)
      ok(not bad, 'no Russian in the work window and the model menu: %s' % bad[:6])
      page.keyboard.press('Escape')

      # translation: labels, numbers, the «?» question in English
      page.fill('#ctx', 'optics')
      translate(page, 'The laser pulse is compressed.')
      ok(page.locator('.card').count() == 3 and page.inner_text('.card .card-label') == 'Neutral · main', 'cards: %s' % texts(page, '.card .card-label'))
      tm = page.inner_text('#timing')
      ok(re.match(r'^3 variants in \d+\.\d s, the first after \d+\.\d s · 10 tok/s$', tm) is not None, 'summary with English numbers: ' + tm)
      ok(re.search(r'^\d+\.\d s · 10 tok/s$', page.inner_text('.card .card-meta')) is not None, 'card meta: ' + page.inner_text('.card .card-meta'))
      page.locator('.card').first.locator('button[data-act="ask"]').click()
      ok(texts(page, '#popMenu .mi > span:first-child')[:3] == ['Why like this?', 'Explain', 'How to say it more precisely?'], '«?» menu: %s' % texts(page, '#popMenu .mi > span:first-child'))
      page.locator('#popMenu .mi', has_text='Why like this?').click()
      page.wait_for_selector('#askLog .msg.bot:not(.pending)', timeout=30000)
      q = chats[-1]['messages'][-1]['content'] if chats else ''
      ok(q.startswith('Why is the text "The laser pulse is compressed." translated into Russian as "'), 'question to the model in English: ' + q[:110])
      page.select_option('#tgtSel', 'en'); page.wait_for_timeout(300)
      ok(page.inner_text('#goLabel') == 'Process' and texts(page, '#chips .chip')[0] == 'Corrected', 'editing mode: Process, Corrected')
      page.select_option('#tgtSel', 'auto')
      bad = page.evaluate(SCAN)
      ok(not bad, 'no Russian after translating and asking: %s' % bad[:6])

      # saved translations, TXT export in English
      page.locator('.card').first.locator('button[data-act="save"]').click(); page.wait_for_timeout(500)
      ok(toast(page) == 'Saved to “Saved”', 'save: ' + toast(page))
      page.click('#savedBtn'); page.wait_for_selector('#savedList .item', timeout=5000)
      ok(texts(page, '#savedFile option') == ['Saved'] and page.inner_text('#savedInfo') == '1 entry', 'saved panel: %s, %s' % (texts(page, '#savedFile option'), page.inner_text('#savedInfo')))
      page.evaluate('() => { window.showSaveFilePicker = undefined; }')
      with page.expect_download() as dl:
          page.click('#savedMenuBtn'); page.locator('#popMenu .mi', has_text='Export to text').click()
      txt_en = os.path.join(S, 'saved-en.txt'); dl.value.save_as(txt_en)
      t_en = open(txt_en, 'rb').read().decode('utf-8-sig')
      ok(t_en.startswith('Ttranslator · saved translations · “Saved” · ') and '\r\nNo. 1 · English → Russian · Neutral' in t_en and 'Context: optics' in t_en, 'TXT export in English: ' + t_en[:120].replace('\r\n', ' | '))
      bad = page.evaluate(SCAN)
      ok(not bad, 'no Russian in the saved panel: %s' % bad[:6])
      page.click('#closeSavedBtn')

      # glossary tab
      page.click('#tabGloss'); page.wait_for_timeout(400)
      ok(texts(page, '#glossFile option') == ['My glossary'] and 'Note' in page.inner_text('#glossTable thead') and 'English' in page.inner_text('#glossTable thead'), 'glossary: %s, header %s' % (texts(page, '#glossFile option'), page.inner_text('#glossTable thead').replace('\n', ' ')))
      bad = page.evaluate(SCAN)
      ok(not bad, 'no Russian in the glossary tab: %s' % bad[:6])
      page.click('#tabAsk')

      # test panel, help, About, settings
      page.click('#testBtn'); page.wait_for_timeout(300)
      ok(page.inner_text('#testIntro').startswith('Model: ') and 'Phrase pairs: ' in page.inner_text('#testIntro'), 'test panel: ' + page.inner_text('#testIntro')[:90])
      bad = page.evaluate(SCAN)
      ok(not bad, 'no Russian in the test panel: %s' % bad[:6])
      page.click('#helpBtn'); page.wait_for_selector('#helpView:not([hidden])')
      h3 = texts(page, '#helpBody h3')
      ok(len(h3) == 11 and h3[0] == 'Translation' and 'Reading aloud' in h3 and h3[-1] == 'If something does not work', 'help in English: %s' % h3)
      bad = page.evaluate(SCAN)
      ok(not bad, 'no Russian in the help: %s' % bad[:6])
      page.screenshot(path=os.path.join(shots, '2-help-en.png'))
      page.click('#helpAboutBtn'); page.wait_for_selector('#aboutView:not([hidden])')
      ab = page.inner_text('#aboutBody')
      ok('Version ' + VERSION in ab and ab.count('\n') > 5 and 'Licence: MIT' in ab and 'GitHub Sponsors' in ab, 'About in English: ' + ab[:100].replace('\n', ' | '))
      ok(page.get_attribute('#aboutBody a[href^="mailto:"]', 'href') == 'mailto:Ttranslator@proton.me' and page.locator('#aboutBody a[href*="github"]').count() == 0, 'contact link; no sponsor link yet')
      ok(page.locator('#aboutBody .about-head svg path').count() == 1, 'icon in About')
      bad = page.evaluate(SCAN)
      ok(not bad, 'no Russian in About: %s' % bad[:6])
      page.screenshot(path=os.path.join(shots, '3-about-en.png'))
      page.click('#settingsBtn'); page.wait_for_selector('#settingsView:not([hidden])')
      ok(page.input_value('#uiLangSel') == 'en' and texts(page, '#themeSeg button') == ['Light', 'Dark'] and texts(page, '#fontSeg button') == ['Small', 'Normal', 'Large', 'Very large'], 'settings in English')
      ok('config.json' in page.inner_text('#settingsNote') and page.is_visible('#quit2Btn') and page.inner_text('#quit2Btn') == 'Exit the program', 'settings: note and Exit')
      bad = page.evaluate(SCAN)
      ok(not bad, 'no Russian in the settings: %s' % bad[:6])
      page.screenshot(path=os.path.join(shots, '4-settings-en.png'))

      # a second window gets the same language from config.json (nothing in its browser memory)
      ctx2 = b.new_context(viewport={'width': 1000, 'height': 700})
      p2 = ctx2.new_page(); p2.goto(URL)
      ok(p2.evaluate('document.documentElement.lang') == 'en', 'second window: English from the first byte of the page')
      ready(p2); ok(p2.inner_text('#goLabel') == 'Translate', 'second window in English')
      ctx2.close()

      # ================= German: the text in the field and the open panel survive the switch
      page.fill('#src', 'Der Laser ist stark.'); page.fill('#ctx', 'Optik'); page.wait_for_timeout(300)
      switch_lang(page, '#uiLangSel', 'de'); ready(page); page.wait_for_timeout(500)
      ok(page.evaluate('document.documentElement.lang') == 'de' and cfg().get('ui_language') == 'de', 'German chosen and kept in config.json')
      ok(page.input_value('#src') == 'Der Laser ist stark.' and page.input_value('#ctx') == 'Optik' and page.is_visible('#settingsView'), 'text, context and the settings panel survive the reload')
      ok(page.inner_text('#counter') == '20 von 1000' and page.inner_text('#goLabel') == 'Übersetzen', 'German: counter and Übersetzen')
      code, j = post_settings({'font_scale': 3})
      ok(code == 400 and j.get('error') == 'ungültiger Wert der Einstellung', 'launcher errors in German: %s' % j)
      bad = page.evaluate(SCAN)
      ok(not bad, 'no Russian in the German window: %s' % bad[:6])
      translate(page, 'Der Laser ist stark.')
      tm = page.inner_text('#timing')
      ok(re.match(r'^3 Varianten in \d+,\d s, die erste nach \d+,\d s · 10 Tok\./s$', tm) is not None, 'summary with German numbers: ' + tm)
      ok(page.inner_text('.card .card-label') == 'Neutral · Hauptvariante', 'card label: ' + page.inner_text('.card .card-label'))
      page.click('#savedBtn'); page.wait_for_selector('#savedList .item', timeout=5000)
      ok(texts(page, '#savedFile option') == ['Saved'], 'the user\'s file keeps its name')
      page.set_input_files('#savedImportFile', txt_en); page.wait_for_timeout(800)
      ok(toast(page) == 'Aus der Datei „saved-en.txt“: 0 hinzugefügt, übersprungene Duplikate: 1', 'English TXT export read back in German: ' + toast(page))
      page.click('#helpBtn'); page.wait_for_selector('#helpView:not([hidden])')
      ok(texts(page, '#helpBody h3')[0] == 'Übersetzung', 'help in German')
      page.click('#helpAboutBtn'); page.wait_for_selector('#aboutView:not([hidden])')
      ok('Version ' + VERSION in page.inner_text('#aboutBody') and 'Lizenz: MIT' in page.inner_text('#aboutBody'), 'About in German')
      bad = page.evaluate(SCAN)
      ok(not bad, 'no Russian in German help and About: %s' % bad[:6])
      page.screenshot(path=os.path.join(shots, '5-about-de.png'))

      # ================= back to Russian; theme and font size
      page.click('#settingsBtn'); page.wait_for_selector('#settingsView:not([hidden])')
      switch_lang(page, '#uiLangSel', 'ru'); ready(page); page.wait_for_timeout(500)
      ok(page.evaluate('document.documentElement.lang') == 'ru' and page.inner_text('#goLabel') == 'Перевести' and page.is_visible('#settingsView'), 'back to Russian')
      ok(texts(page, '#themeSeg button') == ['Светлая', 'Тёмная'] and 'config.json' in page.inner_text('#settingsNote'), 'settings in Russian')
      light_bg = page.evaluate('getComputedStyle(document.body).backgroundColor')
      page.click('#themeSeg button[data-v="dark"]'); page.wait_for_timeout(400)
      dark_bg = page.evaluate('getComputedStyle(document.body).backgroundColor')
      ok(page.evaluate('document.documentElement.dataset.theme') == 'dark' and light_bg == 'rgb(245, 244, 239)' and dark_bg == 'rgb(28, 27, 26)', 'dark theme: %s → %s' % (light_bg, dark_bg))
      ok(page.get_attribute('#themeSeg button[data-v="dark"]', 'aria-pressed') == 'true' and cfg().get('theme') == 'dark', 'dark theme kept in config.json')
      page.click('#fontSeg button[data-v="130"]'); page.wait_for_timeout(400)
      fs = page.evaluate('getComputedStyle(document.documentElement).fontSize')
      src_fs = page.evaluate("getComputedStyle(document.querySelector('#src')).fontSize")
      ok(fs == '18.2px' and float(src_fs[:-2]) > 18 and cfg().get('font_scale') == 130, 'very large font: html %s, text field %s' % (fs, src_fs))
      page.screenshot(path=os.path.join(shots, '6-dark-large.png'))
      page.reload(); ready(page)
      ok(page.evaluate('[document.documentElement.dataset.theme, document.documentElement.dataset.font]') == ['dark', '130'], 'theme and font survive a reload')
      ctx3 = b.new_context(viewport={'width': 1000, 'height': 700})
      p3 = ctx3.new_page(); p3.goto(URL)
      ok(p3.evaluate('[document.documentElement.lang, document.documentElement.dataset.theme, document.documentElement.dataset.font]') == ['ru', 'dark', '130'], 'a new window gets the theme and font at once')
      ctx3.close()
      page.click('#helpBtn'); page.wait_for_selector('#helpView:not([hidden])')
      h3 = texts(page, '#helpBody h3')
      ok(len(h3) == 11 and h3[0] == 'Перевод' and 'Ctrl+Enter' in page.inner_text('#helpBody'), 'help in Russian')
      page.screenshot(path=os.path.join(shots, '7-help-dark.png'))
      page.click('#helpAboutBtn'); page.wait_for_selector('#aboutView:not([hidden])')
      ab = page.inner_text('#aboutBody')
      ok('Версия ' + VERSION in ab and 'Ttranslator@proton.me' in ab and 'Лицензия: MIT' in ab and 'llama.cpp' in ab and 'GitHub Sponsors' in ab, 'About in Russian')
      page.screenshot(path=os.path.join(shots, '8-about-dark.png'))
      page.click('#settingsBtn'); page.wait_for_selector('#settingsView:not([hidden])')
      page.click('#fontSeg button[data-v="100"]'); page.click('#themeSeg button[data-v="light"]'); page.wait_for_timeout(400)
      ok(page.evaluate('getComputedStyle(document.documentElement).fontSize') == '14px' and cfg().get('theme') == 'light' and cfg().get('font_scale') == 100, 'back to light theme and normal font')
      ok(not errors, 'no console errors: %s' % errors[:3])

      # ================= Exit from the settings
      page.click('#quit2Btn')
      ok(page.inner_text('#quit2Btn') == 'Нажмите ещё раз, чтобы выйти' and 'confirm' in page.get_attribute('#quit2Btn', 'class'), 'first press asks to confirm')
      page.keyboard.press('Escape')
      ok(page.inner_text('#quit2Btn') == 'Выйти из программы', 'Esc cancels')
      page.click('#quit2Btn'); page.click('#quit2Btn')
      page.wait_for_selector('#byeView:not([hidden])', timeout=5000)
      ok(page.is_hidden('#mainView') and page.evaluate('window.__closeCalls') >= 1, 'bye screen; the page asked to close the window')
      gone = False
      for i in range(40):
          try:
              urllib.request.urlopen(BASE + '/api/ping', timeout=1)
          except Exception:
              gone = True; break
          time.sleep(0.25)
      ok(gone, 'launcher exited')
      b.close()
except Exception as e:
    import traceback; traceback.print_exc()
    ok(False, 'exception: %s' % e)

fails = [l for l in log if l.startswith('FAIL')]
print('ALL OK %d checks' % len(log) if not fails else 'FAILS: %d of %d' % (len(fails), len(log)))
