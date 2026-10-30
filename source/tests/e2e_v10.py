# End-to-end test of the 1.0 features: a really new installation (no config.json) starts in English, with English
# first in the list of interface languages; the Spanish and Chinese interface (the first-start screen, the first
# files, the glossary header, help, About, settings, the test panel, the launcher's messages and the model notes,
# the Chinese fonts); «Авто» on the right by the interface language and the start languages of a new window; the
# Latin voice (the Italian Paola) in the voice menu, with the church and the classical pronunciation sharing one
# download; phrase pairs of ui/tests.txt in any two languages — the Latin sayings — and the test report grouped by
# direction; the quick test (Latin ↔ the interface language) and the labels of the test rows; the settings of
# «Спросить модель» (temperature, answers) and the speed of reading aloud; About with the links and the thanks.
# Launcher + engine with a stand-in model + UI in Chromium; translations are canned replies.
# Usage: e2e_v10.py <work> <ui_url> <root>   (a launcher in a fresh folder WITHOUT config.json — run_all.sh: FRESH=1;
# the test downloads the stand-in files itself and ends by closing the launcher)
import sys, json, os, urllib.request, urllib.error
from playwright.sync_api import sync_playwright
S, URL, ROOT = sys.argv[1], sys.argv[2], sys.argv[3]
BASE = URL.rstrip('/')
shots = os.path.join(S, 'shots', 'v10'); os.makedirs(shots, exist_ok=True)
log = []
def ok(cond, msg):
    log.append(('OK  ' if cond else 'FAIL') + ' ' + msg); print(log[-1], flush=True)
def cfg():
    return json.load(open(os.path.join(ROOT, 'config.json'), encoding='utf-8'))
def api(path):
    return json.load(urllib.request.urlopen(BASE + path, timeout=5))
def post(path, body):
    req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(), method='POST',
                                 headers={'Content-Type': 'application/json', 'Origin': BASE})
    try:
        r = urllib.request.urlopen(req, timeout=5); return r.status, json.load(r)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
def files(sub):
    d = os.path.join(ROOT, 'data', sub)
    return sorted(os.listdir(d)) if os.path.isdir(d) else []
def texts(page, sel):
    return [x.strip() for x in page.locator(sel).all_inner_texts()]
def switch_lang(page, sel, lang):
    with page.expect_navigation(timeout=15000):
        page.select_option(sel, lang)
def ready(page, t=180000):
    page.wait_for_selector('body[data-model="ready"]', timeout=t)

# Russian letters in the page outside user content and the list of interface languages (as in e2e_v06.py)
SCAN = r'''() => {
  const cyr = /[А-Яа-яЁё]/;
  const user = '#src, #ctx, #customStyle, .card-text, .card-back, .card-diff, .msg-body, #glossTable tbody, #savedList .src, #savedList .tr, #uiLangSel, #setupLangSel, #welcomeLangSel, #glossFile, #savedFile, #testRows, script, style';
  const bad = [];
  const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  while (w.nextNode()) {
    const n = w.currentNode, x = n.nodeValue.trim();
    if (x && cyr.test(x) && !n.parentElement.closest(user)) bad.push(x.slice(0, 70));
  }
  for (const e of document.body.querySelectorAll('[title], [placeholder], [aria-label]')) {
    if (e.closest('#glossTable tbody input, .msg-body, .card-text, #savedList .src, #savedList .tr, #testRows')) continue;
    for (const a of ['title', 'placeholder', 'aria-label']) { const v = e.getAttribute(a); if (v && cyr.test(v)) bad.push(a + ': ' + v.slice(0, 70)); }
  }
  return bad;
}'''

served = []
reqs = []
def reply(route):
    served.append(1)
    try: reqs.append(json.loads(route.request.post_data))
    except Exception: reqs.append({})
    out = 'data: ' + json.dumps({'choices': [{'delta': {'content': 'Fortuna audaces adiuvat.'}}]}) + '\n\n'
    out += 'data: ' + json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}], 'timings': {'predicted_n': 5, 'predicted_per_second': 9.5}}) + '\n\ndata: [DONE]\n\n'
    route.fulfill(status=200, headers={'Content-Type': 'text/event-stream'}, body=out)

try:
  with sync_playwright() as p:
      b = p.chromium.launch()
      ctx = b.new_context(viewport={'width': 1180, 'height': 780}, color_scheme='light')
      ctx.add_init_script("try { sessionStorage.setItem('tdoc.welcome', 'done') } catch (e) {}")   # the welcome window: e2e_v07.py
      page = ctx.new_page()
      errors = []
      page.on('pageerror', lambda e: errors.append(str(e)))
      page.route('**/v1/chat/completions', reply)

      # ================= a new installation: English
      ok(not os.path.exists(os.path.join(ROOT, 'config.json')) or cfg().get('ui_language') == 'en', 'no config.json before the first start (or a new one in English)')
      page.goto(URL)
      page.wait_for_selector('#setupView:not([hidden])', timeout=15000)
      ok(page.evaluate('document.documentElement.lang') == 'en' and page.inner_text('#setupTitle') == 'First start' and page.inner_text('#dlBtn') == 'Download',
         'the first start is in English: %s / %s' % (page.inner_text('#setupTitle'), page.inner_text('#dlBtn')))
      ok(texts(page, '#setupLangSel option') == ['English', 'Русский', 'Deutsch', 'Español', '中文'], 'interface languages, English first: %s' % texts(page, '#setupLangSel option'))
      ok(cfg().get('ui_language') == 'en', 'config.json of the new installation: English (%s)' % cfg().get('ui_language'))
      ok(api('/api/state')['settings']['ui_language'] == 'en', 'state: English')
      page.screenshot(path=os.path.join(shots, '1-setup-en.png'))

      # ================= Spanish on the first-start screen; the first files named in Spanish
      switch_lang(page, '#setupLangSel', 'es')
      page.wait_for_selector('#setupView:not([hidden])', timeout=15000)
      ok(page.inner_text('#setupTitle') == 'Primer inicio' and page.inner_text('#dlBtn') == 'Descargar' and cfg().get('ui_language') == 'es',
         'first-start screen in Spanish: %s / %s' % (page.inner_text('#setupTitle'), page.inner_text('#dlBtn')))
      page.click('#manualHelp summary')
      bad = page.evaluate(SCAN)
      ok(not bad, 'no Russian on the Spanish first-start screen: %s' % bad[:5])
      ok('Linux x64, CPU' in page.inner_text('#dlItems'), 'the launcher\'s platform label in Spanish: %s' % page.inner_text('#dlItems').replace('\n', ' | ')[:160])
      page.screenshot(path=os.path.join(shots, '2-setup-es.png'))
      page.click('#dlBtn')
      ready(page); page.wait_for_timeout(800)
      ok(files('saved') == ['Guardados.tsv'] and files('glossary') == ['Mi glosario.tsv'], 'first files named in Spanish: %s %s' % (files('saved'), files('glossary')))
      head = open(os.path.join(ROOT, 'data', 'glossary', 'Mi glosario.tsv'), encoding='utf-8-sig').read().splitlines()
      ok(head[0].split('\t') == ['Inglés', 'Ruso', 'Alemán', 'Español', 'Nota'] and any('década' in l for l in head),
         'the first glossary: English, Russian, German and the interface language Spanish, the note column: %s' % head[0])
      ok(page.evaluate("['Inglés', 'Español', 'Latín', '英语', '西班牙语', '拉丁语', 'Nota'].map(h => headerLang(h) || (isNoteHeader(h) ? 'note' : null))") == ['en', 'es', 'la', 'en', 'es', 'la', 'note'],
         'glossary headers in Spanish and Chinese are understood')

      # ================= the Spanish window: start languages, «Авто», no Russian
      ok(page.input_value('#srcSel') == 'es' and page.input_value('#tgtSel') == 'en', 'a new window: Spanish → English (%s → %s)' % (page.input_value('#srcSel'), page.input_value('#tgtSel')))
      ok(page.evaluate("[AUTO_TARGET('es'), AUTO_TARGET('de'), AUTO_TARGET('ru')]") == ['en', 'es', 'es'], '«Авто» on the right: Spanish → English, other → Spanish')
      ok(page.get_attribute('#tgtSel option[value="auto"]', 'title') == 'Texto en español, al inglés; texto en otro idioma, al español', 'the hint of «Авто» in Spanish')
      ok(page.inner_text('#goLabel') == 'Traducir', 'the Translate button in Spanish')
      # the example of «Свой» style in the interface language; an example inserted in another language (remembered in
      # the browser) follows the interface language, a style written by hand stays (author's remark of 30.10.2026)
      ok(page.get_attribute('#customStyle', 'placeholder') == 'p. ej.: literario' and page.get_attribute('#ctx', 'placeholder') == 'p. ej.: un artículo de divulgación científica',
         'the examples of «Свой» style and context in Spanish: %s / %s' % (page.get_attribute('#customStyle', 'placeholder'), page.get_attribute('#ctx', 'placeholder')))
      page.evaluate("localStorage.setItem('tdoc.customStyle', JSON.stringify('художественно-литературный'))")
      page.reload(); ready(page, 30000); page.wait_for_timeout(500)
      ok(page.input_value('#customStyle') == 'literario' and page.evaluate("JSON.parse(localStorage.getItem('tdoc.customStyle'))") == 'literario',
         'the Russian example of «Свой» style becomes the Spanish one: %s' % page.input_value('#customStyle'))
      page.evaluate("localStorage.setItem('tdoc.customStyle', JSON.stringify('como en un cuento'))")
      page.reload(); ready(page, 30000); page.wait_for_timeout(500)
      ok(page.input_value('#customStyle') == 'como en un cuento', 'a style written by hand stays as it is')
      page.evaluate("localStorage.removeItem('tdoc.customStyle')")
      page.reload(); ready(page, 30000); page.wait_for_timeout(500)
      bad = page.evaluate(SCAN)
      ok(not bad, 'no Russian in the Spanish window: %s' % bad[:5])
      page.screenshot(path=os.path.join(shots, '3-main-es.png'))
      page.click('#helpBtn'); page.wait_for_selector('#helpView:not([hidden])')
      hb = page.inner_text('#helpBody')
      ok(page.locator('#helpBody h3').count() == 12 and page.locator('#helpBody h3').first.inner_text() == 'Traducción' and 'la eclesiástica (italiana)' in hb and 'o la clásica' in hb,
         'help in Spanish (with both pronunciations of Latin)')
      ok(texts(page, '#helpBody h3')[-2] == 'Actualizar y desinstalar' and 'Desinstalar en Windows' in hb and '~/.cache/ttranslator' in hb and 'Prueba rápida' in hb,
         'help: updating and uninstalling, the quick test: %s' % texts(page, '#helpBody h3')[-3:])
      ok(hb.count('Hay voces para') == 1 and 'Si hay dos voces descargadas para un idioma' in hb, 'help: one line about the voices, the line about two voices')
      page.click('#aboutBtn'); page.wait_for_selector('#aboutView:not([hidden])')
      ab = page.inner_text('#aboutBody')
      ok('Le presentamos Ttranslator, un traductor multifuncional' in ab and 'Versión 1.0' in ab, 'About in Spanish, version 1.0, «multifuncional»')
      ok(page.locator('#aboutBody a[href="https://github.com/Allasoneteam"]').count() == 1 and page.locator('#aboutBody a[href="https://github.com/sponsors/Allasoneteam"]').count() == 1
         and 'GitHub Sponsors: github.com/Allasoneteam y github.com/sponsors/Allasoneteam' in ab, 'About: the links to GitHub and GitHub Sponsors')
      ok('Agradecimiento especial a Ivan Gonoskov y Claude Opus 5.5 (Anthropic).' in ab, 'About: the thanks')
      page.click('#settingsBtn'); page.wait_for_selector('#settingsView:not([hidden])')
      ok('config.json' in page.inner_text('#settingsNote') and page.inner_text('#settingsNote').startswith('Los ajustes'), 'settings in Spanish')

      # ================= «Спросить модель» and reading aloud in the settings: saved in config.json, used by the requests
      sv = page.inner_text('#settingsView')
      ok('Temperatura' in sv and 'Respuestas' in sv and 'Breves' in sv and 'Velocidad' in sv and 'Para todas las voces.' in sv, 'the new settings in Spanish')
      ok(texts(page, '#setTemp option')[:3] == ['0,1', '0,2', '0,3'] and len(texts(page, '#setTemp option')) == 10 and page.input_value('#setTemp') == '0.6'
         and page.get_attribute('#ansSeg button[data-v="normal"]', 'aria-pressed') == 'true' and page.get_attribute('#speedSeg button[data-v="100"]', 'aria-pressed') == 'true',
         'the defaults: temperature 0.6, normal answers, speed 100 %')
      page.select_option('#setTemp', '0.3'); page.wait_for_timeout(300)
      page.click('#ansSeg button[data-v="short"]'); page.wait_for_timeout(300)
      page.click('#speedSeg button[data-v="80"]'); page.wait_for_timeout(400)
      c = cfg()
      ok(c.get('chat_temperature') == 0.3 and c.get('chat_answers') == 'short' and c.get('speech_speed') == 80, 'config.json: %s' % {k: c.get(k) for k in ('chat_temperature', 'chat_answers', 'speech_speed')})
      ok(page.get_attribute('#ansSeg button[data-v="short"]', 'aria-pressed') == 'true' and page.evaluate('speechSpeed()') == 0.8, 'the choice is shown; reading aloud at 80 %%: %s' % page.evaluate('speechSpeed()'))
      page.click('#closeSettingsBtn')
      n = len(reqs)
      page.fill('#askInput', '¿Qué significa «audentes»?'); page.click('#askSend')
      page.wait_for_function("document.querySelectorAll('#askLog .msg.bot').length > 0 && !document.querySelector('#askLog .msg.bot.pending')", timeout=20000)
      r = reqs[n] if len(reqs) > n else {}
      sysmsg = (r.get('messages') or [{}])[0].get('content', '')
      ok(r.get('temperature') == 0.3 and sysmsg.endswith('Answer briefly: a few sentences at most, unless the user asks for more.') and 0 < r.get('max_tokens', 0) <= 512,
         'a chat question with the settings: t=%s, max_tokens=%s, system …%s' % (r.get('temperature'), r.get('max_tokens'), sysmsg[-60:]))
      post('/api/settings', {'chat_temperature': 0.6, 'chat_answers': 'normal', 'speech_speed': 100})

      # ================= the test: pairs in any two languages (the Latin sayings), the report grouped by direction
      page.click('#testBtn'); page.wait_for_timeout(400)
      intro = page.inner_text('#testIntro')
      ok('Pares de frases: 6' in intro and 'Idiomas: inglés ↔ ruso — 2, latín ↔ inglés — 4.' in intro, 'the test panel: six pairs, the languages: %s' % intro.replace('\n', ' | ')[:300])
      ok(intro.startswith('Modelo: ') and 'Prueba rápida. Dos locuciones latinas (Audentes fortuna iuvat; Cogito, ergo sum): latín ↔ español' in intro and '4 traducciones' in intro
         and 'Prueba completa. Pares de frases: 6' in intro, 'the test panel: the model, the quick test, the full test: %s' % intro.replace('\n', ' | ')[:300])
      ok(texts(page, '#testView .pane-head button') == ['Prueba rápida', 'Prueba completa', 'Atrás'], 'the buttons: %s' % texts(page, '#testView .pane-head button'))
      page.click('#runTestBtn')
      page.wait_for_function("document.querySelector('#testProgressText').textContent.startsWith('Hecho') || document.querySelector('#testProgressText').textContent.startsWith('Error')", timeout=120000)
      ok(page.inner_text('#testProgressText').startswith('Hecho: 38 tareas'), 'the test: 6 pairs × 6 + 2 with formulas = 38 tasks: %s' % page.inner_text('#testProgressText'))
      row0 = page.locator('#testRows .test-out').first.inner_text()
      ok('Texto original: ' in row0 and 'Traducción del modelo: Fortuna audaces adiuvat.' in row0 and 'Su versión: ' in row0, 'a row of the full test: the source text, the model translation, your version: %s' % row0.replace('\n', ' | '))
      ed = page.locator('#testRows .test-out', has_text='corrección').first.inner_text()
      ok('Texto original: ' in ed and 'Corregido: ' in ed, 'a row of the correction: the source text and the corrected one: %s' % ed.replace('\n', ' | ')[:160])
      page.wait_for_function("document.querySelector('#testSummary').textContent.includes('Informe guardado')", timeout=15000)
      rows = texts(page, '#testSummary table tbody tr td:first-child')
      ok(rows[:8] == ['Inglés → Ruso'] * 2 + ['Ruso → Inglés'] * 2 + ['Latín → Inglés'] * 2 + ['Inglés → Latín'] * 2 and 'Corrección (latín)' in rows,
         'the summary: every direction in both styles, editing per language: %s' % rows)
      rep = sorted(f for f in os.listdir(os.path.join(ROOT, 'data', 'reports')) if f.endswith('.json'))
      rj = json.load(open(os.path.join(ROOT, 'data', 'reports', rep[-1]), encoding='utf-8'))
      la = [r for r in rj['results'] if r['kind'] == 'translate' and r['from'] == 'la']
      ok(len(la) == 8 and la[0]['source'] == 'Audentes fortuna iuvat.' and la[0]['ref'] == 'Fortune favors the bold.' and {r['to'] for r in la} == {'en'},
         'report: Latin → English with the reference translations: %s' % [(r['source'], r['ref']) for r in la[:2]])
      eds = sorted({r['from'] for r in rj['results'] if r['kind'] == 'edit'})
      ok(eds == ['en', 'la', 'ru'], 'report: each phrase corrected in its own language: %s' % eds)
      md = open(os.path.join(ROOT, 'data', 'reports', rep[-1][:-5] + '.md'), encoding='utf-8').read()
      ok('### Par 3: Latín → Inglés, Neutro' in md and '### Par 6: Inglés → Latín, Coloquial' in md, 'the Markdown report in Spanish, with the Latin pairs')
      got = page.evaluate("parseTests('EN: one\\nRU: два\\n\\n# c\\nLA: tres\\nEN: three\\nDE: vier\\nDE: fünf\\nEN: five\\nXX: q\\nFR: seul').map(p => p.langs.join('-') + ':' + p.text[p.langs[1]])")
      ok(got == ['en-ru:два', 'la-en:three', 'de-en:five'], 'tests.txt: any two languages, a repeated language starts a new pair, unknown codes and a lone line skipped: %s' % got)

      # ================= the quick test: Latin ↔ the interface language (Spanish), the reference translations built in
      page.click('#quickTestBtn')
      page.wait_for_function("document.querySelector('#testProgressText').textContent.startsWith('Hecho') || document.querySelector('#testProgressText').textContent.startsWith('Error')", timeout=60000)
      ok(page.inner_text('#testProgressText').startswith('Hecho: 4 tareas'), 'the quick test: 2 sayings × 2 directions = 4 tasks: %s' % page.inner_text('#testProgressText'))
      qrows = page.locator('#testRows .test-out')
      r0, r1 = qrows.nth(0).inner_text(), qrows.nth(1).inner_text()
      ok(qrows.count() == 4 and 'Frase 1 · Latín → Español · Neutro' in r0 and 'Texto original: Audentes fortuna iuvat.' in r0 and 'Traducción del modelo: ' in r0
         and 'Traducción de referencia: La fortuna favorece a los audaces.' in r0, 'a row of the quick test: %s' % r0.replace('\n', ' | '))
      ok('Español → Latín' in r1 and 'Texto original: La fortuna favorece a los audaces.' in r1 and 'Traducción de referencia: Audentes fortuna iuvat.' in r1, 'the way back: %s' % r1.replace('\n', ' | '))
      ok(page.inner_text('#quickTestBtn') == 'Prueba rápida' and not page.is_disabled('#runTestBtn'), 'the buttons after the quick test')
      page.wait_for_function("document.querySelector('#testSummary').textContent.includes('Informe guardado')", timeout=15000)
      ok(texts(page, '#testSummary table tbody tr td:first-child') == ['Latín → Español', 'Español → Latín'], 'the summary of the quick test: %s' % texts(page, '#testSummary table tbody tr td:first-child'))
      qrep = sorted(f for f in os.listdir(os.path.join(ROOT, 'data', 'reports')) if f.startswith('quick-test-') and f.endswith('.md'))
      qmd = open(os.path.join(ROOT, 'data', 'reports', qrep[-1]), encoding='utf-8').read() if qrep else ''
      qj = json.load(open(os.path.join(ROOT, 'data', 'reports', qrep[-1][:-3] + '.json'), encoding='utf-8')) if qrep else {}
      ok(qmd.startswith('# Prueba del traductor: Prueba rápida') and '### Frase 2: Latín → Español, Neutro' in qmd and '- Traducción de referencia: Pienso, luego existo.' in qmd and '~~' not in qmd,
         'the report of the quick test (%s): no correction section' % (qrep[-1] if qrep else 'none'))
      ok(len(qj.get('results', [])) == 4 and all(r['kind'] == 'translate' and r.get('builtin') for r in qj.get('results', [])), 'the JSON report of the quick test: 4 translations')
      page.click('#closeTestBtn')

      # ================= the Latin voice in the voice menu (Spanish), the model notes of the launcher in Spanish
      page.click('#modelBtn'); page.wait_for_selector('#modelMenu:not([hidden])')
      menu = page.inner_text('#modelMenu')
      ok('Latín · Paola (voz italiana, pronunciación eclesiástica)' in menu and 'Latín · Paola (voz italiana, pronunciación clásica)' in menu, 'the Latin voice: the Italian Paola, church and classical pronunciation')
      ok(menu.count('un solo archivo para ambas pronunciaciones') == 2, 'both Latin entries say they share one file')
      ok('Modelos de prueba' in menu, 'a group name of the launcher\'s catalogue in Spanish')
      vs = {x['id']: x for x in api('/api/state')['tts']['voices'] if x['lang'] == 'la'}
      v, vc = vs.get('la-paola', {}), vs.get('la-paola-classical', {})
      ok(sorted(vs) == ['la-paola', 'la-paola-classical'] and v.get('via') == vc.get('via') == 'it' and v.get('license') == 'CC0' and v.get('file') == vc.get('file') == 'vits-piper-it_IT-paola-medium.tar.bz2'
         and v.get('respell') == 'la-church' and vc.get('respell') == 'la-classical', 'the Latin voices in /api/state: %s' % vs)
      page.keyboard.press('Escape')
      code, j = post('/api/voice', {'id': 'nope'})
      ok(code == 400 and j.get('error') == 'voz desconocida', 'a message of the launcher in Spanish: %s' % j)

      # ================= Chinese
      post('/api/settings', {'ui_language': 'zh'})
      page.close(); page = ctx.new_page(); page.route('**/v1/chat/completions', reply)
      page.goto(URL); ready(page, 30000); page.wait_for_timeout(600)
      ok(page.evaluate('document.documentElement.lang') == 'zh' and page.inner_text('#goLabel') == '翻译', 'the Chinese window')
      ok(page.input_value('#srcSel') == 'zh' and page.input_value('#tgtSel') == 'en', 'a new window: Chinese → English')
      ok(page.evaluate("[AUTO_TARGET('zh'), AUTO_TARGET('ru')]") == ['en', 'zh'], '«Авто» on the right with the Chinese interface')
      ok('Microsoft YaHei' in page.evaluate("getComputedStyle(document.body).fontFamily"), 'fonts for Simplified Chinese')
      bad = page.evaluate(SCAN)
      ok(not bad, 'no Russian in the Chinese window: %s' % bad[:5])
      page.click('#tabGloss'); page.wait_for_timeout(300)
      ok('5 个词条' in page.inner_text('#glossStatus'), 'number forms in Chinese: %s' % page.inner_text('#glossStatus'))
      page.click('#helpBtn'); page.wait_for_selector('#helpView:not([hidden])')
      ok(page.locator('#helpBody h3').first.inner_text() == '翻译' and page.locator('#helpBody h3').count() == 12 and texts(page, '#helpBody h3')[-2] == '更新与卸载', 'help in Chinese: %s' % texts(page, '#helpBody h3')[-3:])
      page.click('#testBtn'); page.wait_for_timeout(300)
      ok('句子对：6' in page.inner_text('#testIntro') and '快速测试。两句拉丁语名言' in page.inner_text('#testIntro') and '拉丁语 ↔ 中文' in page.inner_text('#testIntro')
         and '“中性”、“口语”' in page.inner_text('#testIntro'),
         'the test panel in Chinese: %s' % page.inner_text('#testIntro').replace('\n', ' | ')[:200])
      ok(page.evaluate("quickJobs().map(j => j.from + '>' + j.to + ':' + j.ref)") == ['la>zh:命运眷顾勇敢的人。', 'zh>la:Audentes fortuna iuvat.', 'la>zh:我思故我在。', 'zh>la:Cogito, ergo sum.'],
         'the quick test with the Chinese interface: Latin ↔ Chinese')
      page.screenshot(path=os.path.join(shots, '4-main-zh.png'))
      code, j = post('/api/voice', {'id': 'nope'})
      ok(code == 400 and j.get('error') == '未知语音', 'a message of the launcher in Chinese: %s' % j)

      # ================= English: «Авто» and the start languages
      post('/api/settings', {'ui_language': 'en'})
      page.close(); page = ctx.new_page()
      page.goto(URL); ready(page, 30000); page.wait_for_timeout(500)
      ok(page.input_value('#srcSel') == 'en' and page.input_value('#tgtSel') == 'ru', 'a new window with the English interface: English → Russian')
      ok(page.evaluate("[AUTO_TARGET('en'), AUTO_TARGET('de')]") == ['ru', 'en'] and page.get_attribute('#tgtSel option[value="auto"]', 'title') == 'English text into Russian, text in any other language into English',
         '«Авто» on the right with the English interface')
      ok(not errors, 'no page errors: %s' % errors[:3])
      b.close()
finally:
    try: post('/api/quit', {})
    except Exception: pass
print('FAILS:', sum(1 for x in log if x.startswith('FAIL')), 'of', len(log))
