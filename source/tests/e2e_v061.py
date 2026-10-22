# End-to-end test of version 0.6.1: the order of the header buttons and the «О программе» button (the icon T);
# the languages of a new window (left — the interface language, right — English; with the English interface —
# Russian), kept within the window, and the hint when the text looks like another language; closing the window:
# the program unloads the model and exits within seconds, a reload or a second window keeps it running.
# Usage: e2e_v061.py <work> <ui_url> <root>   (a launcher in a fresh folder, past the first run; the test ends by
# closing all its windows, and the launcher exits)
import sys, json, os, time, urllib.request, subprocess
from playwright.sync_api import sync_playwright
S, URL, ROOT = sys.argv[1], sys.argv[2], sys.argv[3]
BASE = URL.rstrip('/')
shots = os.path.join(S, 'shots', 'v061'); os.makedirs(shots, exist_ok=True)
log = []
def ok(cond, msg):
    log.append(('OK  ' if cond else 'FAIL') + ' ' + msg); print(log[-1], flush=True)
def alive():
    try:
        urllib.request.urlopen(BASE + '/api/ping', timeout=1); return True
    except Exception:
        return False
def set_settings(d):
    req = urllib.request.Request(BASE + '/api/settings', data=json.dumps(d).encode(), method='POST',
                                 headers={'Content-Type': 'application/json', 'Origin': BASE})
    urllib.request.urlopen(req, timeout=5)
def set_ui_lang(lang):
    set_settings({'ui_language': lang})
def ready(page, t=60000):
    page.wait_for_selector('body[data-model="ready"]', timeout=t)
def langs(page):
    return page.input_value('#srcSel'), page.input_value('#tgtSel')
def hint(page):
    return page.inner_text('#langHint .txt') if page.is_visible('#langHint') else ''
def hint_btn(page):
    return page.inner_text('#langHint button') if page.is_visible('#langHint') else ''
def typed(page, text):
    page.fill('#src', text); page.wait_for_timeout(450)   # «Авто» and the hint react 250 ms after typing
def engine_running():
    return bool(subprocess.run(['pgrep', '-f', ROOT + '/engine/'], capture_output=True, text=True).stdout.strip())

try:
  with sync_playwright() as p:
      b = p.chromium.launch()
      ctx = b.new_context(viewport={'width': 1180, 'height': 780}, locale='ru-RU')
      page = ctx.new_page()
      errors = []
      page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
      page.on('pageerror', lambda e: errors.append(str(e)))
      set_settings({'show_welcome': False})   # new windows here: the welcome window is tested in e2e_v07.py
      page.goto(URL); ready(page)

      # --- header: ⚙ · model ⏏ · Saved · Test · ? · T · Exit
      ids = page.evaluate("[...document.querySelectorAll('header .actions > button')].map(b => b.id)")
      ok(ids == ['settingsBtn', 'modelBtn', 'unloadBtn', 'savedBtn', 'testBtn', 'helpBtn', 'aboutBtn', 'quitBtn'], 'order of the header buttons: %s' % ids)
      vis = page.evaluate("[...document.querySelectorAll('header .actions > button')].filter(b => b.offsetParent).map(b => b.id)")
      ok(vis == ids, 'all of them visible in the work window: %s' % vis)
      ok(page.get_attribute('#aboutBtn', 'title') == 'О программе' and (page.get_attribute('#aboutBtn svg path', 'd') or '').startswith('M67 88.5')
         and page.evaluate("getComputedStyle(document.querySelector('#aboutBtn')).color") == 'rgb(117, 5, 117)', 'the T button: icon t4, hint «О программе»')
      page.click('#aboutBtn')
      ok(page.is_visible('#aboutView') and 'Версия ' + json.load(urllib.request.urlopen(BASE + '/api/ping'))['version'] in page.inner_text('#aboutBody'), 'T opens «О программе»')
      page.click('#closeAboutBtn')
      page.screenshot(path=os.path.join(shots, '1-header.png'), clip={'x': 0, 'y': 0, 'width': 1180, 'height': 110})

      # --- languages of a new window: the interface language on the left, English on the right
      ok(langs(page) == ('ru', 'en') and page.inner_text('#modeBadge') == 'русский → английский', 'new window: %s → %s' % langs(page))
      ok(page.evaluate("[JSON.parse(localStorage.getItem('tdoc.srcLang')), JSON.parse(localStorage.getItem('tdoc.tgtLang'))]") == ['ru', 'en'], 'start languages remembered for this window')
      typed(page, 'Мы представляем решение в замкнутой форме.')
      ok(not page.is_visible('#langHint'), 'Russian text, Russian on the left: no hint')
      # English text with «русский → английский»: the hint offers to swap
      typed(page, 'We present a closed-form solution for the recurrence relation.')
      ok(hint(page) == 'Текст похож на английский.' and hint_btn(page) == 'Поменять местами: английский → русский', 'English text: %s / %s' % (hint(page), hint_btn(page)))
      page.screenshot(path=os.path.join(shots, '2-hint.png'))
      page.click('#langHint button'); page.wait_for_timeout(200)
      ok(langs(page) == ('en', 'ru') and not page.is_visible('#langHint'), 'swapped: %s → %s, hint gone' % langs(page))
      # German text with «английский → русский»: the hint offers to choose German on the left
      typed(page, 'Der Laser ist stark und die Welle ist sehr kurz.')
      ok(hint(page) == 'Текст похож на немецкий.' and hint_btn(page) == 'Выбрать «Немецкий»', 'German text: %s / %s' % (hint(page), hint_btn(page)))
      page.click('#langHint button'); page.wait_for_timeout(200)
      ok(langs(page) == ('de', 'ru') and not page.is_visible('#langHint'), 'German chosen on the left: %s → %s' % langs(page))
      # short texts in another Latin-script language are not judged; another alphabet is
      typed(page, 'Hello world')
      ok(not page.is_visible('#langHint'), 'two English words with German on the left: no hint')
      typed(page, 'Привет')
      ok(hint(page) == 'Текст похож на русский.' and hint_btn(page) == 'Поменять местами: русский → немецкий', 'Cyrillic with German on the left: %s / %s' % (hint(page), hint_btn(page)))
      page.select_option('#srcSel', 'auto'); page.wait_for_timeout(300)
      ok(not page.is_visible('#langHint'), '«Авто» on the left: no hint')

      # --- the choice stays within the window: a reload, a change of the interface language
      page.select_option('#srcSel', 'fr'); page.select_option('#tgtSel', 'de'); page.fill('#src', '')
      page.reload(); ready(page)
      ok(langs(page) == ('fr', 'de'), 'after a reload the window keeps its languages: %s → %s' % langs(page))
      page.click('#settingsBtn')
      with page.expect_navigation(timeout=15000):
          page.select_option('#uiLangSel', 'en')
      ready(page)
      ok(langs(page) == ('fr', 'de') and page.inner_text('#modeBadge') == 'French → German', 'after switching the interface to English: %s → %s, %s' % (langs(page) + (page.inner_text('#modeBadge'),)))
      # a new window with the English interface: English on the left, Russian on the right
      c2 = b.new_context(viewport={'width': 1000, 'height': 700}); p2 = c2.new_page(); p2.goto(URL); ready(p2)
      ok(langs(p2) == ('en', 'ru'), 'new window, English interface: %s → %s' % langs(p2))
      typed(p2, 'Der Laser ist stark und die Welle ist sehr kurz.')
      ok(hint(p2) == 'The text looks like German.' and hint_btn(p2) == 'Choose “German”', 'hint in English: %s / %s' % (hint(p2), hint_btn(p2)))
      c2.close()
      set_ui_lang('ru')
      c3 = b.new_context(viewport={'width': 1000, 'height': 700}); p3 = c3.new_page(); p3.goto(URL); ready(p3)
      ok(langs(p3) == ('ru', 'en'), 'new window, Russian interface again: %s → %s' % langs(p3))

      # --- closing: a second window keeps the program running; the last one closed — it exits within seconds
      p3.close(); c3.close(); time.sleep(7)
      ok(alive(), 'another window is still open: the program keeps running')
      page.reload(); ready(page); time.sleep(7)
      ok(alive() and engine_running(), 'a reload does not close the program')
      ok(not errors or all('net::' in e for e in errors), 'no console errors: %s' % errors[:3])
      t0 = time.time()
      page.close(); ctx.close()
      while alive() and time.time() - t0 < 30:
          time.sleep(0.25)
      gone = time.time() - t0
      ok(not alive() and gone < 9, 'last window closed: the program exited after %.1f s' % gone)
      time.sleep(0.5)
      ok(not engine_running(), 'the engine (and the model) is gone from memory')
      tail = open(os.path.join(ROOT, 'data', 'logs', 'launcher.log'), encoding='utf-8').read().splitlines()[-2:]
      ok(tail == [tail[0][:20] + 'window closed, exiting', tail[1][:20] + 'bye'], 'log: %s' % tail)
      b.close()
except Exception as e:
    import traceback; traceback.print_exc()
    ok(False, 'exception: %s' % e)

fails = [l for l in log if l.startswith('FAIL')]
print('ALL OK %d checks' % len(log) if not fails else 'FAILS: %d of %d' % (len(fails), len(log)))
