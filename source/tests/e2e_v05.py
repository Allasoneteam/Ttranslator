# End-to-end test of the v0.5 features: the ↔ button, the work window staying open while the model is unloaded,
# loading or broken, "Please load a model." instead of translating, the state banner, the Exit button.
# Launcher + engine with a stand-in model + UI in Chromium.
# Usage: e2e_v05.py <work> <ui_url> <root>   (a launcher in a fresh folder, already past the first run;
# the test ends by closing that launcher with the Exit button)
import sys, json, os, subprocess, time, urllib.request, urllib.error
from playwright.sync_api import sync_playwright
S, URL, ROOT = sys.argv[1], sys.argv[2], sys.argv[3]
shots = os.path.join(S, 'shots', 'v05'); os.makedirs(shots, exist_ok=True)
log = []
NEED = 'Please load a model.'
def ok(cond, msg):
    log.append(('OK  ' if cond else 'FAIL') + ' ' + msg); print(log[-1], flush=True)
def api(path):
    return json.load(urllib.request.urlopen(URL.rstrip('/') + path, timeout=5))
def raw_chat():
    req = urllib.request.Request(URL.rstrip('/') + '/v1/chat/completions', data=b'{"messages":[]}',
                                 headers={'Content-Type': 'application/json', 'Origin': URL.rstrip('/')})
    try:
        urllib.request.urlopen(req, timeout=5)
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())
    return 200, {}
def engine_running():
    return bool(subprocess.run(['pgrep', '-f', ROOT + '/engine/'], capture_output=True, text=True).stdout.strip())
def wait_idle(page, t=60000):
    page.wait_for_selector('#goBtn:not([hidden])', timeout=t)
def ready(page, t=60000):
    page.wait_for_selector('body[data-model="ready"]', timeout=t)
def opacity(page, sel):
    return float(page.evaluate("(s) => getComputedStyle(document.querySelector(s)).opacity", sel))
def toast(page):
    return page.inner_text('#toast')

try:
  with sync_playwright() as p:
      b = p.chromium.launch()
      ctx = b.new_context(viewport={'width': 1180, 'height': 780}, locale='ru-RU')
      ctx.grant_permissions(['clipboard-read', 'clipboard-write'])
      ctx.add_init_script("window.__closeCalls = 0; window.close = () => { window.__closeCalls++; };")
      # the start languages of a new window (0.6.1) are tested in e2e_v061.py; here the window is an "old" one
      ctx.add_init_script("try { sessionStorage.setItem('tdoc.window', '1'); sessionStorage.setItem('tdoc.welcome', 'done') } catch (e) {}")
      page = ctx.new_page()
      errors = []
      page.on('console', lambda m: errors.append(m.text) if m.type == 'error' and 'status of 503' not in m.text else None)
      page.on('pageerror', lambda e: errors.append(str(e)))
      chat_reqs = []
      page.on('request', lambda r: chat_reqs.append(r.url) if '/v1/chat/completions' in r.url else None)
      page.goto(URL); ready(page)

      # --- name and buttons
      ok(page.title() == 'Ttranslator', 'page title: ' + page.title())
      ok(page.inner_text('.brand').strip() == 'Ttranslator', 'brand: ' + page.inner_text('.brand'))
      ok(page.is_visible('#swapBtn') and page.is_visible('#randomBtn') and page.is_visible('#quitBtn'), 'buttons ↔, Случайно and Выход are visible')
      ok(page.get_attribute('body', 'data-model') == 'ready' and not page.is_visible('#modelBanner'), 'no banner while the model works')
      ok(opacity(page, '#goBtn') == 1 and opacity(page, '#randomBtn') == 1, 'buttons that need the model look normal when it is loaded')

      # --- ↔
      page.select_option('#srcSel', 'en'); page.select_option('#tgtSel', 'de'); page.wait_for_timeout(300)
      page.click('#swapBtn'); page.wait_for_timeout(300)
      ok(page.input_value('#srcSel') == 'de' and page.input_value('#tgtSel') == 'en', 'en → de swapped to de → en')
      ok(page.evaluate("localStorage.getItem('tdoc.srcLang')") == '"de"' and page.evaluate("localStorage.getItem('tdoc.tgtLang')") == '"en"', 'swapped languages are remembered')
      ok(page.inner_text('#modeBadge') == 'немецкий → английский', 'badge after swap: ' + page.inner_text('#modeBadge'))
      page.select_option('#srcSel', 'auto'); page.select_option('#tgtSel', 'auto')
      page.fill('#src', 'Мы представляем точное решение.'); page.wait_for_timeout(400)
      ok(page.inner_text('#modeBadge') == 'русский → английский', 'auto direction: ' + page.inner_text('#modeBadge'))
      page.click('#swapBtn'); page.wait_for_timeout(300)
      ok(page.input_value('#srcSel') == 'en' and page.input_value('#tgtSel') == 'ru', 'Авто turned into the detected languages, swapped: %s → %s' % (page.input_value('#srcSel'), page.input_value('#tgtSel')))
      ok(page.input_value('#src') == 'Мы представляем точное решение.', 'the text is not touched by ↔')
      ok(page.inner_text('#modeBadge') == 'английский → русский', 'badge: ' + page.inner_text('#modeBadge'))
      page.click('#swapBtn'); page.wait_for_timeout(300)
      ok(page.input_value('#srcSel') == 'ru' and page.input_value('#tgtSel') == 'en', 'second ↔ goes back')
      page.select_option('#srcSel', 'ru'); page.select_option('#tgtSel', 'ru'); page.wait_for_timeout(300)
      page.click('#swapBtn'); page.wait_for_timeout(200)
      ok(page.input_value('#srcSel') == 'ru' and page.input_value('#tgtSel') == 'ru' and 'нечего' in toast(page), 'editing mode (same language): nothing to swap, hint: ' + toast(page))
      page.select_option('#srcSel', 'auto'); page.select_option('#tgtSel', 'auto'); page.fill('#src', ''); page.wait_for_timeout(300)
      page.click('#swapBtn'); page.wait_for_timeout(300)
      ok(page.input_value('#srcSel') == 'en' and page.input_value('#tgtSel') == 'ru', 'empty text: swaps the default direction')
      page.select_option('#srcSel', 'auto'); page.select_option('#tgtSel', 'auto')

      # --- the window stays when the model is unloaded
      text_ru = 'Мы представляем точное решение в замкнутой форме.'
      page.fill('#src', text_ru); page.wait_for_timeout(300)
      page.click('#goBtn'); wait_idle(page)
      n_cards = page.locator('.card').count()
      ok(n_cards >= 1, 'translated before unloading: %d cards' % n_cards)
      page.fill('#askInput', 'Как лучше сказать?'); page.click('#askSend')
      page.wait_for_selector('#askLog .msg.bot:not(.pending)', timeout=60000)
      n_msgs = page.locator('#askLog .msg').count()
      page.click('.card [data-act=save]'); page.wait_for_timeout(500)
      ok('(1)' in page.inner_text('#savedCount'), 'a result is saved: ' + page.inner_text('#savedCount'))
      chat_reqs.clear()
      page.click('#unloadBtn'); page.wait_for_selector('body[data-model="unloaded"]', timeout=15000)
      page.wait_for_timeout(300)
      ok(page.is_visible('#mainView') and page.is_visible('#modelBanner') and page.is_visible('#bnUnloaded'), 'work window stays, banner on top')
      ok('выгружена из памяти' in page.inner_text('#bnUnloaded') and page.inner_text('#loadBtn').startswith('Загрузить '), 'banner text and button: ' + page.inner_text('#bnUnloaded')[:70])
      ok(page.input_value('#src') == text_ru and page.locator('.card').count() == n_cards and page.locator('#askLog .msg').count() == n_msgs, 'text, results and chat are still there')
      ok(page.is_visible('#savedBtn') and page.is_visible('#testBtn') and page.is_visible('#quitBtn'), 'Сохранённые, Тест and Выход stay available')
      ok(opacity(page, '#goBtn') < 1 and opacity(page, '#askSend') < 1 and opacity(page, '#randomBtn') < 1 and opacity(page, '.card [data-act=more]') < 1, 'buttons that need the model look dimmed')
      ok(opacity(page, '.card [data-act=copy]') == 1 and opacity(page, '.card [data-act=save]') == 1, 'copy and save stay normal')
      ok(page.is_enabled('#goBtn') and page.is_enabled('#askSend'), 'dimmed buttons can still be pressed')
      page.screenshot(path=os.path.join(shots, '1-unloaded.png'))
      # editing and language detection work without a model
      page.fill('#src', 'Wir stellen eine geschlossene Lösung vor.'); page.wait_for_timeout(400)
      ok(page.inner_text('#counter') == '41 из 1000', 'counter works: ' + page.inner_text('#counter'))
      ok(page.inner_text('#modeBadge') == 'немецкий → русский', 'detection works without a model: ' + page.inner_text('#modeBadge'))
      page.click('#swapBtn'); page.wait_for_timeout(200)
      ok(page.input_value('#srcSel') == 'ru' and page.input_value('#tgtSel') == 'de', '↔ works without a model')
      page.click('#swapBtn'); page.select_option('#srcSel', 'auto'); page.select_option('#tgtSel', 'auto')
      # actions that need the model: a hint, no request, nothing changes
      page.click('#goBtn'); page.wait_for_timeout(250)
      ok(toast(page) == NEED and not chat_reqs and page.locator('.card').count() == n_cards, 'Перевести: "%s", no request, no new cards' % toast(page))
      ok(page.inner_text('#formError') == '', 'no error line under the button')
      page.evaluate("document.querySelector('#toast').classList.remove('show'); document.querySelector('#toast').textContent = ''")
      page.fill('#askInput', 'Вопрос без модели'); page.click('#askSend'); page.wait_for_timeout(250)
      ok(toast(page) == NEED and page.input_value('#askInput') == 'Вопрос без модели' and not chat_reqs and page.locator('#askLog .msg').count() == n_msgs, 'chat: hint, the question stays in the field, no request')
      page.evaluate("document.querySelector('#toast').textContent = ''")
      page.click('#randomBtn'); page.wait_for_timeout(250)
      ok(toast(page) == NEED and page.input_value('#src') == 'Wir stellen eine geschlossene Lösung vor.' and not chat_reqs, 'Случайно: hint, the text is not replaced, no request')
      for act in ('more', 'back'):
          page.evaluate("document.querySelector('#toast').textContent = ''")
          page.locator('.card [data-act=%s]' % act).first.click(); page.wait_for_timeout(250)
          ok(toast(page) == NEED and not chat_reqs, 'card button «%s»: hint, no request' % act)
      page.evaluate("document.querySelector('#toast').textContent = ''")
      page.locator('.card [data-act=ask]').first.click(); page.wait_for_selector('#popMenu:not([hidden])')
      page.locator('#popMenu .mi').first.click(); page.wait_for_timeout(250)
      ok(toast(page) == NEED and not chat_reqs, 'question about a variant: hint, no request')
      page.click('#testBtn'); page.wait_for_selector('#testView:not([hidden])')
      page.evaluate("document.querySelector('#toast').textContent = ''")
      page.click('#runTestBtn'); page.wait_for_timeout(250)
      ok(toast(page) == NEED and not chat_reqs, 'Запустить тест: hint, no request')
      page.click('#closeTestBtn')
      # what does not need the model keeps working
      page.locator('.card [data-act=copy]').first.click(); page.wait_for_timeout(200)
      ok('on' in (page.locator('.card [data-act=copy]').first.get_attribute('class') or ''), 'copying a variant works')
      page.click('#savedBtn'); page.wait_for_selector('#savedList .item', timeout=5000)
      ok(page.is_visible('#savedView') and page.locator('#savedList .item').count() == 1, 'saved list opens: %d item' % page.locator('#savedList .item').count())
      page.click('#closeSavedBtn')
      # the engine endpoint itself
      code, body = raw_chat()
      ok(code == 503 and body['error']['message'] == NEED, 'direct request to the engine: %s %s' % (code, body))
      ok(api('/api/state')['phase'] == 'unloaded', 'launcher state: unloaded')
      # load back: everything on the screen is still there
      page.evaluate("""() => { window.__seq = []; new MutationObserver(() => { const m = document.body.dataset.model; if (window.__seq[window.__seq.length - 1] !== m) window.__seq.push(m); }).observe(document.body, { attributes: true, attributeFilter: ['data-model'] }); }""")
      page.click('#loadBtn'); ready(page)
      seq = page.evaluate('window.__seq')
      ok(seq[-1] == 'ready' and 'error' not in seq and 'setup' not in seq, 'loading goes to ready without errors: %s' % seq)
      ok(not page.is_visible('#modelBanner') and opacity(page, '#goBtn') == 1, 'banner gone, buttons normal')
      ok(page.locator('.card').count() == n_cards and page.locator('#askLog .msg').count() == n_msgs, 'results and chat survived unload/load')
      page.fill('#src', text_ru); page.click('#goBtn'); wait_idle(page)
      ok(page.locator('.card').count() >= 1 and page.inner_text('#formError') == '', 'translation works again')

      # --- reload while unloaded: the window comes up with the banner, not an empty screen
      page.click('#unloadBtn'); page.wait_for_selector('body[data-model="unloaded"]', timeout=15000)
      page.reload(); page.wait_for_selector('body[data-model="unloaded"]', timeout=15000)
      ok(page.is_visible('#mainView') and page.is_visible('#bnUnloaded') and page.is_visible('#src'), 'after reload: work window with the banner')
      page.fill('#src', 'Привет, мир'); page.wait_for_timeout(300)
      ok(page.input_value('#src') == 'Привет, мир', 'text can be typed after reload')
      page.click('#loadBtn'); ready(page)

      # --- banner variants (the launcher state is replaced on the way)
      def fake(phase, **extra):
          def h(route):
              j = route.fetch().json(); j['phase'] = phase; j.update(extra)
              route.fulfill(status=200, content_type='application/json', body=json.dumps(j))
          return h
      page.route('**/api/state', fake('starting'))
      page.evaluate('refreshState()'); page.wait_for_selector('body[data-model="starting"]', timeout=5000)
      ok(page.is_visible('#bnStarting') and page.is_visible('#modelBanner .spinner') and 'info' in page.get_attribute('#modelBanner', 'class'), 'banner while the model loads')
      ok(page.is_visible('#mainView') and page.is_enabled('#src'), 'work window is available while the model loads')
      page.evaluate("document.querySelector('#toast').textContent = ''")
      page.click('#goBtn'); page.wait_for_timeout(250)
      ok('загружается' in toast(page), 'Перевести while loading: ' + toast(page))
      page.screenshot(path=os.path.join(shots, '2-starting.png'))
      page.unroute('**/api/state')
      page.route('**/api/state', fake('error', error='Тестовая ошибка запуска', engine_log='строка журнала 1\nстрока журнала 2'))
      page.evaluate('refreshState()'); page.wait_for_selector('body[data-model="error"]', timeout=5000)
      ok(page.is_visible('#bnError') and page.inner_text('#errorTitle') == 'Движок не запустился.' and page.inner_text('#errorText') == 'Тестовая ошибка запуска', 'error banner: ' + page.inner_text('#bnError')[:60])
      ok(page.is_visible('#retryBtn') and page.is_visible('#errorModelBtn') and page.is_visible('#errorOpenBtn') and page.is_visible('#errorLogBtn'), 'error banner buttons')
      ok(not page.is_visible('#errorLog'), 'log is folded')
      page.click('#errorLogBtn'); page.wait_for_selector('#errorLog:not([hidden])', timeout=5000)
      ok('строка журнала 2' in page.inner_text('#errorLog') and page.inner_text('#errorLogBtn') == 'Скрыть подробности', 'log opens')
      page.screenshot(path=os.path.join(shots, '3-error.png'))
      page.click('#errorLogBtn'); page.wait_for_selector('#errorLog', state='hidden', timeout=5000)
      page.evaluate("document.querySelector('#toast').textContent = ''")
      page.click('#goBtn'); page.wait_for_timeout(250)
      ok(toast(page) == NEED, 'Перевести with a broken engine: ' + toast(page))
      page.unroute('**/api/state')
      page.route('**/api/state', lambda r: r.abort())
      page.evaluate('refreshState()'); page.wait_for_selector('#bnError:not([hidden])', timeout=5000)
      ok(page.inner_text('#errorTitle') == 'Программа Ttranslator не отвечает.' and page.is_hidden('#retryBtn') and page.is_hidden('#errorModelBtn') and page.is_hidden('#errorOpenBtn'), 'launcher not answering: banner without useless buttons')
      ok(page.is_visible('#mainView') and page.input_value('#src') == 'Привет, мир', 'work window and text stay when the launcher is gone')
      page.unroute('**/api/state')
      ready(page, 10000)
      ok(not page.is_visible('#modelBanner'), 'the window recovers by itself when the launcher answers again')
      ok(not errors or all('net::' in e for e in errors), 'no console errors: %s' % errors[:3])

      # --- Exit
      page.click('#quitBtn')
      ok(page.inner_text('#quitLabel') == 'Выйти?' and 'confirm' in page.get_attribute('#quitBtn', 'class'), 'first click asks to confirm')
      page.keyboard.press('Escape')
      ok(page.inner_text('#quitLabel') == 'Выход', 'Esc cancels')
      page.click('#quitBtn'); page.wait_for_timeout(4400)
      ok(page.inner_text('#quitLabel') == 'Выход' and page.evaluate('window.__closeCalls') == 0, 'confirmation expires by itself, nothing closed')
      ok(api('/api/ping')['app'] == 'tdoc-translator', 'launcher still runs')
      page.click('#quitBtn'); page.click('#quitBtn')
      page.wait_for_selector('#byeView:not([hidden])', timeout=5000)
      ok(page.is_hidden('#mainView') and page.is_hidden('#modelBanner') and page.is_hidden('#quitBtn'), 'bye screen replaces the work window')
      ok(page.evaluate('window.__closeCalls') >= 1, 'the page asked the browser to close the window')
      page.screenshot(path=os.path.join(shots, '4-bye.png'))
      gone = False
      for i in range(40):
          try:
              urllib.request.urlopen(URL.rstrip('/') + '/api/ping', timeout=1)
          except Exception:
              gone = True; break
          time.sleep(0.25)
      ok(gone, 'launcher exited')
      time.sleep(0.5)
      ok(not engine_running(), 'engine stopped with it')
      b.close()
finally:
  print(chr(10).join(l for l in log if l.startswith('FAIL')) or 'ALL OK', len(log), 'checks')
