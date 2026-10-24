# Fallback start without the launcher (start.sh: llama-server serves the UI itself).
# Usage: basic_mode.py <ui_url>   (start.sh running with a model named like Gemma 4 E2B)
import sys
from playwright.sync_api import sync_playwright
URL = sys.argv[1]
EN1 = 'Over the past two decades, finding new planets has become a piece of cake for astronomers.'
res = []
def ok(c, m): res.append(('OK  ' if c else 'FAIL') + ' ' + m)
bodies = []
def spy(route):
    import json
    bodies.append(json.loads(route.request.post_data)); route.continue_()
with sync_playwright() as p:
    b = p.chromium.launch(); page = b.new_page(viewport={'width': 1180, 'height': 780})
    page.add_init_script("try { sessionStorage.setItem('tdoc.window', '1'); sessionStorage.setItem('tdoc.welcome', 'done') } catch (e) {}")   # an "old" window: start languages are tested in e2e_v061.py, the welcome window in e2e_v07.py
    # the checks below are in Russian; a browser without settings shows English since 1.0 (checked first)
    page.add_init_script("try { if (sessionStorage.getItem('tdoc.ruSet') === null && localStorage.getItem('tdoc.settings') === null && location.search.indexOf('fresh') < 0) { localStorage.setItem('tdoc.settings', JSON.stringify({ ui_language: 'ru' })); sessionStorage.setItem('tdoc.ruSet', '1') } } catch (e) {}")
    errs = []; page.on('pageerror', lambda e: errs.append(str(e)))
    page.route('**/v1/chat/completions', spy)
    page.goto(URL + ('&' if '?' in URL else '?') + 'fresh=1'); page.wait_for_selector('body[data-model="ready"]', timeout=30000)
    ok(page.evaluate('document.documentElement.lang') == 'en' and page.inner_text('#goLabel') == 'Translate', 'a browser without settings: English (1.0)')
    page.goto(URL); page.wait_for_selector('body[data-model="ready"]', timeout=30000); page.wait_for_timeout(800)
    ok(page.evaluate('document.documentElement.lang') == 'ru', 'Russian from the browser memory')
    ok('gemma-4-E2B_q4_0-it.gguf' in page.inner_text('#engineInfo'), 'engine info names the model file: ' + page.inner_text('#engineInfo'))
    ok(page.evaluate('basicFamily') == 'chat' and page.evaluate('basicCtx') == 4096, 'family and context from /props')
    ok(page.is_hidden('#unloadBtn') and page.is_hidden('#modelBtn'), 'no model menu and no unload button')
    ok(page.is_hidden('#quitBtn') and page.is_hidden('#modelBanner'), 'no Exit button (the window cannot stop start.sh) and no banner')
    ok(page.is_hidden('#srcSpeak') and page.is_hidden('#ownSpeak'), 'no reading aloud without the launcher')
    page.select_option('#srcSel', 'en'); page.select_option('#tgtSel', 'de'); page.click('#swapBtn')
    ok(page.input_value('#srcSel') == 'de' and page.input_value('#tgtSel') == 'en', '↔ works')
    page.select_option('#srcSel', 'auto'); page.select_option('#tgtSel', 'auto')
    page.fill('#src', 'Wir stellen eine geschlossene Lösung vor.'); page.wait_for_timeout(400)
    page.click('#goBtn'); page.wait_for_selector('#goBtn:not([hidden])', timeout=30000)
    ok(bodies[0]['messages'][0]['content'].startswith('Translate the following German text into Russian.'), 'chat-family prompt')
    page.fill('#askInput', 'Привет'); page.click('#askSend')
    page.wait_for_selector('#askLog .msg.bot:not(.pending)', timeout=30000)
    ok([m['role'] for m in bodies[-1]['messages']] == ['system', 'user'], 'chat works')
    # saved translations: one list in the browser (no files without the launcher)
    page.locator('.card').first.locator('button[data-act="save"]').click(); page.wait_for_timeout(300)
    ok(page.inner_text('#savedCount') == '(1)' and page.inner_text('#toast') == 'Сохранено', 'saved in the browser')
    page.click('#savedBtn'); page.wait_for_selector('#savedList .item', timeout=5000)
    ok(page.is_disabled('#savedFile') and page.inner_text('#savedFile') == 'в этом браузере' and 'только в этом браузере' in page.inner_text('#savedNote'), 'no files: the list lives in the browser')
    page.click('#savedMenuBtn')
    ok(page.locator('#popMenu .mi > span:first-child').all_inner_texts() == ['Импорт из файла…', 'Экспорт в таблицу (.tsv)…', 'Экспорт в текст (.txt)…'], 'saved menu: import and export only')
    page.keyboard.press('Escape')
    page.fill('#src', ''); page.locator('#savedList .item button.mini').click()
    ok(page.input_value('#src') == 'Wir stellen eine geschlossene Lösung vor.' and page.input_value('#srcSel') == 'de', '«В поле» works in the browser')
    page.select_option('#srcSel', 'auto'); page.select_option('#tgtSel', 'auto')
    page.click('#tabGloss'); page.wait_for_timeout(300)
    ok(page.locator('#glossTable tbody tr').count() == 5 and page.is_disabled('#glossFile'), 'browser glossary with starter terms')
    page.fill('#src', EN1); page.wait_for_timeout(400)
    ok(page.inner_text('#glossHint') == 'Словарь: 2 термина', 'glossary hint')
    page.click('#glossAdd'); r = page.locator('#glossTable tbody tr').first
    r.locator('input').nth(0).fill('laser'); r.locator('input').nth(1).fill('лазер'); page.wait_for_timeout(900)
    page.reload(); page.wait_for_selector('body[data-model="ready"]', timeout=30000); page.wait_for_timeout(800)
    ok(page.locator('#glossTable tbody tr').count() == 6, 'glossary kept in the browser after reload')
    page.click('#glossMenuBtn')
    ok(page.locator('#popMenu .mi > span:first-child').all_inner_texts() == ['Импорт из файла…', 'Экспорт в файл…'], 'menu has only import and export')
    page.keyboard.press('Escape')
    # settings without the launcher: kept in this browser, applied before the page is drawn
    page.click('#settingsBtn'); page.wait_for_selector('#settingsView:not([hidden])')
    ok('в этом браузере' in page.inner_text('#settingsNote') and page.is_hidden('#quitRow'), 'settings kept in this browser; no Exit')
    page.click('#themeSeg button[data-v="dark"]'); page.click('#fontSeg button[data-v="115"]')
    page.fill('#src', 'Der Laser ist stark.')
    with page.expect_navigation(timeout=15000):
        page.select_option('#uiLangSel', 'en')
    page.wait_for_selector('body[data-model="ready"]', timeout=30000); page.wait_for_timeout(500)
    attrs = page.evaluate('[document.documentElement.lang, document.documentElement.dataset.theme, document.documentElement.dataset.font]')
    ok(attrs == ['en', 'dark', '115'] and page.inner_text('#goLabel') == 'Translate' and page.input_value('#src') == 'Der Laser ist stark.', 'English, dark theme and large font from the browser memory: %s' % attrs)
    ok(page.is_visible('#settingsView') and 'in this browser' in page.inner_text('#settingsNote'), 'settings panel back, note in English')
    with page.expect_navigation(timeout=15000):
        page.select_option('#uiLangSel', 'ru')
    page.wait_for_selector('body[data-model="ready"]', timeout=30000)
    page.click('#themeSeg button[data-v="light"]'); page.click('#fontSeg button[data-v="100"]')
    ok(page.evaluate("JSON.parse(localStorage.getItem('tdoc.settings'))") == {'ui_language': 'ru', 'theme': 'light', 'font_scale': 100}, 'settings in localStorage: %s' % page.evaluate("localStorage.getItem('tdoc.settings')"))
    ok(not errs, 'no page errors %s' % errs[:2])
    b.close()
print('\n'.join(res))
print('FAILS:', sum(1 for x in res if x.startswith('FAIL')), 'of', len(res))
