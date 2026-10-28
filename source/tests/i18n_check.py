# Completeness of the interface translations (index.html): every Russian text the window can show — t('…') in
# the script, plural forms, texts and hints of the HTML markup, names of languages and styles, texts of the
# «?» menu and notes — has an English, a German, a Spanish and a Chinese translation in I18N (1.0), with the same
# {placeholders}; the help, the About text and «Что нового» exist in all five languages; I18N holds nothing unused.
# Usage: i18n_check.py <path to ui/index.html>      (prints the result; "FAILS: 0" when all is well)
import sys, re, json
from html.parser import HTMLParser
from playwright.sync_api import sync_playwright

PATH = sys.argv[1]
src = open(PATH, encoding='utf-8').read()
res = []
def ok(c, m): res.append(('OK  ' if c else 'FAIL') + ' ' + m)
CYR = re.compile(r'[А-Яа-яЁё]')

# --- texts of the markup (translated at start by translateStatic)
class Markup(HTMLParser):
    def __init__(self):
        super().__init__(); self.skip = 0; self.keys = []
    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.skip += 1
        for k, v in attrs:
            if k in ('title', 'placeholder', 'aria-label') and v and CYR.search(v): self.keys.append(v)
    def handle_endtag(self, tag):
        if tag in ('script', 'style'): self.skip -= 1
    def handle_data(self, data):
        if not self.skip and CYR.search(data): self.keys.append(data.strip())
body = src[src.index('<body>'):]
mk = Markup(); mk.feed(body.split('<script>')[0])
static_keys = set(mk.keys)

# --- the script: t('…') literals, plural forms, data shown through t(variable)
js = src[src.index("<script>\n'use strict';"):]
a = js.index('const I18N = {'); b = js.index('\n};\n', a) + 4
js_code = js[:a] + js[b:]          # the whole script except the dictionary itself
def unq(lit):
    return json.loads('"' + lit[1:-1].replace('\\\'', '\'').replace('"', '\\"') + '"') if lit[0] == "'" else json.loads(lit)
lit = r"'(?:[^'\\\n]|\\.)*'"
t_keys = set(unq(m) for m in re.findall(r"\bt\((" + lit + r")", js_code))
plural_keys = set(unq(m) for m in re.findall(r"\bplural\([^,()]+,\s*(" + lit + r")", js_code))
data_keys = set()
for prop in ('name', 'lower', 'label', 'editLabel', 'sub', 'editHint', 'hymtNote', 'note'):
    for m in re.findall(r"\b" + prop + r":\s*(" + lit + r")", js_code):
        v = unq(m)
        if CYR.search(v): data_keys.add(v)
for name in ('SAVED_TXT_TITLE', 'STYLE_EXAMPLE', 'CTX_EXAMPLE'):
    data_keys.add(unq(re.search(r"const " + name + r" = (" + lit + r")", js_code).group(1)))
data_keys.add(re.search(r"const GLOSS_DEFAULT_FILE = '([^']+)\.tsv'", js_code).group(1))
# Russian forms of language names in sentences (fromLoc) and the editing template are only for Russian
ok(len(t_keys) > 250 and len(static_keys) > 50, 'texts found: t() %d, markup %d, plural %d, data %d' % (len(t_keys), len(static_keys), len(plural_keys), len(data_keys)))

# --- the dictionary, as the page itself sees it
with sync_playwright() as p:
    b = p.chromium.launch(); page = b.new_page()
    page.goto('file://' + PATH)
    page.wait_for_function('typeof I18N === "object"')
    I18N = page.evaluate('I18N')
    help_ = page.evaluate('HELP'); about = page.evaluate('ABOUT'); news = page.evaluate('WHATS_NEW')
    ask_about = page.evaluate("Object.fromEntries(Object.entries(ASK_ABOUT).map(([k, v]) => [k, Array.isArray(v) ? v.map(x => Object.keys(x.q).sort().join(',')) : Object.keys(v).sort().join(',')]))")
    lesson = page.evaluate("({ bad: Object.values(LESSON.topics).flat().filter(x => !(x.en && x.ru && x.de && x.es && x.zh)).map(x => x.en || JSON.stringify(x)), n: Object.values(LESSON.topics).flat().length, ask: Object.values(LESSON_ASK).map(v => Object.keys(v).sort().join(',')) })")
    ui_langs = page.evaluate('Object.keys(UI_LANGS)')
    starter = page.evaluate("GLOSS_STARTER.filter(x => !(x.en && x.ru && x.de && x.es && x.zh)).map(x => x.en)")
    b.close()

ph = re.compile(r'\{\w+\}')
missing, bad_ph, bad_shape = [], [], []
for k in sorted(static_keys | t_keys | data_keys):
    v = I18N.get(k)
    if not (isinstance(v, list) and len(v) == 4 and all(isinstance(x, str) and x.strip() for x in v)):
        missing.append(k); continue
    for x in v:
        if sorted(ph.findall(k)) != sorted(ph.findall(x)) or k.count('<code></code>') != x.count('<code></code>'):
            bad_ph.append((k, x))
for k in sorted(plural_keys):
    v = I18N.get(k)
    if not (isinstance(v, list) and len(v) == 4 and all(isinstance(x, list) and len(x) == 2 and all(y.strip() for y in x) for x in v)):
        bad_shape.append(k)
ok(not missing, 'every text has an English, a German, a Spanish and a Chinese translation; missing %d: %s' % (len(missing), missing[:8]))
ok(not bad_ph, 'placeholders {…} and <code></code> are the same in translations: %s' % bad_ph[:4])
ok(not bad_shape, 'plural forms are [[one, many], [ein, viele], [uno, muchos], [个, 个]]: %s' % bad_shape[:6])
unused = sorted(set(I18N) - static_keys - t_keys - data_keys - plural_keys)
ok(not unused, 'I18N has no unused entries: %s' % unused[:8])
cyr_in_tr = [k for k, v in I18N.items() if any(CYR.search(json.dumps(x, ensure_ascii=False)) for x in v)]
ok(not cyr_in_tr, 'translations contain no Cyrillic letters: %s' % cyr_in_tr[:6])
ok(sorted(ui_langs) == ['de', 'en', 'es', 'ru', 'zh'] and ui_langs[0] == 'en', 'interface languages, English first: %s' % ui_langs)
ok(sorted(help_) == ['de', 'en', 'es', 'ru', 'zh'] and len({len(help_[l]) for l in help_}) == 1 and all(len(help_[l][i]) == len(help_['ru'][i]) for l in help_ for i in range(len(help_['ru']))), 'help in five languages with the same sections and items')
ok(sorted(about) == ['de', 'en', 'es', 'ru', 'zh'] and all(len(about[l]['features']) == len(about['ru']['features']) and sorted(about[l]) == sorted(about['ru']) for l in about),
   'About text in five languages (the same parts: %s)' % sorted(about['ru']))
ok(all(v == 'de,en,es,ru,zh' or all(x == 'de,en,es,ru,zh' for x in v) for v in ask_about.values()), 'questions of the «?» menu in five languages: %s' % ask_about)
ok(not lesson['bad'] and lesson['n'] > 60, 'topics of «Учебный пример» have names in five languages (%d topics): %s' % (lesson['n'], lesson['bad'][:5]))
ok(len(lesson['ask']) == 2 and all(x == 'de,en,es,ru,zh' for x in lesson['ask']), 'questions of «Учебный пример» in five languages: %s' % lesson['ask'])
ok(not starter, 'the first glossary has terms in five languages: %s' % starter)
ok(all(isinstance(news.get(l), list) and len(news[l]) == len(news['ru']) > 0 for l in ('ru', 'en', 'de', 'es', 'zh'))
   and not any(CYR.search(x) for l in ('en', 'de', 'es', 'zh') for x in news[l]), '«Что нового» (WHATS_NEW %s) in five languages, %d items each' % (news.get('version'), len(news.get('ru', []))))
go = open(PATH.replace('/ui/index.html', '/source/launcher/main.go'), encoding='utf-8').read() if '/ui/index.html' in PATH else ''
m = re.search(r'appVersion\s*=\s*"([^"]+)"', go)
v = re.search(r"const APP_VERSION = '([^']+)'", js_code)
ok(bool(m and v and m.group(1) == v.group(1)), 'APP_VERSION in index.html equals appVersion of the launcher (%s / %s)' % (v and v.group(1), m and m.group(1)))   # no "main.go: …": the Go problem matcher of CI would take it for an error
print('\n'.join(res))
print('FAILS:', sum(1 for x in res if x.startswith('FAIL')), 'of', len(res))
