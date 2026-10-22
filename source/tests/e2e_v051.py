# End-to-end test of the v0.5.1 features: files of saved translations (data/saved), the move of the old
# data/saved.tsv, search, «В поле», import and export (TSV and TXT), a file edited outside, the program's icon.
# Launcher + engine with a stand-in model + UI in Chromium; translations are canned replies (fixtures written
# for the test, not model output).
# Usage: e2e_v051.py <work> <ui_url> <root>   (a launcher in a fresh folder, past the first run, started with
# the 0.5 file <root>/data/saved.tsv in place — see run_all.sh)
import sys, json, os, csv, io, codecs
from datetime import datetime
from playwright.sync_api import sync_playwright
S, URL, ROOT = sys.argv[1], sys.argv[2], sys.argv[3]
shots = os.path.join(S, 'shots', 'v051'); os.makedirs(shots, exist_ok=True)
SAVED = os.path.join(ROOT, 'data', 'saved')
DEF = 'Сохранённые.tsv'
log = []
def ok(cond, msg):
    log.append(('OK  ' if cond else 'FAIL') + ' ' + msg); print(log[-1], flush=True)
def disk(name):
    p = os.path.join(SAVED, name)
    return open(p, 'rb').read().decode('utf-8-sig') if os.path.exists(p) else None
def rows(name):
    t = disk(name)   # cells read the way spreadsheets read them ("…" with "" inside)
    return [r for r in csv.reader(io.StringIO(t, newline=''), delimiter='\t')][1:] if t is not None else None
def minute(iso):
    return datetime.fromisoformat(iso.replace('Z', '+00:00')).timestamp() // 60
def toast(page):
    return page.inner_text('#toast')
def items(page):
    return page.locator('#savedList .item')

# different texts for the styles: equal variants would be merged into one card
REPLIES = ['Лазерный импульс сжат.', 'Лазерный импульс был сжат.', 'Импульс лазера сжат.']
served = []
def reply(route):
    words = REPLIES[len(served) % len(REPLIES)].split(' '); served.append(1)
    body = ''.join('data: ' + json.dumps({'choices': [{'delta': {'content': (w if i == 0 else ' ' + w)}}]}) + '\n\n' for i, w in enumerate(words))
    body += 'data: ' + json.dumps({'choices': [{'delta': {}, 'finish_reason': 'stop'}], 'timings': {'predicted_n': 5, 'predicted_per_second': 9.5}}) + '\n\ndata: [DONE]\n\n'
    route.fulfill(status=200, headers={'Content-Type': 'text/event-stream'}, body=body)

try:
  with sync_playwright() as p:
      b = p.chromium.launch()
      ctx = b.new_context(viewport={'width': 1180, 'height': 780}, locale='ru-RU', color_scheme='light', accept_downloads=True)
      # the start languages of a new window (0.6.1) are tested in e2e_v061.py; here the window is an "old" one
      ctx.add_init_script("try { sessionStorage.setItem('tdoc.window', '1'); sessionStorage.setItem('tdoc.welcome', 'done') } catch (e) {}")
      page = ctx.new_page()
      errors = []
      # 409 — the expected answer to a taken file name
      page.on('console', lambda m: errors.append(m.text) if m.type == 'error' and 'status of 409' not in m.text else None)
      page.on('pageerror', lambda e: errors.append(str(e)))
      page.route('**/v1/chat/completions', reply)
      opened = []
      def open_route(route):
          opened.append(json.loads(route.request.post_data or '{}')); route.fulfill(status=200, content_type='application/json', body='{"ok":true}')
      page.route('**/api/open', open_route)
      page.goto(URL); page.wait_for_selector('body[data-model="ready"]', timeout=60000)
      page.evaluate('() => { window.showSaveFilePicker = undefined; }')   # export: a download instead of the system dialog

      # --- icon
      d = page.get_attribute('#logo svg path', 'd') or ''
      ok(d.startswith('M67 88.5') and page.evaluate("getComputedStyle(document.querySelector('#logo')).color") == 'rgb(117, 5, 117)', 'icon in the header: purple T with arrows')
      fav = page.evaluate("(document.querySelector('link[rel=icon]') || {}).href || ''")
      ok(fav.startswith('data:image/svg+xml,') and 'M67%2088.5' in fav, 'the same icon is the window icon (favicon)')

      # --- the 0.5 file moved into data/saved
      ok(not os.path.exists(os.path.join(ROOT, 'data', 'saved.tsv')) and disk(DEF) is not None, 'data/saved.tsv moved to data/saved/' + DEF)
      ok(len(rows(DEF)) == 3 and rows(DEF)[0][0] == 'm1', 'the moved file keeps its 3 rows')
      ok(page.inner_text('#savedCount') == '(3)', 'header counts the rows of the current file: ' + page.inner_text('#savedCount'))

      # --- the panel
      page.click('#savedBtn'); page.wait_for_selector('#savedList .item', timeout=5000)
      ok(page.input_value('#savedFile') == DEF and page.locator('#savedFile option').all_inner_texts() == ['Сохранённые'], 'file list: ' + str(page.locator('#savedFile option').all_inner_texts()))
      ok(items(page).count() == 3 and page.inner_text('#savedInfo') == '3 записи', 'three rows, newest first: ' + page.inner_text('#savedInfo'))
      ok(items(page).first.locator('.src').inner_text() == 'Der Laser ist stark.', 'newest first')
      ok(page.inner_text('#savedNote').endswith(os.path.join('data', 'saved', DEF)), 'path of the file: ' + page.inner_text('#savedNote'))
      ok('правка (русский)' in items(page).nth(1).locator('.meta').inner_text(), 'editing direction shown')
      page.screenshot(path=os.path.join(shots, '1-saved.png'))

      # --- search
      page.fill('#savedSearch', 'лазер')
      ok(items(page).count() == 1 and page.inner_text('#savedInfo') == 'Найдено: 1 из 3', 'search «лазер»: ' + page.inner_text('#savedInfo'))
      ok(page.locator('#savedList .item mark').first.inner_text() == 'Лазер', 'found words are highlighted')
      page.fill('#savedSearch', 'замкнутой  решение')
      ok(items(page).count() == 1 and 'closed-form' in items(page).first.inner_text(), 'all words of the query, any order')
      page.fill('#savedSearch', 'еще')
      ok(items(page).count() == 1 and 'ещё' in items(page).first.inner_text(), 'ё and е are the same in search')
      page.fill('#savedSearch', 'нет такого слова')
      ok(items(page).count() == 0 and 'Ничего не найдено' in page.inner_text('#savedList'), 'nothing found')
      page.fill('#savedSearch', '')
      ok(items(page).count() == 3, 'empty search shows everything')

      # --- «В поле»
      page.fill('#src', ''); page.select_option('#srcSel', 'auto'); page.select_option('#tgtSel', 'auto')
      items(page).first.locator('button.mini').click()
      ok(page.input_value('#src') == 'Der Laser ist stark.' and page.input_value('#srcSel') == 'de' and page.input_value('#tgtSel') == 'ru', '«В поле»: text and languages of the row')
      ok(page.is_hidden('#savedView') and page.is_visible('#resultsView') and 'Перевести' in toast(page), 'back to the results, hint: ' + toast(page))
      page.click('#savedBtn'); page.wait_for_selector('#savedList .item')
      btn = items(page).nth(2).locator('button.mini')
      btn.click()
      ok(btn.inner_text() == 'Заменить текст?' and page.input_value('#src') == 'Der Laser ist stark.', 'another text in the field: asks first')
      page.keyboard.press('Escape')
      ok(btn.inner_text() == 'В поле', 'Esc cancels')
      btn.click(); btn.click()
      ok(page.input_value('#src') == 'We present a closed-form solution.' and page.input_value('#srcSel') == 'en', 'second press replaces the text')

      # --- a variant saved into the current file
      page.fill('#src', 'The laser pulse is compressed.'); page.wait_for_timeout(300)
      page.click('#goBtn'); page.wait_for_selector('#goBtn:not([hidden])', timeout=30000)
      page.wait_for_selector('.card:not(.pending)', timeout=10000)
      ok(page.locator('.card').count() == 3, 'three variants: %d' % page.locator('.card').count())
      save1 = page.locator('.card').first.locator('button[data-act="save"]')
      save1.click(); page.wait_for_timeout(500)
      ok('Сохранено в «Сохранённые»' in toast(page) and page.inner_text('#savedCount') == '(4)', 'saved into the current file: ' + toast(page))
      ok(len(rows(DEF)) == 4 and rows(DEF)[3][5] == 'The laser pulse is compressed.' and rows(DEF)[3][6] == 'Лазерный импульс сжат.', 'row written to the file')

      # --- a new file
      page.click('#savedBtn'); page.wait_for_selector('#savedList .item')
      page.click('#savedMenuBtn')
      labels = page.locator('#popMenu .mi > span:first-child').all_inner_texts()
      ok(labels == ['Новый файл…', 'Сохранить копию как…', 'Импорт из файла…', 'Экспорт в таблицу (.tsv)…', 'Экспорт в текст (.txt)…', 'Открыть папку'], 'menu: ' + str(labels))
      page.locator('#popMenu .mi', has_text='Новый файл').click()
      page.fill('#popMenu input', 'Статья 1'); page.keyboard.press('Enter'); page.wait_for_timeout(600)
      ok(page.input_value('#savedFile') == 'Статья 1.tsv' and disk('Статья 1.tsv') is not None and rows('Статья 1.tsv') == [], 'new empty file created and chosen')
      ok(items(page).count() == 0 and 'пока ничего нет' in page.inner_text('#savedList') and page.inner_text('#savedCount') == '', 'empty file: hint, no count')
      page.click('#closeSavedBtn')
      save2 = page.locator('.card').nth(1).locator('button[data-act="save"]')
      save2.click(); page.wait_for_timeout(500)
      ok('«Статья 1»' in toast(page) and len(rows('Статья 1.tsv')) == 1 and len(rows(DEF)) == 4, 'the next save goes to the new file')
      # un-saving the first card removes its row from the file it was saved to, not from the current one
      save1.click(); page.wait_for_timeout(500)
      ok(len(rows(DEF)) == 3 and len(rows('Статья 1.tsv')) == 1, 'un-saving removes the row from its own file')
      ok(page.evaluate("JSON.parse(localStorage.getItem('tdoc.savedFile'))") == 'Статья 1.tsv', 'the chosen file is remembered')

      # --- copy, and a taken name
      page.click('#savedBtn'); page.wait_for_selector('#savedList .item')
      page.click('#savedMenuBtn'); page.locator('#popMenu .mi', has_text='Сохранить копию').click()
      ok(page.input_value('#popMenu input') == 'Статья 1 (копия)', 'copy: suggested name')
      page.keyboard.press('Enter'); page.wait_for_timeout(600)
      ok(page.input_value('#savedFile') == 'Статья 1 (копия).tsv' and len(rows('Статья 1 (копия).tsv')) == 1, 'copy created with the rows')
      page.click('#savedMenuBtn'); page.locator('#popMenu .mi', has_text='Новый файл').click()
      page.fill('#popMenu input', 'Статья 1'); page.keyboard.press('Enter'); page.wait_for_timeout(500)
      ok('уже есть' in page.inner_text('#popMenu'), 'a taken name is refused: ' + page.inner_text('#popMenu .error'))
      page.keyboard.press('Escape')
      page.select_option('#savedFile', 'Статья 1.tsv'); page.wait_for_timeout(400)
      ok(items(page).count() == 1 and page.inner_text('#savedCount') == '(1)', 'switching files')

      # --- import: this program's table (one row is already in the file), a CSV with a header, a plain list
      imp1 = os.path.join(S, 'saved-import.tsv')
      open(imp1, 'w', encoding='utf-8-sig', newline='').write(
          'id\tвремя\tс\tна\tстиль\tисходный текст\tперевод\tконтекст\r\n'
          'x1\t2026-10-01T10:00:00+02:00\ten\tru\tНаучный\tThe laser pulse is compressed.\tЛазерный импульс был сжат.\t\r\n'
          'x2\t2026-10-01T10:01:00+02:00\ten\tde\tНейтральный\tA "quoted" word.\tEin Wort.\t\r\n'
          'x3\t\t??\t\t\tПрямой перевод.\tDirect translation.\tфизика\r\n')
      page.set_input_files('#savedImportFile', imp1); page.wait_for_timeout(800)
      ok('добавлено 2, повторов пропущено 1' in toast(page), 'import of a saved table: ' + toast(page))
      r = rows('Статья 1.tsv')
      ok(len(r) == 3 and r[1][2:4] == ['en', 'de'] and r[1][5] == 'A "quoted" word.' and r[2][2:4] == ['ru', 'en'] and r[2][7] == 'физика', 'imported rows; unknown languages taken from the text')
      imp2 = os.path.join(S, 'saved-import.csv')
      open(imp2, 'w', encoding='cp1251', newline='').write('English;Русский\r\nclosed form;замкнутая форма\r\n"field, strong";сильное поле\r\n')
      page.set_input_files('#savedImportFile', imp2); page.wait_for_timeout(800)
      r = rows('Статья 1.tsv')
      ok('добавлено 2' in toast(page) and r[3][2:4] == ['en', 'ru'] and r[4][5] == 'field, strong' and r[4][4] == 'импорт', 'CSV in Windows-1251 with a header of languages')
      imp3 = os.path.join(S, 'saved-list.txt')
      open(imp3, 'w', encoding='utf-8', newline='').write('Die Wellenfunktion ist normiert.\nDer Impuls, die Energie und der Drehimpuls bleiben erhalten.\n')
      page.set_input_files('#savedImportFile', imp3); page.wait_for_timeout(800)
      r = rows('Статья 1.tsv')
      ok(len(r) == 7 and r[6][5].startswith('Der Impuls, die Energie') and r[6][6] == '' and r[6][2:4] == ['de', 'ru'], 'plain TXT list: one text per line (commas stay), no translation')
      ok('без перевода' in items(page).first.inner_text(), 'a row without translation is marked')
      u16 = os.path.join(S, 'saved-utf16.txt')
      open(u16, 'wb').write(codecs.BOM_UTF16_LE + 'Deutsch\tРусский\r\nder Laser\tлазер\r\n'.encode('utf-16-le'))
      page.set_input_files('#savedImportFile', u16); page.wait_for_timeout(800)
      r = rows('Статья 1.tsv')
      ok(len(r) == 8 and r[7][2:4] == ['de', 'ru'] and r[7][5:7] == ['der Laser', 'лазер'], 'UTF-16 table from Excel')

      # --- export: the table is the file itself; the text is readable and imports back
      with page.expect_download() as dl:
          page.click('#savedMenuBtn'); page.locator('#popMenu .mi', has_text='Экспорт в таблицу').click()
      ep = os.path.join(S, 'saved-export.tsv'); dl.value.save_as(ep)
      ok(dl.value.suggested_filename == 'Статья 1.tsv' and open(ep, 'rb').read() == open(os.path.join(SAVED, 'Статья 1.tsv'), 'rb').read(), 'TSV export equals the file byte for byte')
      with page.expect_download() as dl:
          page.click('#savedMenuBtn'); page.locator('#popMenu .mi', has_text='Экспорт в текст').click()
      tp = os.path.join(S, 'saved-export.txt'); dl.value.save_as(tp)
      t = open(tp, 'rb').read().decode('utf-8-sig')
      ok(dl.value.suggested_filename == 'Статья 1.txt' and t.startswith('Ttranslator · сохранённые переводы · «Статья 1»') and '№ 1 · английский → русский · Научный' in t, 'TXT export: title and numbered rows')
      ok('\r\nA "quoted" word.\r\n→ Ein Wort.\r\n' in t and 'Контекст: физика' in t, 'TXT export: text, arrow and translation, context')
      page.click('#savedMenuBtn'); page.locator('#popMenu .mi', has_text='Новый файл').click()
      page.fill('#popMenu input', 'Из текста'); page.keyboard.press('Enter'); page.wait_for_timeout(600)
      page.set_input_files('#savedImportFile', tp); page.wait_for_timeout(900)
      a, c = rows('Статья 1.tsv'), rows('Из текста.tsv')
      ok(c is not None and [x[2:4] + x[5:8] for x in c] == [x[2:4] + x[5:8] for x in a], 'TXT export imports back: same texts, languages and context')
      ok(c is not None and [x[4] for x in c] == [x[4] for x in a] and [minute(x[1]) for x in c] == [minute(x[1]) for x in a], 'style and time survive the round trip')

      # --- the file edited outside (spreadsheet, UTF-16, a row without id) is read again on focus
      page.select_option('#savedFile', 'Статья 1.tsv'); page.wait_for_timeout(400)
      txt = disk('Статья 1.tsv') + '\t\ten\tru\t\tAdded in Excel.\tДобавлено в Excel.\t\r\n'
      open(os.path.join(SAVED, 'Статья 1.tsv'), 'wb').write(codecs.BOM_UTF16_LE + txt.encode('utf-16-le'))
      page.evaluate("window.dispatchEvent(new Event('focus'))"); page.wait_for_timeout(700)
      ok(items(page).first.locator('.src').inner_text() == 'Added in Excel.' and page.inner_text('#savedCount') == '(9)', 'file edited outside is read again')
      items(page).first.locator('button[title="Удалить"]').click(); page.wait_for_timeout(600)
      r = rows('Статья 1.tsv')
      ok(len(r) == 8 and not any('Added in Excel.' in x for x in map('\t'.join, r)) and disk('Статья 1.tsv').startswith('id\t'), 'a row without id is deleted; the file is UTF-8 again')

      # --- folder
      page.click('#savedMenuBtn'); page.locator('#popMenu .mi', has_text='Открыть папку').click(); page.wait_for_timeout(300)
      ok(opened and opened[-1].get('what') == 'saved', 'Открыть папку asks for data/saved')
      page.screenshot(path=os.path.join(shots, '2-saved-file.png'))

      # --- after a reload: the same file is chosen
      page.reload(); page.wait_for_selector('body[data-model="ready"]', timeout=30000); page.wait_for_timeout(500)
      ok(page.inner_text('#savedCount') == '(8)', 'after reload the chosen file is counted: ' + page.inner_text('#savedCount'))
      os.remove(os.path.join(SAVED, 'Статья 1.tsv'))
      page.click('#savedBtn'); page.wait_for_timeout(700)
      ok(page.input_value('#savedFile') == DEF, 'the chosen file was deleted outside: back to the main one')

      ok(not errors, 'no console errors: %s' % errors[:3])
      b.close()
except Exception as e:
    import traceback; traceback.print_exc()
    ok(False, 'exception: %s' % e)

fails = [l for l in log if l.startswith('FAIL')]
print('ALL OK %d checks' % len(log) if not fails else 'FAILS: %d of %d' % (len(fails), len(log)))
