# End-to-end test for v0.4 (glossary, «?» questions): launcher + engine (stand-in model) + UI in Chromium.
# Usage: e2e_v04.py <work> <ui_url> <root>    (the launcher must be ready and have no glossary yet)
import sys, json, os, time, codecs, urllib.request, urllib.error
from playwright.sync_api import sync_playwright
S, URL, ROOT = sys.argv[1], sys.argv[2], sys.argv[3]
shots = os.path.join(S, 'shots', 'v04'); os.makedirs(shots, exist_ok=True)
GDIR = os.path.join(ROOT, 'data', 'glossary')
EN1 = 'Over the past two decades, finding new planets has become a piece of cake for astronomers.'
log = []
def ok(cond, msg):
    log.append(('OK  ' if cond else 'FAIL') + ' ' + msg); print(log[-1], flush=True)
def http(method, path, body=None):
    req = urllib.request.Request(URL.rstrip('/') + path, data=body, method=method, headers={'Origin': URL.rstrip('/'), 'Content-Type': 'text/plain; charset=utf-8'})
    try:
        r = urllib.request.urlopen(req, timeout=10); return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()
def gfile(name):
    return open(os.path.join(GDIR, name), 'rb').read().decode('utf-8-sig')
def wait_file(name, pred, t=5):
    end = time.time() + t
    while time.time() < end:
        try:
            if pred(gfile(name)): return True
        except FileNotFoundError: pass
        time.sleep(0.2)
    return False
def row_index(page, value):
    return page.evaluate("(v) => [...document.querySelectorAll('#glossTable tbody tr')].findIndex(tr => [...tr.querySelectorAll('input')].some(i => i.value === v))", value)
def wait_idle(page, t=60000):
    page.wait_for_selector('#goBtn:not([hidden])', timeout=t)

try:
  with sync_playwright() as p:
      b = p.chromium.launch()
      ctx = b.new_context(viewport={'width': 1180, 'height': 780}, locale='ru-RU', accept_downloads=True)
      # the start languages of a new window (0.6.1) are tested in e2e_v061.py; here the window is an "old" one
      ctx.add_init_script("try { sessionStorage.setItem('tdoc.window', '1'); sessionStorage.setItem('tdoc.welcome', 'done') } catch (e) {}")
      page = ctx.new_page()
      errors = []
      page.on('console', lambda m: errors.append(m.text) if m.type == 'error' and 'status of 40' not in m.text else None)
      page.on('pageerror', lambda e: errors.append(str(e)))
      page.goto(URL); page.wait_for_selector('body[data-model="ready"]', timeout=30000)
      page.wait_for_function("document.querySelector('#glossTabInfo').textContent !== ''", timeout=10000)

      # --- default glossary file
      st, body = http('GET', '/api/glossary')
      files = [f['name'] for f in json.loads(body)['files']]
      ok(files == ['Мой словарь.tsv'], 'default glossary created: %s' % files)
      raw = open(os.path.join(GDIR, 'Мой словарь.tsv'), 'rb').read()
      text = raw.decode('utf-8-sig')
      ok(raw.startswith(b'\xef\xbb\xbf') and '\r\n' in text and text.split('\r\n')[0] == 'Английский\tРусский\tНемецкий\tПримечание', 'file has BOM, CRLF and a header: %r' % text.split('\r\n')[0])
      ok('a piece of cake\tпроще простого\tein Kinderspiel\tидиома: дословно не переводится' in text and text.count('\r\n') == 6, 'starter terms with notes in the file (%d lines)' % text.count('\r\n'))
      ok(page.inner_text('#glossTabInfo') == '· 5', 'tab shows 5 terms: ' + page.inner_text('#glossTabInfo'))

      # --- matched terms: hint, highlight, run info
      page.fill('#src', EN1); page.wait_for_timeout(400)
      ok(page.is_visible('#glossHint') and page.inner_text('#glossHint') == 'Словарь: 2 термина', 'hint: ' + (page.inner_text('#glossHint') if page.is_visible('#glossHint') else 'hidden'))
      ok('decade → десятилетие' in page.get_attribute('#glossHint', 'title'), 'plural "decades" matched by stem')
      page.click('#goBtn'); wait_idle(page)
      ok(page.inner_text('#runInfo').startswith('Учтены термины из словаря: decade → десятилетие; a piece of cake → проще простого'), 'run info: ' + page.inner_text('#runInfo')[:80])
      page.click('#tabGloss'); page.wait_for_timeout(300)
      ok(page.locator('#glossTable tbody tr.hit').count() == 2, 'two matched rows highlighted')
      page.screenshot(path=os.path.join(shots, '1-gloss.png'))

      # --- on/off
      page.uncheck('#glossOn'); page.wait_for_timeout(200)
      ok(not page.is_visible('#glossHint') and page.inner_text('#glossTabInfo') == '· выкл', 'switched off: no hint, tab says выкл')
      page.click('#goBtn'); wait_idle(page)
      ok(not page.is_visible('#runInfo'), 'no glossary terms used when off')
      page.check('#glossOn'); page.wait_for_timeout(200)
      ok(page.is_visible('#glossHint'), 'switched on again')

      # --- edit: add, delete, languages, search (columns: English, Russian, German, note)
      page.click('#glossAdd')
      first = page.locator('#glossTable tbody tr').first
      first.locator('input').nth(0).fill('astronomer')
      first.locator('input').nth(1).fill('астроном')
      first.locator('input').nth(3).fill('из теста')
      ok(wait_file('Мой словарь.tsv', lambda t: 'astronomer\tастроном\t\tиз теста' in t), 'new term autosaved to the file')
      ok(page.inner_text('#glossTabInfo') == '· 6', 'count updated: ' + page.inner_text('#glossTabInfo'))
      page.fill('#src', EN1); page.wait_for_timeout(400)
      ok(page.inner_text('#glossHint') == 'Словарь: 3 термина', 'new term found in the text: ' + page.inner_text('#glossHint'))
      row = page.locator('#glossTable tbody tr').nth(row_index(page, 'user-friendly'))
      row.locator('td.act button').click(); page.wait_for_timeout(100)
      ok(row_index(page, 'user-friendly') >= 0 and 'confirm' in row.locator('td.act button').get_attribute('class'), 'first click on trash only asks')
      row.locator('td.act button').click()
      ok(wait_file('Мой словарь.tsv', lambda t: 'user-friendly' not in t), 'term deleted after the second click')
      page.locator('#glossTable tbody tr').first.locator('input').nth(2).fill('Astronom')
      ok(wait_file('Мой словарь.tsv', lambda t: 'astronomer\tастроном\tAstronom\tиз теста' in t), 'German term saved in its column')
      th = page.locator('#glossTable th[data-lang="de"] button')
      th.click(); page.wait_for_timeout(100)
      ok('confirm' in th.get_attribute('class') and th.inner_text() == '×', 'removing a filled column asks first')
      th.click()
      ok(wait_file('Мой словарь.tsv', lambda t: 'Немецкий' not in t and 'Astronom\t' not in t and 'Kinderspiel' not in t), 'German column removed')
      page.locator('#glossTable th.act button').click(); page.wait_for_selector('#popMenu:not([hidden])')
      page.locator('#popMenu .mi', has_text='Немецкий').click()
      ok(wait_file('Мой словарь.tsv', lambda t: t.split('\r\n')[0] == 'Английский\tРусский\tНемецкий\tПримечание'), 'German column added to the file')
      page.fill('#glossSearch', 'planck'); page.wait_for_timeout(200)
      ok(page.locator('#glossTable tbody tr').count() == 1, 'search filters rows')
      page.fill('#glossSearch', '')

      # --- files: new, copy, switch
      page.click('#glossMenuBtn'); page.wait_for_selector('#popMenu:not([hidden])')
      page.locator('#popMenu .mi', has_text='Новый словарь').click()
      page.fill('#popMenu input', 'Лазеры'); page.keyboard.press('Enter')
      page.wait_for_function("document.querySelector('#glossFile').value === 'Лазеры.tsv'", timeout=5000)
      ok(os.path.exists(os.path.join(GDIR, 'Лазеры.tsv')) and page.is_visible('#glossEmpty'), 'new empty glossary created and opened')
      page.click('#glossMenuBtn'); page.locator('#popMenu .mi', has_text='Новый словарь').click()
      page.fill('#popMenu input', 'Лазеры'); page.keyboard.press('Enter'); page.wait_for_timeout(400)
      ok('уже есть' in page.inner_text('#popMenu'), 'duplicate name refused: ' + page.inner_text('#popMenu .error'))
      page.keyboard.press('Escape')
      page.select_option('#glossFile', 'Мой словарь.tsv'); page.wait_for_timeout(500)
      ok(page.locator('#glossTable tbody tr').count() == 5, 'switched back: %d rows' % page.locator('#glossTable tbody tr').count())
      page.click('#glossMenuBtn'); page.locator('#popMenu .mi', has_text='копию').click()
      ok(page.input_value('#popMenu input') == 'Мой словарь (копия)', 'copy name suggested')
      page.keyboard.press('Enter')
      page.wait_for_function("document.querySelector('#glossFile').value === 'Мой словарь (копия).tsv'", timeout=5000)
      ok('проще простого' in gfile('Мой словарь (копия).tsv'), 'copy has the terms')
      page.select_option('#glossFile', 'Мой словарь.tsv'); page.wait_for_timeout(400)

      # --- import: Excel CSV in Windows-1251 with ";" and quotes, and Excel "Unicode text" (UTF-16)
      csv = 'Английский;Русский;Примечание\r\n"lead";"свинец";"элемент; не путать с «вести»"\r\ndecade;десятилетие;\r\nastronomer;;уже есть\r\n'
      p1 = os.path.join(S, 'import-1251.csv'); open(p1, 'wb').write(csv.encode('cp1251'))
      page.set_input_files('#glossImportFile', p1); page.wait_for_timeout(800)
      t = gfile('Мой словарь.tsv')
      ok('lead\tсвинец\t\tэлемент; не путать с «вести»' in t, 'cp1251 CSV imported with the quoted note (empty German cell)')
      ok(t.count('decade\t') == 1 and t.count('astronomer\t') == 1, 'duplicates are not added twice')
      u16 = 'English\tRussian\tDeutsch\r\nlaser pulse\tлазерный импульс\tLaserpuls\r\n'
      p2 = os.path.join(S, 'import-utf16.txt'); open(p2, 'wb').write(codecs.BOM_UTF16_LE + u16.encode('utf-16-le'))
      page.set_input_files('#glossImportFile', p2); page.wait_for_timeout(800)
      t = gfile('Мой словарь.tsv')
      ok(t.split('\r\n')[0] == 'Английский\tРусский\tНемецкий\tПримечание' and 'laser pulse\tлазерный импульс\tLaserpuls' in t, 'UTF-16 table imported with a German column')

      # --- export (download when the system dialog is not available)
      page.evaluate('window.showSaveFilePicker = undefined')
      with page.expect_download() as dl:
          page.click('#glossMenuBtn'); page.locator('#popMenu .mi', has_text='Экспорт').click()
      d = dl.value; ep = os.path.join(S, 'export.tsv'); d.save_as(ep)
      ok(d.suggested_filename == 'Мой словарь.tsv' and open(ep, 'rb').read().decode('utf-8-sig') == t, 'export downloads the same table')

      # --- the file edited outside (Excel) is reread when the window gets focus
      with open(os.path.join(GDIR, 'Мой словарь.tsv'), 'ab') as f:
          f.write('electron bunch\tэлектронный сгусток\t\t\r\n'.encode('utf-8'))
      time.sleep(0.05)
      page.evaluate("window.dispatchEvent(new Event('focus'))"); page.wait_for_timeout(800)
      ok(row_index(page, 'electron bunch') >= 0, 'outside edit picked up on focus')

      # --- API safety
      ok(http('PUT', '/api/glossary/..%2Fevil.tsv', b'x')[0] == 400, 'path in name refused')
      ok(http('PUT', '/api/glossary/CON', b'x')[0] == 400, 'reserved Windows name refused')
      ok(http('PUT', '/api/glossary/' + urllib.parse.quote('Лазеры.tsv') + '?create=1', b'x')[0] == 409, 'create does not overwrite')
      ok(http('GET', '/api/glossary/' + urllib.parse.quote('нет такого.tsv'))[0] == 404, 'missing file → 404')
      open(os.path.join(GDIR, 'excel.txt'), 'wb').write(codecs.BOM_UTF16_LE + 'English\tRussian\r\nbeam\tпучок\r\n'.encode('utf-16-le'))
      st, body = http('GET', '/api/glossary/excel.txt')
      ok(st == 200 and body.decode('utf-8') == 'English\tRussian\r\nbeam\tпучок\r\n', 'UTF-16 file served as UTF-8')
      req = urllib.request.Request(URL.rstrip('/') + '/api/glossary/x.tsv', data=b'x', method='PUT', headers={'Origin': 'http://evil.example'})
      try: code = urllib.request.urlopen(req, timeout=5).status
      except urllib.error.HTTPError as e: code = e.code
      ok(code == 403, 'foreign page cannot write (%d)' % code)

      # --- «?» on a variant
      page.click('#tabAsk')
      page.fill('#src', EN1); page.wait_for_timeout(300)
      page.click('#goBtn'); wait_idle(page)
      card = page.locator('.card:not(.err)').first
      card.locator('[data-act=ask]').click(); page.wait_for_selector('#popMenu:not([hidden])')
      items = page.locator('#popMenu .mi > span:first-child').all_inner_texts()
      ok(items == ['Почему так?', 'Объяснить', 'Как сказать точнее?', 'Свой вопрос…'], 'translation menu: %s' % items)
      page.screenshot(path=os.path.join(shots, '2-ask-menu.png'))
      variant = card.locator('.card-text').inner_text()
      page.locator('#popMenu .mi', has_text='Почему так?').click()
      page.wait_for_selector('#askLog .msg.bot:not(.pending)', timeout=60000)
      q = page.locator('#askLog .msg.user').last.inner_text()
      ok(q.startswith('Почему текст «Over the past') and 'переведён на русский' in q and 'Термины взяты из словаря пользователя: ' in q and 'decade → десятилетие' in q, 'question text: ' + q[:80])
      ok(variant.strip()[:20] in q, 'question contains the variant')
      card.locator('[data-act=ask]').click(); page.locator('#popMenu .mi', has_text='Свой вопрос').click()
      v = page.input_value('#askInput')
      ok(v.startswith('О варианте «') and v.endswith('): ') and page.evaluate("document.activeElement.id") == 'askInput', 'custom question prefilled and focused')
      page.fill('#askInput', '')
      # edit mode: other wording; comments card has its own menu
      page.select_option('#tgtSel', 'en'); page.wait_for_timeout(200)
      page.locator('#chips .chip', has_text='Замечания').click()
      page.click('#goBtn'); wait_idle(page)
      page.locator('.card:not(.err):not(.comments)').first.locator('[data-act=ask]').click()
      subs = page.locator('#popMenu .mi .sub').all_inner_texts()
      ok('объяснить каждую правку' in subs, 'edit-mode menu: %s' % subs)
      page.keyboard.press('Escape')
      if page.locator('.card.comments:not(.err)').count():
          page.locator('.card.comments').first.locator('[data-act=ask]').click()
          items = page.locator('#popMenu .mi > span:first-child').all_inner_texts()
          ok(items == ['Объяснить подробнее', 'Как исправить?', 'Свой вопрос…'], 'comments menu: %s' % items)
          page.keyboard.press('Escape')
      ok(not page.is_visible('#runInfo'), 'no glossary in same-language editing')
      page.locator('#chips .chip', has_text='Замечания').click()
      page.select_option('#tgtSel', 'auto')

      # --- test report mentions the glossary
      page.click('#testBtn'); page.wait_for_timeout(300)
      ok('Словарь терминов включён' in page.inner_text('#testIntro'), 'test intro mentions the glossary')
      page.click('#runTestBtn')
      page.wait_for_function("document.querySelector('#testProgressText').textContent.startsWith('Готово')", timeout=180000)
      page.wait_for_function("document.querySelector('#testSummary').textContent.includes('Отчёт сохранён')", timeout=15000)
      rep = sorted(f for f in os.listdir(os.path.join(ROOT, 'data/reports')) if f.endswith('.md'))
      md = open(os.path.join(ROOT, 'data/reports', rep[-1]), encoding='utf-8').read()
      ok('- Словарь терминов: Мой словарь.tsv' in md and any(l.startswith('- Термины из словаря:') and 'decade → десятилетие' in l for l in md.splitlines()), 'report lists the glossary and terms')
      page.click('#closeTestBtn')

      page.click('#tabGloss'); page.emulate_media(color_scheme='dark'); page.wait_for_timeout(200)
      page.screenshot(path=os.path.join(shots, '3-gloss-dark.png'))
      ok(not errors, 'no console errors: %s' % errors[:3])
      b.close()
finally:
  print(chr(10).join(l for l in log if l.startswith('FAIL')) or 'ALL OK', len(log), 'checks')
