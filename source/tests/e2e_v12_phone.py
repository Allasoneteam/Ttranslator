# End-to-end test for 1.2: the interface on a phone screen (Android) — and the computer's as before.
#   1) a phone (412 x 915, as the Android emulator of the CI and many phones), with the window functions of the Android
#      app (ttwPlatform 'android'): nothing wider than the screen; in the header the name, the model and the menu «⋮»
#      (the other buttons are in it), the languages on a second line; «Перевести» across the width; no keyboard hints;
#      the variants come under the form; the panes (Сохранённые, Тест, Настройки, Справка, О программе) take the place
#      of the work window and «Назад» of the phone (ttwBack) closes them, then the model menu, then nothing is left
#      (false: the app goes to the background); no «Открыть папку» in the menus; no window type in the settings and
#      in the welcome window; «на вашем устройстве» in the welcome window; text from another app (ttwSetText) comes
#      into the field and is translated at once («Авто» → «Авто»);
#   2) the same phone screen in a browser tab (no Android app): the folder items and the keyboard hint stay;
#   3) a computer (1280 x 800): all the header buttons are there, «⋮» is not, two columns as before.
# Usage: e2e_v12_phone.py <work> <ui_url>   (a launcher with a ready stand-in model)
import json, os, sys, time
from playwright.sync_api import sync_playwright
S, URL = sys.argv[1], sys.argv[2]
shots = os.path.join(S, 'shots', 'v12'); os.makedirs(shots, exist_ok=True)
res = []
def ok(c, m): res.append(('OK  ' if c else 'FAIL') + ' ' + m); print(res[-1], flush=True)

PHONE = dict(viewport={'width': 412, 'height': 915}, device_scale_factor=2.625, is_mobile=True, has_touch=True,
             user_agent='Mozilla/5.0 (Linux; Android 16; Phone) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0 Mobile Safari/537.36 wv')
ANDROID = """window.ttwPlatform = 'android';
window.ttwSaveFile = (n) => Promise.resolve({path: n}); window.ttwOpenExternal = () => Promise.resolve({});
window.ttwClose = () => Promise.resolve({});"""
OLD_WINDOW = "sessionStorage.setItem('tdoc.window', '1'); sessionStorage.setItem('tdoc.welcome', 'done');"
WIDE = """() => [...document.querySelectorAll('body *')].filter(e => e.getClientRects().length
  && e.getBoundingClientRect().right > document.documentElement.clientWidth + 0.5 && !e.closest('[hidden]'))
  .map(e => e.id || e.tagName.toLowerCase()).slice(0, 8)"""

def open_page(p, ctx_args, init):
    b = p.chromium.launch()
    ctx = b.new_context(**ctx_args)
    if init:
        ctx.add_init_script(init)
    ctx.add_init_script(OLD_WINDOW)
    page = ctx.new_page()
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.goto(URL)
    page.wait_for_selector('body[data-model="ready"]', timeout=60000)
    time.sleep(0.6)
    return b, page, errors

def menu_items(page):
    return page.eval_on_selector_all('#popMenu .mi', 'es => es.map(e => e.innerText.split("\\n")[0])')

with sync_playwright() as p:
    # ---------------------------------------------------------------- 1) the phone, in the Android app
    b, page, errors = open_page(p, PHONE, ANDROID)
    ok(page.evaluate("document.documentElement.classList.contains('android')"), 'Android: the page knows it (html.android)')
    # the welcome window (after the first-start downloads it does not open by itself: «Окно приветствия» in the settings)
    page.click('#moreBtn'); time.sleep(0.2)
    page.locator('#popMenu .mi', has_text='Настройки').first.click(); time.sleep(0.4)
    page.click('#openWelcomeBtn'); time.sleep(0.4)
    ok(page.is_visible('#welcomeView'), 'the welcome window opens')
    intro = page.inner_text('#welcomeIntro')
    ok('устройстве' in intro, 'welcome: «на вашем устройстве», not «компьютере»: %r' % intro)
    ok(not page.is_visible('#welcomeModeRow'), 'welcome: no window type on Android')
    ok(page.evaluate('window.ttwBack()') is True and not page.is_visible('#welcomeView'), '«Назад» of the phone closes the welcome window')
    while page.evaluate('window.ttwBack()'):
        time.sleep(0.2)
    page.screenshot(path=os.path.join(shots, 'phone-main.png'))
    m = page.evaluate("""() => ({w: innerWidth, sw: document.documentElement.scrollWidth,
      shown: [...document.querySelectorAll('header.top button')].filter(e => e.getClientRects().length).map(e => e.id),
      go: document.querySelector('#goBtn').getBoundingClientRect().width,
      dir: document.querySelector('.dir').getBoundingClientRect().top > document.querySelector('#modelBtn').getBoundingClientRect().bottom - 1,
      kbd: getComputedStyle(document.querySelector('#goBtn .kbd')).display})""")
    ok(m['w'] == 412 and m['sw'] == 412, 'phone: the page is as wide as the screen (%s of %s)' % (m['sw'], m['w']))
    ok(page.evaluate(WIDE) == [], 'phone: nothing wider than the screen: %s' % page.evaluate(WIDE))
    ok(set(m['shown']) <= {'modelBtn', 'moreBtn', 'swapBtn'} and 'moreBtn' in m['shown'] and 'modelBtn' in m['shown'],
       'phone header: the model and «⋮» (the rest is in the menu): %s' % m['shown'])
    ok(m['dir'], 'phone header: the languages on a second line')
    ok(m['go'] > 300, '«Перевести» across the width (%d px)' % m['go'])
    ok(m['kbd'] == 'none', 'Android: no keyboard hint (Ctrl+Enter) on the button')
    page.click('#moreBtn'); time.sleep(0.3)
    items = menu_items(page)
    want = ['Сохранённые', 'Тест', 'Настройки', 'Справка', 'О программе']
    ok(all(w in items for w in want) and 'Выход' in items, 'menu «⋮»: %s' % items)
    page.screenshot(path=os.path.join(shots, 'phone-menu.png'))
    ok(page.evaluate('window.ttwBack()') is True and not page.is_visible('#popMenu'), '«Назад» closes the menu')
    for label, pane in (('Сохранённые', 'saved'), ('Тест', 'test'), ('Настройки', 'settings'), ('Справка', 'help'), ('О программе', 'about')):
        page.click('#moreBtn'); time.sleep(0.2)
        page.locator('#popMenu .mi', has_text=label).first.click(); time.sleep(0.4)
        st = page.evaluate("""(k) => ({pane: !document.querySelector('#' + k + 'View').hidden, form: !!document.querySelector('#src').getClientRects().length,
          top: Math.round(document.querySelector('#' + k + 'View').getBoundingClientRect().top), sw: document.documentElement.scrollWidth})""", pane)
        ok(st['pane'] and not st['form'] and st['top'] < 200 and st['sw'] == 412,
           '«%s» from the menu: the pane in place of the work window, at the top, as wide as the screen: %s' % (label, st))
        if pane == 'help':
            h = page.eval_on_selector_all('#helpBody h3', 'es => es.map(e => e.textContent)')
            ok(h[:1] == ['Android: телефон и планшет'] and 'Перевод' in h and 'Обновление и удаление' not in h and 'Файлы программы' not in h,
               'Справка on Android: its own section first; no program folder and no updating of a computer: %s' % h)
        if pane == 'settings':
            ok(not page.is_visible('#modeRow'), 'settings on Android: no window type')
            page.screenshot(path=os.path.join(shots, 'phone-settings.png'))
        if pane == 'saved':
            page.click('#savedMenuBtn'); time.sleep(0.3)
            si = menu_items(page)
            ok('Открыть папку' not in si and any(x.startswith('Экспорт') for x in si), 'Сохранённые on Android: export, no «Открыть папку»: %s' % si)
            page.evaluate('window.ttwBack()')
        ok(page.evaluate('window.ttwBack()') is True and not page.is_visible('#' + pane + 'View')
           and page.evaluate("!document.querySelector('#resultsView').hidden && !!document.querySelector('#src').getClientRects().length"),
           '«Назад» of the phone: back from «%s» to the work window' % label)
    # the glossary menu: no folder on Android
    page.click('#tabGloss'); time.sleep(0.3)
    page.click('#glossMenuBtn'); time.sleep(0.3)
    gi = menu_items(page)
    ok('Открыть папку словарей' not in gi and 'Экспорт в файл…' in gi, 'glossary on Android: export, no folder: %s' % gi)
    page.evaluate('window.ttwBack()')
    page.click('#tabAsk')
    # a translation: the variants under the form, the page scrolled to them
    page.fill('#src', 'Доброе утро! Сегодня хорошая погода.')
    time.sleep(0.4)
    page.click('#goBtn')
    page.wait_for_function("document.querySelectorAll('.card').length > 0 && !document.querySelector('#goBtn').disabled", timeout=120000)
    time.sleep(0.8)
    pos = page.evaluate("""() => ({go: document.querySelector('#goBtn').getBoundingClientRect().bottom,
      card: document.querySelector('.card').getBoundingClientRect().top, ask: document.querySelector('#askBox').getBoundingClientRect().top,
      scrolled: document.scrollingElement.scrollTop, hdr: document.querySelector('header.top').getBoundingClientRect().bottom,
      sw: document.documentElement.scrollWidth})""")
    ok(pos['go'] < pos['card'] < pos['ask'], 'phone: the variants come after «Перевести» and before «Спросить модель»: %s' % pos)
    ok(pos['scrolled'] > 0 and pos['hdr'] <= pos['go'] - 36 and pos['card'] < 915,
       'phone: the page scrolled to «Перевести» (just under the header), the variants under it: %s' % pos)
    ok(pos['sw'] == 412 and page.evaluate(WIDE) == [], 'phone: the variant cards are as wide as the screen: %s' % page.evaluate(WIDE))
    page.screenshot(path=os.path.join(shots, 'phone-variants.png'))
    # the ask window on the phone (1.4): its header with the language of the voice conversation is one line, 🎤 in the row
    page.locator('#askBox').scroll_into_view_if_needed(); time.sleep(0.3)
    hd = page.evaluate("""() => { const h = document.querySelector('.ask-head').getBoundingClientRect(), s = document.querySelector('#askLang').getBoundingClientRect(),
      m = document.querySelector('#askMic').getBoundingClientRect(), i = document.querySelector('#askInput').getBoundingClientRect();
      return { h: Math.round(h.height), right: Math.round(s.right), w: window.innerWidth, mic: Math.round(m.width), input: Math.round(i.width) }; }""")
    ok(hd['h'] <= 40 and hd['right'] <= hd['w'] and hd['mic'] > 20 and hd['input'] > 150,
       'phone: the ask window header is one line, the language of the conversation fits, 🎤 in the row, room to type: %s' % hd)
    page.screenshot(path=os.path.join(shots, 'phone-ask.png'))
    # text from another app (Android: selected text → «Ttranslator»): into the field, «Авто» → «Авто», translated at once
    page.select_option('#srcSel', 'ru'); page.select_option('#tgtSel', 'en')
    page.evaluate("document.querySelector('#cards').innerHTML = ''")
    r = page.evaluate("window.ttwSetText('  Guten Morgen! Wie geht es Ihnen?  ')")
    page.wait_for_function("document.querySelectorAll('.card').length > 0 && document.querySelector('#stopBtn').hidden", timeout=120000)
    got = page.evaluate("[document.querySelector('#src').value, document.querySelector('#srcSel').value, document.querySelector('#tgtSel').value]")
    ok(r is True and got == ['Guten Morgen! Wie geht es Ihnen?', 'auto', 'auto'], 'text from another app: in the field, «Авто» → «Авто», translated at once: %s' % got)
    ok(page.evaluate("window.ttwSetText('   ')") is False, 'empty text from another app: nothing happens')
    # a phone with little memory (Android sees under 5 GB: a "4 GB" phone): a warning in the menu of models
    notes = page.evaluate("""() => { const was = STATE.machine.ram_gb, out = [];
      for (const gb of [3.6, 7.4]) { STATE.machine.ram_gb = gb; renderModelMenu(); const n = document.querySelector('#modelMenu .warn-note'); out.push(n ? n.textContent : ''); }
      STATE.machine.ram_gb = was; renderModelMenu(); return out; }""")
    ok('3,6' in notes[0] and '6 ГБ' in notes[0] and notes[1] == '', 'a phone with 3.6 GB: a warning in the menu of models; with 7.4 GB none: %s' % notes)
    page.click('#modelBtn'); time.sleep(0.3)
    ok(page.is_visible('#modelMenu'), 'the model menu opens')
    ok(page.evaluate('window.ttwBack()') is True and not page.is_visible('#modelMenu'), '«Назад» closes the model menu')
    ok(page.evaluate('window.ttwBack()') is False, '«Назад» with nothing open: false (the app goes to the background)')
    ok(not errors, 'no errors in the page: %s' % errors[:3])
    b.close()

    # ---------------------------------------------------------------- 2) the phone screen in a browser tab
    b, page, errors = open_page(p, PHONE, '')
    ok(not page.evaluate("document.documentElement.classList.contains('android')"), 'browser tab: not Android')
    ok(page.evaluate("getComputedStyle(document.querySelector('#goBtn .kbd')).display") != 'none', 'browser tab: the keyboard hint stays')
    ok(page.is_visible('#moreBtn') and page.evaluate("document.documentElement.scrollWidth") == 412, 'browser tab, narrow: the same phone header')
    page.click('#moreBtn'); time.sleep(0.2)
    page.locator('#popMenu .mi', has_text='Сохранённые').first.click(); time.sleep(0.4)
    page.click('#savedMenuBtn'); time.sleep(0.3)
    ok('Открыть папку' in menu_items(page), 'browser tab: «Открыть папку» stays in Сохранённые')
    page.evaluate('window.ttwBack()'); time.sleep(0.2)
    page.click('#moreBtn'); time.sleep(0.2)
    page.locator('#popMenu .mi', has_text='Справка').first.click(); time.sleep(0.4)
    h = page.eval_on_selector_all('#helpBody h3', 'es => es.map(e => e.textContent)')
    ok(h[:1] == ['Перевод'] and 'Обновление и удаление' in h and not [x for x in h if x.startswith('Android')],
       'browser tab: the help of a computer, without the Android section: %s' % h[:3])
    ok(not errors, 'no errors in the page: %s' % errors[:3])
    b.close()

    # ---------------------------------------------------------------- 3) the computer, as before
    b, page, errors = open_page(p, dict(viewport={'width': 1280, 'height': 800}), '')
    shown = page.evaluate("[...document.querySelectorAll('header.top .actions button')].filter(e => e.getClientRects().length).map(e => e.id)")
    ok(not page.is_visible('#moreBtn') and all(x in shown for x in ['settingsBtn', 'modelBtn', 'savedBtn', 'testBtn', 'helpBtn', 'aboutBtn']),
       'computer: all header buttons, no «⋮»: %s' % shown)
    cols = page.evaluate("[document.querySelector('.left').getBoundingClientRect().right, document.querySelector('.right').getBoundingClientRect().left, document.querySelector('.left').getBoundingClientRect().top, document.querySelector('.right').getBoundingClientRect().top]")
    ok(abs(cols[0] - cols[1]) < 2 and abs(cols[2] - cols[3]) < 2, 'computer: two columns side by side: %s' % cols)
    page.click('#settingsBtn'); time.sleep(0.4)
    ok(page.is_visible('.left') and page.is_visible('#settingsView'), 'computer: the settings open next to the work window, as before')
    ok(not errors, 'no errors in the page: %s' % errors[:3])
    b.close()

fails = [r for r in res if r.startswith('FAIL')]
print('FAILS: %d of %d' % (len(fails), len(res)))
