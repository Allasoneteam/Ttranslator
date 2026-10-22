# End-to-end test of the v0.3 features (languages, 1000 characters, chat, unload/load of the model).
# Launcher + engine with a stand-in model + UI in Chromium. Usage: e2e_v03.py <work> <ui_url> <root>  (fresh root)
import sys, json, os, subprocess, urllib.request, urllib.error
from playwright.sync_api import sync_playwright
S, URL, ROOT = sys.argv[1], sys.argv[2], sys.argv[3]
shots = os.path.join(S, 'shots', 'v03'); os.makedirs(shots, exist_ok=True)
log = []
def ok(cond, msg):
    log.append(('OK  ' if cond else 'FAIL') + ' ' + msg); print(log[-1], flush=True)
def api(path):
    return json.load(urllib.request.urlopen(URL.rstrip('/') + path, timeout=5))
def status(path):
    try:
        return urllib.request.urlopen(URL.rstrip('/') + path, timeout=5).status
    except urllib.error.HTTPError as e:
        return e.code
def engine_running():
    out = subprocess.run(['pgrep', '-f', ROOT + '/engine/'], capture_output=True, text=True).stdout.strip()
    return bool(out)
def wait_idle(page, t=60000):
    page.wait_for_selector('#goBtn:not([hidden])', timeout=t)

try:
  with sync_playwright() as p:
      b = p.chromium.launch()
      ctx = b.new_context(viewport={'width': 1180, 'height': 780}, locale='ru-RU')
      ctx.grant_permissions(['clipboard-read', 'clipboard-write'])
      # the start languages of a new window (0.6.1) are tested in e2e_v061.py; here the window is an "old" one
      ctx.add_init_script("try { sessionStorage.setItem('tdoc.window', '1'); sessionStorage.setItem('tdoc.welcome', 'done') } catch (e) {}")
      page = ctx.new_page()
      errors = []
      page.on('console', lambda m: errors.append(m.text) if m.type == 'error' and 'status of 503' not in m.text else None)
      page.on('pageerror', lambda e: errors.append(str(e)))
      page.goto(URL)
      page.wait_for_selector('#setupView:not([hidden])', timeout=10000)
      page.click('#dlBtn')
      page.wait_for_selector('body[data-model="ready"]', timeout=90000)
      ok(api('/api/state')['phase'] == 'ready', 'ready after first-run downloads')

      # --- languages
      src_opts = page.locator('#srcSel option').all_inner_texts()
      tgt_opts = page.locator('#tgtSel option').all_inner_texts()
      want = ['Авто', 'Русский', 'Английский', 'Немецкий', 'Французский', 'Испанский', 'Греческий', 'Китайский', 'Латынь', 'Шведский']
      ok(src_opts == want and tgt_opts == want, 'language lists: %s' % src_opts)
      samples = {
          'ru': 'Мы представляем точное решение в замкнутой форме.',
          'en': 'We present a closed-form solution for the n-th term of a recurrence relation.',
          'de': 'Wir stellen eine geschlossene Lösung für das n-te Glied einer Rekursion vor.',
          'fr': 'Nous présentons une solution exacte pour le terme général de cette relation.',
          'es': 'Presentamos una solución exacta para el término general de la relación de recurrencia.',
          'el': 'Παρουσιάζουμε μια λύση κλειστής μορφής για τον ν-οστό όρο.',
          'zh': '我们给出了一般三项递推关系第n项的闭式解。',
          'la': 'Gallia est omnis divisa in partes tres, quarum unam incolunt Belgae.',
          'sv': 'Vi presenterar en sluten lösning för den n:te termen i en rekursionsrelation.',
      }
      got = page.evaluate('(s) => Object.fromEntries(Object.entries(s).map(([k, t]) => [k, detectLang(t)]))', samples)
      ok(all(got[k] == k for k in samples), 'detection: %s' % got)
      mixed = page.evaluate("detectLang('Пусть параметр α мал, а β порядка единицы.')")
      ok(mixed == 'ru', 'Russian text with Greek letters stays Russian: %s' % mixed)

      page.fill('#src', samples['de']); page.wait_for_timeout(400)
      ok(page.inner_text('#modeBadge') == 'немецкий → русский', 'badge for German: ' + page.inner_text('#modeBadge'))
      ok('определён автоматически' in page.get_attribute('#modeBadge', 'title'), 'badge tooltip mentions auto-detection')
      page.fill('#src', samples['ru']); page.select_option('#tgtSel', 'sv'); page.wait_for_timeout(300)
      ok(page.inner_text('#modeBadge') == 'русский → шведский', 'badge ru → sv: ' + page.inner_text('#modeBadge'))
      ok(page.is_visible('#modeHint') and 'шведский' in page.inner_text('#modeHint'), 'Hy-MT2 hint for Swedish: ' + page.inner_text('#modeHint'))
      page.select_option('#tgtSel', 'de'); page.wait_for_timeout(300)
      ok(not page.is_visible('#modeHint'), 'no hint for German with Hy-MT2')
      page.select_option('#tgtSel', 'auto')
      page.fill('#src', samples['de']); page.wait_for_timeout(300)
      page.click('#goBtn'); wait_idle(page)
      ok(page.locator('.card').count() >= 1, 'German text translated: %d cards' % page.locator('.card').count())

      # --- 1000-character limit
      page.fill('#src', 'а' * 1000); page.wait_for_timeout(200)
      ok(page.inner_text('#counter') == '1000 из 1000', 'counter at 1000: ' + page.inner_text('#counter'))
      ok('1000' in page.get_attribute('#src', 'placeholder'), 'placeholder mentions 1000')
      page.fill('#src', 'а' * 1001); page.click('#goBtn'); page.wait_for_timeout(200)
      ok('длиннее 1000' in page.inner_text('#formError'), 'over-limit error: ' + page.inner_text('#formError'))
      page.fill('#src', samples['ru'])

      # --- layout: chat fills the left column down to the bottom edge, no scrollbar at 1180x780
      lay = page.evaluate("""() => {
        const l = document.querySelector('.left').getBoundingClientRect(), a = document.querySelector('#askBox').getBoundingClientRect();
        const left = document.querySelector('.left');
        return { gap: l.bottom - a.bottom, askH: a.height, scroll: left.scrollHeight - left.clientHeight, logH: document.querySelector('#askLog').getBoundingClientRect().height };
      }""")
      ok(abs(lay['gap'] - 16) <= 2 and lay['scroll'] <= 1, 'chat reaches the bottom: %s' % lay)
      ok(lay['askH'] >= 230, 'chat height %d px' % lay['askH'])

      # --- chat
      page.fill('#askInput', 'Как лучше перевести perturbation theory?')
      page.click('#askSend')
      page.wait_for_selector('#askLog .msg.bot:not(.pending)', timeout=60000)
      ok(page.locator('#askLog .msg.user').count() == 1 and page.locator('#askLog .msg.bot').count() == 1, 'question and answer shown')
      bot = page.locator('#askLog .msg.bot').first
      ok(bot.locator('.msg-meta').count() == 1 or 'err' in (bot.get_attribute('class') or ''), 'answer has meta line (time/speed): ' + (bot.inner_text()[:60]))
      ok(page.inner_text('#askSend') == 'Ввод', 'send button back to Ввод')
      ok(page.is_visible('#askNote'), 'chat shows the Hy-MT2 note: ' + page.inner_text('#askNote')[:40])
      page.fill('#askInput', 'А theory of perturbations?')
      page.press('#askInput', 'Enter')
      page.wait_for_function("document.querySelectorAll('#askLog .msg.bot:not(.pending)').length == 2", timeout=60000)
      ok(page.locator('#askLog .msg').count() == 4, 'Enter sends: %d messages' % page.locator('#askLog .msg').count())
      page.screenshot(path=os.path.join(shots, '1-chat.png'))
      page.click('#askReset'); page.wait_for_timeout(200)
      ok(page.locator('#askLog .msg').count() == 0 and page.is_visible('#askEmpty'), 'Обновить clears the chat')
      page.fill('#askInput', 'Ещё вопрос'); page.click('#askSend')
      page.wait_for_selector('#askLog .msg.bot:not(.pending)', timeout=60000)

      # --- unload / load
      ok(page.is_visible('#unloadBtn'), 'unload button visible next to the model name')
      ok('Выгрузить' in page.get_attribute('#unloadBtn', 'title'), 'unload tooltip: ' + page.get_attribute('#unloadBtn', 'title'))
      ok(engine_running(), 'engine process runs before unloading')
      page.click('#unloadBtn')
      page.wait_for_selector('body[data-model="unloaded"]', timeout=15000)
      ok(page.is_visible('#mainView') and page.is_visible('#bnUnloaded') and not page.is_visible('#bnStarting'), 'work window stays, the banner says the model is unloaded')
      st = api('/api/state')
      ok(st['phase'] == 'unloaded' and st['unloaded'], 'state unloaded: ' + st['phase'])
      page.wait_for_timeout(500)
      ok(not engine_running(), 'engine process gone after unloading')
      ok(status('/health') == 503, 'engine endpoint answers 503 while unloaded')
      ok(page.inner_text('#engineInfo') == 'модель выгружена из памяти', 'footer: ' + page.inner_text('#engineInfo'))
      ok('Загрузить' in page.get_attribute('#unloadBtn', 'title'), 'header button now loads')
      ok(page.inner_text('#loadBtn').startswith('Загрузить '), 'load button: ' + page.inner_text('#loadBtn'))
      page.screenshot(path=os.path.join(shots, '2-unloaded.png'))
      page.wait_for_timeout(3500)
      ok(api('/api/state')['phase'] == 'unloaded', 'stays unloaded (no automatic restart)')
      page.click('#loadBtn')
      page.wait_for_selector('body[data-model="ready"]', timeout=60000)
      ok(api('/api/state')['phase'] == 'ready' and engine_running(), 'loaded again')
      ok(page.locator('#askLog .msg').count() == 2, 'chat kept across unload/load')
      ok(page.input_value('#src') == samples['ru'], 'source text kept across unload/load')

      # unload, then pick another model from the unloaded screen (needs download): it loads
      page.click('#unloadBtn'); page.wait_for_selector('body[data-model="unloaded"]', timeout=15000)
      page.click('#unloadedModelBtn'); page.wait_for_selector('#modelMenu:not([hidden])')
      ok('выгружена из памяти' in page.inner_text('#modelMenu'), 'menu marks the active model as unloaded')
      item = page.locator('#modelMenu .mitem', has_text='Q8_0').locator('button.pick')
      item.click(); page.click('#modelMenu .dl-confirm button.primary')
      page.wait_for_selector('body[data-model="ready"]', timeout=90000)
      st = api('/api/state')
      ok(st['active_model'] == 'q8' and st['phase'] == 'ready' and not st['unloaded'], 'switched to q8 and loaded: %s %s' % (st['active_model'], st['phase']))
      # header button toggles too
      page.click('#unloadBtn'); page.wait_for_selector('body[data-model="unloaded"]', timeout=15000)
      page.click('#unloadBtn'); page.wait_for_selector('body[data-model="ready"]', timeout=60000)
      ok(api('/api/state')['phase'] == 'ready', 'header button loads the model back')

      page.emulate_media(color_scheme='dark'); page.wait_for_timeout(200)
      page.screenshot(path=os.path.join(shots, '3-dark.png'))
      ok(not errors, 'no console errors: %s' % errors[:3])
      b.close()
finally:
  print(chr(10).join(l for l in log if l.startswith('FAIL')) or 'ALL OK', len(log), 'checks')
