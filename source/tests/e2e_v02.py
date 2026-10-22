# End-to-end test of the v0.2 features (translation, same-language editing, saved, test, model menu).
# Launcher + engine with a stand-in model + UI in Chromium. Usage: e2e_v02.py <work> <ui_url> <root>  (fresh root)
import sys, json, time, os, shutil, urllib.request
from playwright.sync_api import sync_playwright
S, URL, ROOT = sys.argv[1], sys.argv[2], sys.argv[3]
shots = os.path.join(S, 'shots', 'v02'); os.makedirs(shots, exist_ok=True)
log = []
def ok(cond, msg):
    log.append(('OK  ' if cond else 'FAIL') + ' ' + msg); print(log[-1], flush=True)
def api(path):
    return json.load(urllib.request.urlopen(URL.rstrip('/') + path, timeout=5))
def wait_idle(page, t=60000):
    page.wait_for_selector('#goBtn:not([hidden])', timeout=t)

try:
  with sync_playwright() as p:
      b = p.chromium.launch()
      ctx = b.new_context(viewport={'width': 1180, 'height': 800}, locale='ru-RU')
      ctx.grant_permissions(['clipboard-read', 'clipboard-write'])
      # the start languages of a new window (0.6.1) are tested in e2e_v061.py; here the window is an "old" one
      ctx.add_init_script("try { sessionStorage.setItem('tdoc.window', '1'); sessionStorage.setItem('tdoc.welcome', 'done') } catch (e) {}")
      page = ctx.new_page()
      errors = []
      page.on('console', lambda m: errors.append(m.text) if m.type == 'error' else None)
      page.on('pageerror', lambda e: errors.append(str(e)))
      page.goto(URL)
      page.wait_for_selector('#setupView:not([hidden])', timeout=10000)
      page.click('#dlBtn')
      page.wait_for_selector('body[data-model="ready"]', timeout=90000)
      ok(api('/api/state')['phase'] == 'ready', 'ready after first-run downloads')

      # translation, auto direction
      page.fill('#src', 'Мы представляем точное решение в замкнутой форме.')
      page.wait_for_timeout(400)
      ok(page.inner_text('#modeBadge') == 'русский → английский', 'badge: ' + page.inner_text('#modeBadge'))
      ok(page.inner_text('#goLabel') == 'Перевести', 'button says Перевести')
      chips = page.locator('#chips .chip').all_inner_texts()
      ok('Замечания' not in chips and 'Другими словами' not in chips, 'edit-only chips hidden in translation: %s' % chips)
      page.click('#goBtn'); wait_idle(page)
      ok(page.locator('.card').count() >= 1, 'translation cards: %d' % page.locator('.card').count())
      ok(page.locator('.card').first.locator('[data-act=back]').count() == 1, 'translation card has back-translation')
      page.screenshot(path=os.path.join(shots, '1-translate.png'))

      # same-language editing
      page.select_option('#tgtSel', 'ru'); page.wait_for_timeout(200)
      ok(page.inner_text('#modeBadge').startswith('правка: русский'), 'edit badge: ' + page.inner_text('#modeBadge'))
      ok(page.inner_text('#goLabel') == 'Обработать', 'button says Обработать')
      chips = page.locator('#chips .chip').all_inner_texts()
      ok(chips[0] == 'Исправленный' and 'Замечания' in chips and 'Другими словами' in chips, 'edit chips: %s' % chips)
      ok(page.is_visible('#modeHint'), 'hint about Hy-MT2 for editing shown: ' + page.inner_text('#modeHint')[:50])
      page.locator('#chips .chip', has_text='Замечания').click()
      page.click('#goBtn'); wait_idle(page)
      labels = page.locator('.card-label').all_inner_texts()
      ok(labels and labels[0].startswith('Исправленный'), 'edit labels: %s' % labels)
      first = page.locator('.card:not(.err)').first
      ok(page.locator('.card.comments').count() <= 1, 'comments card at most one')
      if first.count():
          ok(first.locator('.card-diff').is_visible() or not first.locator('[data-act=diff]').count(), 'diff shown on corrected card')
          ok(first.locator('[data-act=back]').count() == 0, 'no back-translation in edit mode')
          first.locator('[data-act=save]').click(); page.wait_for_timeout(400)
      page.screenshot(path=os.path.join(shots, '2-edit.png'))
      page.click('#savedBtn'); page.wait_for_selector('#savedList .item', timeout=5000)
      ok('правка (русский)' in page.locator('#savedList .item .meta').first.inner_text(), 'saved shows editing direction')
      page.click('#closeSavedBtn')
      page.select_option('#tgtSel', 'auto')

      # test with translation + correction items
      page.click('#testBtn'); page.wait_for_timeout(300)
      ok('Модель:' in page.inner_text('#testIntro'), 'test intro names model')
      page.click('#runTestBtn')
      page.wait_for_function("document.querySelector('#testProgressText').textContent.startsWith('Готово') || document.querySelector('#testProgressText').textContent.startsWith('Ошибка')", timeout=180000)
      n_pairs, n_math = page.evaluate('loadTests().then(p => p.length)'), page.evaluate('MATH_TESTS.length')
      ok(n_pairs >= 1 and page.inner_text('#testProgressText').startswith('Готово: %d ' % (n_pairs * 6 + n_math * 2)),
         'test (%d pairs from tests.txt × 6 tasks and %d with formulas × 2): %s' % (n_pairs, n_math, page.inner_text('#testProgressText')))
      page.wait_for_function("document.querySelector('#testSummary').textContent.includes('Отчёт сохранён')", timeout=15000)
      rep = sorted(f for f in os.listdir(os.path.join(ROOT, 'data/reports')) if f.endswith('.md'))
      md = open(os.path.join(ROOT, 'data/reports', rep[-1]), encoding='utf-8').read()
      ok('## Правка на том же языке' in md and 'Правки (' in md, 'report has editing section')
      ok('## Формулы LaTeX' in md and 'Формулы LaTeX на месте: ' in md and md.count('- Образец перевода:') == n_math * 2, 'report has the formulas section')
      page.click('#closeTestBtn')

      # model menu: groups, custom file, delete, download
      shutil.copy(os.path.join(S, 'mirror/tiny-q8.gguf'), os.path.join(ROOT, 'models/my-custom-model.gguf'))
      page.click('#modelBtn'); page.wait_for_selector('#modelMenu:not([hidden])')
      groups = page.locator('#modelMenu .group').all_inner_texts()
      ok('Свои файлы из папки models' in groups, 'menu groups: %s' % groups)
      page.screenshot(path=os.path.join(shots, '3-menu.png'))
      page.locator('#modelMenu .mitem', has_text='my-custom-model').locator('button.pick').click()
      page.wait_for_function("document.querySelector('#modelName').textContent.includes('my-custom-model')", timeout=30000)
      page.wait_for_selector('body[data-model="ready"]', timeout=30000)
      st = api('/api/state')
      am = [m for m in st['models'] if m['id'] == st['active_model']][0]
      ok(am['custom'] and am['family'] == 'chat', 'custom model active with chat family')
      page.select_option('#tgtSel', 'ru'); page.fill('#src', 'Привет, как дела?'); page.wait_for_timeout(300)
      ok(not page.is_visible('#modeHint'), 'no Hy-MT hint for chat family')
      page.select_option('#tgtSel', 'auto')
      # delete q4 (not active now)
      page.click('#modelBtn'); page.wait_for_selector('#modelMenu:not([hidden])')
      row = page.locator('#modelMenu .mitem').first
      row.locator('button.icon').click(); page.wait_for_timeout(150); row.locator('button.icon').click(); page.wait_for_timeout(600)
      ok(not os.path.exists(os.path.join(ROOT, 'models/tiny-q4.gguf')), 'q4 file deleted via menu')
      # switch to q8 (needs download); the menu stays open after a deletion
      if not page.is_visible('#modelMenu'):
          page.click('#modelBtn')
      page.wait_for_selector('#modelMenu:not([hidden])')
      item = page.locator('#modelMenu .mitem', has_text='Q8_0').locator('button.pick')
      item.click(); page.wait_for_selector('#modelMenu .dl-confirm')
      conf, st = page.inner_text('#modelMenu .dl-confirm'), api('/api/state')
      ok('Откуда:' in conf and 'tiny-q8.gguf' in conf and st['models_dir'] in conf and st['active_model'] != 'q8', 'download asks first: from, to, file')
      page.click('#modelMenu .dl-confirm button.primary')
      page.wait_for_selector('#setupView:not([hidden]), body[data-model="starting"]', timeout=10000)
      page.screenshot(path=os.path.join(shots, '4-switch-download.png'))
      page.wait_for_selector('body[data-model="ready"]', timeout=90000)
      st = api('/api/state'); ok(st['active_model'] == 'q8', 'switched to q8 after download')
      ok(not errors, 'no console errors: %s' % errors[:3])
      b.close()
finally:
  print(chr(10).join(l for l in log if l.startswith('FAIL')) or 'ALL OK', len(log), 'checks')
