// ttranslator-window — the own window of Ttranslator (launch_mode "window"). It shows the interface of the launcher
// in a native window with the web engine of the system: WebView2 on Windows, WebKitGTK on Linux, WKWebView on macOS
// (1.1). Built on the webview library (https://github.com/webview/webview, MIT, version 0.12.0, in webview/ with
// one small patch, see README.md). The launcher stays on the Go standard library; it starts this program and, if
// it cannot start (no WebView2 Runtime, no WebKitGTK), opens an Edge/Chrome window instead.
//
//   ttranslator-window URL [--title TEXT] [--size WxH] [--maximized] [--data DIR] [--icon FILE.png] [--lang CODE]
//
//   URL      a page of the launcher: http://127.0.0.1:PORT/... or http://localhost:PORT/...
//   --data   Windows: folder for the WebView2 profile (else WebView2 writes into %APPDATA%)
//   --icon   Linux: window icon (PNG); on Windows the icon is a resource of this program, on macOS of Ttranslator.app
//   --lang   macOS: the language of the menu bar (en, ru, de, es, zh — the interface language)
//   --maximized  start maximized (the size of --size is the size after "restore"; macOS: the window is zoomed)
//
// Prints "ready" on stdout when the window exists. Exit codes: 0 — the window was closed, 2 — wrong arguments,
// 3 — the web engine is not available.
//
// The window shows only pages of the launcher: other addresses (links to GitHub, e-mail) open in the default
// browser or mail program. For the page there are three functions (each returns a Promise):
//   ttwOpenExternal(url)                        open an http(s) or mailto address outside the window
//   ttwSaveFile(name, text, ext, title, label)  "Save as" dialog of the system, writes text (UTF-8) to the file;
//                                               resolves to {path} or {cancelled: true}
//   ttwClose()                                  close the window (after «Выход»)
// and window.TTW = { version } tells the page that it runs in this window.
//
// At start the window comes to the front (0.9.3): the launcher, started from Explorer, passes its right to take the
// foreground to this program (AllowSetForegroundWindow); Linux: gtk_window_present; macOS: the app activates itself.
//
// macOS (1.1): Cocoa through the Objective-C runtime, as in webview.h (no Objective-C compiler mode needed). The
// program is a regular app with a menu bar — the Edit menu is what makes ⌘C, ⌘V, ⌘X, ⌘A and ⌘Z work in the page —
// although Ttranslator.app itself is an agent (LSUIElement: the launcher has no window and no Dock icon).

#if defined(_WIN32) && !defined(_WIN32_WINNT)
#define _WIN32_WINNT 0x0A00   // Windows 10 (older MinGW headers default to XP and hide QueryFullProcessImageNameW)
#endif

#include "webview/webview.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

#if defined(_WIN32)
#include <windows.h>
#include <commdlg.h>
#include <shellapi.h>
#elif defined(__APPLE__)
#include <objc/message.h>
#include <objc/runtime.h>
#else
#include <gtk/gtk.h>
#include <webkit2/webkit2.h>
#endif

namespace {

const char *const kVersion = "1";

webview_t g_wv = nullptr;
std::string g_origin;   // "http://127.0.0.1:PORT": the only site shown inside the window

// ---------------------------------------------------------------- strings

bool starts_with(const std::string &s, const char *p) { return s.compare(0, std::strlen(p), p) == 0; }

std::string lower_ascii(std::string s) {
  for (auto &c : s) {
    if (c >= 'A' && c <= 'Z') c = char(c - 'A' + 'a');
  }
  return s;
}

void put_utf8(std::string &o, unsigned long cp) {
  if (cp < 0x80) {
    o += char(cp);
  } else if (cp < 0x800) {
    o += char(0xC0 | (cp >> 6));
    o += char(0x80 | (cp & 0x3F));
  } else if (cp < 0x10000) {
    o += char(0xE0 | (cp >> 12));
    o += char(0x80 | ((cp >> 6) & 0x3F));
    o += char(0x80 | (cp & 0x3F));
  } else {
    o += char(0xF0 | (cp >> 18));
    o += char(0x80 | ((cp >> 12) & 0x3F));
    o += char(0x80 | ((cp >> 6) & 0x3F));
    o += char(0x80 | (cp & 0x3F));
  }
}

// The arguments of a call from the page: a JSON array; strings are decoded (with \uXXXX and surrogate pairs),
// other values become empty strings.
std::vector<std::string> json_args(const std::string &s) {
  std::vector<std::string> out;
  size_t i = 0, n = s.size();
  auto ws = [&] { while (i < n && (s[i] == ' ' || s[i] == '\n' || s[i] == '\r' || s[i] == '\t')) i++; };
  auto hex4 = [&](size_t at, unsigned long &v) {
    if (at + 4 > n) return false;
    v = 0;
    for (size_t k = at; k < at + 4; k++) {
      char c = s[k];
      v <<= 4;
      if (c >= '0' && c <= '9') v |= unsigned(c - '0');
      else if (c >= 'a' && c <= 'f') v |= unsigned(c - 'a' + 10);
      else if (c >= 'A' && c <= 'F') v |= unsigned(c - 'A' + 10);
      else return false;
    }
    return true;
  };
  ws();
  if (i >= n || s[i] != '[') return out;
  i++;
  for (;;) {
    ws();
    if (i >= n || s[i] == ']') break;
    std::string v;
    if (s[i] == '"') {
      i++;
      while (i < n && s[i] != '"') {
        char c = s[i++];
        if (c != '\\') { v += c; continue; }
        if (i >= n) break;
        char e = s[i++];
        switch (e) {
        case 'n': v += '\n'; break;
        case 'r': v += '\r'; break;
        case 't': v += '\t'; break;
        case 'b': v += '\b'; break;
        case 'f': v += '\f'; break;
        case 'u': {
          unsigned long cp = 0;
          if (!hex4(i, cp)) break;
          i += 4;
          if (cp >= 0xD800 && cp < 0xDC00) {   // a surrogate pair
            unsigned long lo = 0;
            if (i + 6 <= n && s[i] == '\\' && s[i + 1] == 'u' && hex4(i + 2, lo) && lo >= 0xDC00 && lo < 0xE000) {
              i += 6;
              cp = 0x10000 + ((cp - 0xD800) << 10) + (lo - 0xDC00);
            } else {
              cp = 0xFFFD;
            }
          } else if (cp >= 0xDC00 && cp < 0xE000) {
            cp = 0xFFFD;
          }
          put_utf8(v, cp);
          break;
        }
        default: v += e;   // \" \\ \/
        }
      }
      i++;   // the closing quote
    } else {   // a number, true, false, null: not used by the page
      while (i < n && s[i] != ',' && s[i] != ']') i++;
    }
    out.push_back(v);
    ws();
    if (i < n && s[i] == ',') i++;
  }
  return out;
}

std::string json_quote(const std::string &s) {
  std::string o = "\"";
  for (unsigned char c : s) {
    switch (c) {
    case '"': o += "\\\""; break;
    case '\\': o += "\\\\"; break;
    case '\n': o += "\\n"; break;
    case '\r': o += "\\r"; break;
    case '\t': o += "\\t"; break;
    default:
      if (c < 0x20) {
        char b[8];
        std::snprintf(b, sizeof b, "\\u%04x", c);
        o += b;
      } else {
        o += char(c);
      }
    }
  }
  return o + "\"";
}

// ---------------------------------------------------------------- addresses

// Inside the window: pages of the launcher, and blob:, data: and about: addresses of those pages.
bool allowed_inside(const std::string &u) {
  std::string l = lower_ascii(u);
  if (starts_with(l, "blob:")) l = l.substr(5);
  if (starts_with(l, "about:") || starts_with(l, "data:")) return true;
  if (l.compare(0, g_origin.size(), g_origin) != 0) return false;
  return l.size() == g_origin.size() || l[g_origin.size()] == '/' || l[g_origin.size()] == '?' || l[g_origin.size()] == '#';
}

bool is_external(const std::string &u) {
  std::string l = lower_ascii(u);
  return starts_with(l, "http://") || starts_with(l, "https://") || starts_with(l, "mailto:");
}

// http://127.0.0.1:PORT/... or http://localhost:PORT/... → "http://host:port"; empty if the URL is not local.
std::string local_origin(const std::string &url) {
  std::string l = lower_ascii(url);
  for (const char *p : {"http://127.0.0.1:", "http://localhost:"}) {
    if (!starts_with(l, p)) continue;
    size_t i = std::strlen(p), j = i;
    while (j < l.size() && l[j] >= '0' && l[j] <= '9') j++;
    if (j == i || j - i > 5 || (j < l.size() && l[j] != '/')) return "";
    return l.substr(0, j);
  }
  return "";
}

// ---------------------------------------------------------------- platform parts

#if defined(_WIN32)

std::wstring widen(const std::string &s) {
  if (s.empty()) return std::wstring();
  int n = MultiByteToWideChar(CP_UTF8, 0, s.data(), int(s.size()), nullptr, 0);
  std::wstring w(size_t(n), L'\0');
  MultiByteToWideChar(CP_UTF8, 0, s.data(), int(s.size()), &w[0], n);
  return w;
}

std::string narrow(const wchar_t *w) {
  if (!w || !*w) return std::string();
  int n = WideCharToMultiByte(CP_UTF8, 0, w, -1, nullptr, 0, nullptr, nullptr);
  std::string s(size_t(n > 0 ? n - 1 : 0), '\0');
  if (n > 1) WideCharToMultiByte(CP_UTF8, 0, w, -1, &s[0], n, nullptr, nullptr);
  return s;
}

void open_external(const std::string &u) {
  ShellExecuteW(nullptr, L"open", widen(u).c_str(), nullptr, nullptr, SW_SHOWNORMAL);
}

std::string save_dialog(const std::string &name, const std::string &ext, const std::string &title, const std::string &label) {
  std::vector<wchar_t> file(32768, L'\0');
  std::wstring wname = widen(name);
  wcsncpy(file.data(), wname.c_str(), file.size() - 1);
  std::wstring wext = widen(ext), wtitle = widen(title);
  std::wstring filter;   // "label (*.ext)\0*.ext\0*.*\0*.*\0\0"
  if (!wext.empty()) {
    filter += widen(label.empty() ? ext : label) + L" (*." + wext + L")";
    filter += L'\0';
    filter += L"*." + wext;
    filter += L'\0';
  }
  filter += L"*.*";
  filter += L'\0';
  filter += L"*.*";
  filter += L'\0';
  filter += L'\0';
  OPENFILENAMEW ofn;
  ZeroMemory(&ofn, sizeof ofn);
  ofn.lStructSize = sizeof ofn;
  ofn.hwndOwner = static_cast<HWND>(webview_get_window(g_wv));
  ofn.lpstrFilter = filter.c_str();
  ofn.lpstrFile = file.data();
  ofn.nMaxFile = DWORD(file.size());
  ofn.lpstrTitle = wtitle.empty() ? nullptr : wtitle.c_str();
  ofn.lpstrDefExt = wext.empty() ? nullptr : wext.c_str();
  ofn.Flags = OFN_OVERWRITEPROMPT | OFN_PATHMUSTEXIST | OFN_EXPLORER | OFN_NOCHANGEDIR | OFN_HIDEREADONLY;
  if (!GetSaveFileNameW(&ofn)) return std::string();
  return narrow(file.data());
}

bool write_file(const std::string &path, const std::string &data) {
  FILE *f = _wfopen(widen(path).c_str(), L"wb");
  if (!f) return false;
  bool ok = std::fwrite(data.data(), 1, data.size(), f) == data.size();
  return std::fclose(f) == 0 && ok;
}

void say_ready() {
  HANDLE h = GetStdHandle(STD_OUTPUT_HANDLE);
  if (h && h != INVALID_HANDLE_VALUE) {
    DWORD n = 0;
    WriteFile(h, "ready\n", 6, &n, nullptr);
  }
}

// A minimal COM event handler for WebView2: Invoke is a lambda.
template <class Iface, class Args>
class event_handler : public Iface {
public:
  using fn_t = void (*)(Args *);
  event_handler(const IID &iid, fn_t fn) : m_iid(iid), m_fn(fn) {}
  HRESULT STDMETHODCALLTYPE QueryInterface(REFIID riid, void **ppv) override {
    if (!ppv) return E_POINTER;
    if (IsEqualIID(riid, m_iid) || IsEqualIID(riid, IID_IUnknown)) {
      *ppv = static_cast<Iface *>(this);
      AddRef();
      return S_OK;
    }
    *ppv = nullptr;
    return E_NOINTERFACE;
  }
  ULONG STDMETHODCALLTYPE AddRef() override { return InterlockedIncrement(&m_ref); }
  ULONG STDMETHODCALLTYPE Release() override {
    ULONG r = InterlockedDecrement(&m_ref);
    if (r == 0) delete this;
    return r;
  }
  HRESULT STDMETHODCALLTYPE Invoke(ICoreWebView2 *, Args *args) override {
    if (args) m_fn(args);
    return S_OK;
  }

private:
  virtual ~event_handler() = default;
  IID m_iid;
  fn_t m_fn;
  LONG m_ref{1};
};

// IIDs from WebView2.h (MIDL_INTERFACE uuids; MinGW has no __uuidof for them).
const IID kNewWindowRequestedHandler = {0xd4c185fe, 0xc81c, 0x4989, {0x97, 0xaf, 0x2d, 0x3f, 0xa7, 0xab, 0x56, 0x51}};
const IID kNavigationStartingHandler = {0x9adbe429, 0xf36d, 0x432b, {0x9d, 0xdc, 0xf8, 0x88, 0x1f, 0xbd, 0x76, 0xe3}};

std::string take_uri(LPWSTR uri) {
  std::string u = narrow(uri);
  if (uri) CoTaskMemFree(uri);
  return u;
}

// Links that want a new window and navigation to other sites go to the default browser.
void guard_navigation() {
  auto *ctrl = static_cast<ICoreWebView2Controller *>(webview_get_native_handle(g_wv, WEBVIEW_NATIVE_HANDLE_KIND_BROWSER_CONTROLLER));
  if (!ctrl) return;
  ICoreWebView2 *core = nullptr;
  if (FAILED(ctrl->get_CoreWebView2(&core)) || !core) return;
  EventRegistrationToken token;
  auto *nw = new event_handler<ICoreWebView2NewWindowRequestedEventHandler, ICoreWebView2NewWindowRequestedEventArgs>(
      kNewWindowRequestedHandler, [](ICoreWebView2NewWindowRequestedEventArgs *a) {
        LPWSTR uri = nullptr;
        a->get_Uri(&uri);
        std::string u = take_uri(uri);
        a->put_Handled(TRUE);   // no second window inside the program
        if (is_external(u)) open_external(u);
      });
  core->add_NewWindowRequested(nw, &token);
  nw->Release();
  auto *ns = new event_handler<ICoreWebView2NavigationStartingEventHandler, ICoreWebView2NavigationStartingEventArgs>(
      kNavigationStartingHandler, [](ICoreWebView2NavigationStartingEventArgs *a) {
        LPWSTR uri = nullptr;
        a->get_Uri(&uri);
        std::string u = take_uri(uri);
        if (allowed_inside(u)) return;
        a->put_Cancel(TRUE);
        if (is_external(u)) open_external(u);
      });
  core->add_NavigationStarting(ns, &token);
  ns->Release();
  core->Release();
}

void set_icon(const std::string &) {}   // the icon is a resource of the exe (ttranslator-window.rc)

void maximize() { ShowWindow(static_cast<HWND>(webview_get_window(g_wv)), SW_MAXIMIZE); }

// The window of the shell: a folder window or the desktop (explorer.exe).
bool is_shell_window(HWND w) {
  DWORD pid = 0;
  GetWindowThreadProcessId(w, &pid);
  HANDLE p = pid ? OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid) : nullptr;
  if (!p) return false;
  wchar_t buf[MAX_PATH];
  DWORD n = MAX_PATH;
  bool shell = false;
  if (QueryFullProcessImageNameW(p, 0, buf, &n)) {
    std::wstring s(buf, n);
    size_t k = s.find_last_of(L"\\/");
    shell = _wcsicmp(s.c_str() + (k == std::wstring::npos ? 0 : k + 1), L"explorer.exe") == 0;
  }
  CloseHandle(p);
  return shell;
}

// To the front at start. A program started by another program in the background (the launcher) may not take the
// foreground by itself: its window would open behind the folder window in which Ttranslator.exe was started. The
// launcher passes its right on (AllowSetForegroundWindow), so SetForegroundWindow works. If Windows still refuses
// and the foreground window is the shell (the folder or the desktop), the input of the two threads is joined for a
// moment — the usual way around; never over another program the user switched to meanwhile.
void bring_to_front() {
  HWND hwnd = static_cast<HWND>(webview_get_window(g_wv));
  if (!hwnd || GetForegroundWindow() == hwnd) return;
  if (SetForegroundWindow(hwnd) && GetForegroundWindow() == hwnd) return;
  HWND fg = GetForegroundWindow();
  if (!fg || !is_shell_window(fg)) return;
  DWORD fg_tid = GetWindowThreadProcessId(fg, nullptr), tid = GetCurrentThreadId();
  if (fg_tid && fg_tid != tid && AttachThreadInput(tid, fg_tid, TRUE)) {
    BringWindowToTop(hwnd);
    SetForegroundWindow(hwnd);
    AttachThreadInput(tid, fg_tid, FALSE);
  }
}

#elif defined(__APPLE__)   // macOS: Cocoa and WKWebView through the Objective-C runtime

// A method call with its exact signature (objc_msgSend must be cast so on arm64).
template <typename R = id, typename... A>
R msg(id self, const char *sel, A... args) {
  return reinterpret_cast<R (*)(id, SEL, A...)>(objc_msgSend)(self, sel_registerName(sel), args...);
}

id cls(const char *name) { return reinterpret_cast<id>(objc_getClass(name)); }

id ns_string(const std::string &s) { return msg(cls("NSString"), "stringWithUTF8String:", s.c_str()); }

std::string utf8(id s) {
  const char *p = s ? msg<const char *>(s, "UTF8String") : nullptr;
  return p ? p : "";
}

// Autoreleased objects made outside the run loop of the app go to a pool of our own.
struct autorelease_pool {
  id pool = msg(msg(cls("NSAutoreleasePool"), "alloc"), "init");
  ~autorelease_pool() { msg<void>(pool, "drain"); }
};

id window() { return static_cast<id>(webview_get_window(g_wv)); }

void open_external(const std::string &u) {
  autorelease_pool arp;
  id url = msg(cls("NSURL"), "URLWithString:", ns_string(u));
  if (!url) {   // letters a URL may not have (the page gives addresses already encoded; just in case)
    id esc = msg(ns_string(u), "stringByAddingPercentEncodingWithAllowedCharacters:", msg(cls("NSCharacterSet"), "URLQueryAllowedCharacterSet"));
    url = esc ? msg(cls("NSURL"), "URLWithString:", esc) : nullptr;
  }
  if (!url || !msg<BOOL>(msg(cls("NSWorkspace"), "sharedWorkspace"), "openURL:", url)) {
    std::fprintf(stderr, "cannot open %s\n", u.c_str());
  }
}

// The "Save" panel of macOS, in the Downloads folder (as on Linux); the extension is added if the name has none.
std::string save_dialog(const std::string &name, const std::string &ext, const std::string &title, const std::string &) {
  autorelease_pool arp;
  id panel = msg(cls("NSSavePanel"), "savePanel");
  if (!title.empty()) msg<void>(panel, "setMessage:", ns_string(title));
  msg<void>(panel, "setNameFieldStringValue:", ns_string(name));
  msg<void>(panel, "setCanCreateDirectories:", (BOOL)YES);
  msg<void>(panel, "setExtensionHidden:", (BOOL)NO);
  msg<void>(panel, "setShowsTagField:", (BOOL)NO);
  if (!ext.empty()) {
    id type = cls("UTType") ? msg(cls("UTType"), "typeWithFilenameExtension:", ns_string(ext)) : nullptr;
    if (type) msg<void>(panel, "setAllowedContentTypes:", msg(cls("NSArray"), "arrayWithObject:", type));
    msg<void>(panel, "setAllowsOtherFileTypes:", (BOOL)YES);
  }
  id dirs = msg(msg(cls("NSFileManager"), "defaultManager"), "URLsForDirectory:inDomains:",
                (NSUInteger)15 /* NSDownloadsDirectory */, (NSUInteger)1 /* NSUserDomainMask */);
  if (dirs && msg<NSUInteger>(dirs, "count") > 0) msg<void>(panel, "setDirectoryURL:", msg(dirs, "firstObject"));
  if (msg<NSInteger>(panel, "runModal") != 1 /* NSModalResponseOK */) return std::string();
  return utf8(msg(msg(panel, "URL"), "path"));
}

bool write_file(const std::string &path, const std::string &data) {
  FILE *f = std::fopen(path.c_str(), "wb");
  if (!f) return false;
  bool ok = std::fwrite(data.data(), 1, data.size(), f) == data.size();
  return std::fclose(f) == 0 && ok;
}

void say_ready() {
  std::fputs("ready\n", stdout);
  std::fflush(stdout);
}

// The decision handler of WebKit is a block: called through its function (the layout of blocks is a fixed ABI).
struct block_layout {
  void *isa;
  int flags;
  int reserved;
  void (*invoke)(void *, ...);
};

void decide(id handler, NSInteger policy) {
  auto *b = reinterpret_cast<block_layout *>(handler);
  reinterpret_cast<void (*)(void *, NSInteger)>(b->invoke)(b, policy);
}

// WKNavigationDelegate: pages of the launcher stay inside; links that want a new window (no target frame) and other
// sites go to the default browser.
void decide_policy(id, SEL, id, id action, id handler) {
  std::string u = utf8(msg(msg(msg(action, "request"), "URL"), "absoluteString"));
  bool allow = msg(action, "targetFrame") != nullptr && allowed_inside(u);
  decide(handler, allow ? 1 /* WKNavigationActionPolicyAllow */ : 0 /* Cancel */);
  if (!allow && is_external(u)) open_external(u);
}

void guard_navigation() {
  id view = static_cast<id>(webview_get_native_handle(g_wv, WEBVIEW_NATIVE_HANDLE_KIND_UI_WIDGET));
  if (!view) return;
  Class c = objc_allocateClassPair(reinterpret_cast<Class>(cls("NSObject")), "TtwNavigationDelegate", 0);
  if (!c) return;
  class_addProtocol(c, objc_getProtocol("WKNavigationDelegate"));
  class_addMethod(c, sel_registerName("webView:decidePolicyForNavigationAction:decisionHandler:"),
                  reinterpret_cast<IMP>(decide_policy), "v@:@@@?");
  objc_registerClassPair(c);
  // kept as long as the program runs: the view holds its navigation delegate weakly
  msg<void>(view, "setNavigationDelegate:", msg(reinterpret_cast<id>(c), "new"));
}

void set_icon(const std::string &) {}   // the icon of Ttranslator.app

// Maximized = zoomed to the screen; the zoom button gives back the size of --size.
void maximize() { msg<void>(window(), "zoom:", (id) nullptr); }

void bring_to_front() {
  id app = msg(cls("NSApplication"), "sharedApplication");
  msg<void>(window(), "makeKeyAndOrderFront:", (id) nullptr);
  msg<void>(window(), "orderFrontRegardless");
  msg<void>(app, "activateIgnoringOtherApps:", (BOOL)YES);
}

// The menu bar in the interface language: the names macOS itself uses in these languages.
struct menu_texts {
  const char *about, *hide, *hide_others, *show_all, *quit, *edit, *undo, *redo, *cut, *copy, *paste, *select_all,
      *window, *minimize, *zoom, *close;
};

const menu_texts &menu_for(const std::string &lang) {
  static const menu_texts en = {"About Ttranslator", "Hide Ttranslator", "Hide Others", "Show All", "Quit Ttranslator",
                                "Edit", "Undo", "Redo", "Cut", "Copy", "Paste", "Select All",
                                "Window", "Minimize", "Zoom", "Close"};
  static const menu_texts ru = {"О программе Ttranslator", "Скрыть Ttranslator", "Скрыть остальные", "Показать все",
                                "Завершить Ttranslator", "Правка", "Отменить", "Повторить", "Вырезать", "Скопировать",
                                "Вставить", "Выбрать все", "Окно", "Свернуть", "Изменить масштаб", "Закрыть"};
  static const menu_texts de = {"Über Ttranslator", "Ttranslator ausblenden", "Andere ausblenden", "Alle einblenden",
                                "Ttranslator beenden", "Bearbeiten", "Widerrufen", "Wiederholen", "Ausschneiden",
                                "Kopieren", "Einsetzen", "Alles auswählen", "Fenster", "Im Dock ablegen", "Zoomen",
                                "Schließen"};
  static const menu_texts es = {"Acerca de Ttranslator", "Ocultar Ttranslator", "Ocultar otros", "Mostrar todo",
                                "Salir de Ttranslator", "Edición", "Deshacer", "Rehacer", "Cortar", "Copiar", "Pegar",
                                "Seleccionar todo", "Ventana", "Minimizar", "Zoom", "Cerrar"};
  static const menu_texts zh = {"关于 Ttranslator", "隐藏 Ttranslator", "隐藏其他", "全部显示", "退出 Ttranslator",
                                "编辑", "撤销", "重做", "剪切", "拷贝", "粘贴", "全选", "窗口", "最小化", "缩放", "关闭"};
  if (lang == "ru") return ru;
  if (lang == "de") return de;
  if (lang == "es") return es;
  if (lang == "zh") return zh;
  return en;
}

id add_item(id menu, const char *title, const char *action, const char *key) {
  id item = msg(msg(cls("NSMenuItem"), "alloc"), "initWithTitle:action:keyEquivalent:", ns_string(title),
                action ? sel_registerName(action) : static_cast<SEL>(nullptr), ns_string(key));
  msg<void>(menu, "addItem:", item);
  return item;
}

void add_separator(id menu) { msg<void>(menu, "addItem:", msg(cls("NSMenuItem"), "separatorItem")); }

id add_menu(id bar, const char *title) {
  id menu = msg(msg(cls("NSMenu"), "alloc"), "initWithTitle:", ns_string(title));
  msg<void>(add_item(bar, title, nullptr, ""), "setSubmenu:", menu);
  return menu;
}

// A regular app (the Dock icon, the menu bar) with its menu, before the window is made. The menu items go to the
// first responder: the page (copy, paste…), the window (close, minimize) or the app (hide, quit).
void prepare_app(const std::string &lang) {
  autorelease_pool arp;
  const menu_texts &m = menu_for(lang);
  id app = msg(cls("NSApplication"), "sharedApplication");
  msg<void>(app, "setActivationPolicy:", (NSInteger)0 /* NSApplicationActivationPolicyRegular */);
  id bar = msg(msg(cls("NSMenu"), "alloc"), "initWithTitle:", ns_string(""));
  id appm = add_menu(bar, "Ttranslator");
  add_item(appm, m.about, "orderFrontStandardAboutPanel:", "");
  add_separator(appm);
  add_item(appm, m.hide, "hide:", "h");
  msg<void>(add_item(appm, m.hide_others, "hideOtherApplications:", "h"), "setKeyEquivalentModifierMask:",
            (NSUInteger)((1 << 19) | (1 << 20)));   // ⌥⌘H
  add_item(appm, m.show_all, "unhideAllApplications:", "");
  add_separator(appm);
  add_item(appm, m.quit, "terminate:", "q");
  id edit = add_menu(bar, m.edit);
  add_item(edit, m.undo, "undo:", "z");
  add_item(edit, m.redo, "redo:", "Z");   // ⇧⌘Z
  add_separator(edit);
  add_item(edit, m.cut, "cut:", "x");
  add_item(edit, m.copy, "copy:", "c");
  add_item(edit, m.paste, "paste:", "v");
  add_item(edit, m.select_all, "selectAll:", "a");
  id win = add_menu(bar, m.window);
  add_item(win, m.minimize, "performMiniaturize:", "m");
  add_item(win, m.zoom, "performZoom:", "");
  add_separator(win);
  add_item(win, m.close, "performClose:", "w");
  msg<void>(app, "setMainMenu:", bar);
  msg<void>(app, "setWindowsMenu:", win);
}

#else   // Linux: GTK 3 and WebKitGTK

void open_external(const std::string &u) {
  GError *err = nullptr;
  if (!g_app_info_launch_default_for_uri(u.c_str(), nullptr, &err)) {
    std::fprintf(stderr, "cannot open %s: %s\n", u.c_str(), err ? err->message : "?");
    if (err) g_error_free(err);
  }
}

std::string save_dialog(const std::string &name, const std::string &ext, const std::string &title, const std::string &label) {
  GtkWindow *parent = GTK_WINDOW(webview_get_window(g_wv));
  GtkFileChooserNative *d = gtk_file_chooser_native_new(title.empty() ? nullptr : title.c_str(), parent,
                                                        GTK_FILE_CHOOSER_ACTION_SAVE, nullptr, nullptr);
  GtkFileChooser *fc = GTK_FILE_CHOOSER(d);
  gtk_file_chooser_set_do_overwrite_confirmation(fc, TRUE);
  if (const char *dl = g_get_user_special_dir(G_USER_DIRECTORY_DOWNLOAD)) {
    gtk_file_chooser_set_current_folder(fc, dl);
  }
  gtk_file_chooser_set_current_name(fc, name.c_str());
  if (!ext.empty()) {
    GtkFileFilter *f = gtk_file_filter_new();
    gtk_file_filter_set_name(f, ((label.empty() ? ext : label) + " (*." + ext + ")").c_str());
    gtk_file_filter_add_pattern(f, ("*." + ext).c_str());
    gtk_file_chooser_add_filter(fc, f);
    GtkFileFilter *all = gtk_file_filter_new();
    gtk_file_filter_set_name(all, "*.*");
    gtk_file_filter_add_pattern(all, "*");
    gtk_file_chooser_add_filter(fc, all);
  }
  std::string path;
  if (gtk_native_dialog_run(GTK_NATIVE_DIALOG(d)) == GTK_RESPONSE_ACCEPT) {
    if (char *p = gtk_file_chooser_get_filename(fc)) {
      path = p;
      g_free(p);
    }
  }
  g_object_unref(d);
  return path;
}

bool write_file(const std::string &path, const std::string &data) {
  FILE *f = std::fopen(path.c_str(), "wb");
  if (!f) return false;
  bool ok = std::fwrite(data.data(), 1, data.size(), f) == data.size();
  return std::fclose(f) == 0 && ok;
}

void say_ready() {
  std::fputs("ready\n", stdout);
  std::fflush(stdout);
}

gboolean on_decide_policy(WebKitWebView *, WebKitPolicyDecision *d, WebKitPolicyDecisionType type, gpointer) {
  if (type != WEBKIT_POLICY_DECISION_TYPE_NAVIGATION_ACTION && type != WEBKIT_POLICY_DECISION_TYPE_NEW_WINDOW_ACTION) {
    return FALSE;
  }
  WebKitNavigationAction *a = webkit_navigation_policy_decision_get_navigation_action(WEBKIT_NAVIGATION_POLICY_DECISION(d));
  const char *uri = webkit_uri_request_get_uri(webkit_navigation_action_get_request(a));
  std::string u = uri ? uri : "";
  if (type == WEBKIT_POLICY_DECISION_TYPE_NAVIGATION_ACTION && allowed_inside(u)) return FALSE;
  webkit_policy_decision_ignore(d);
  if (is_external(u)) open_external(u);
  return TRUE;
}

// Links that want a new window and navigation to other sites go to the default browser.
void guard_navigation() {
  auto *view = static_cast<GtkWidget *>(webview_get_native_handle(g_wv, WEBVIEW_NATIVE_HANDLE_KIND_UI_WIDGET));
  if (view) g_signal_connect(view, "decide-policy", G_CALLBACK(on_decide_policy), nullptr);
}

void set_icon(const std::string &icon) {
  if (!icon.empty()) gtk_window_set_icon_from_file(GTK_WINDOW(webview_get_window(g_wv)), icon.c_str(), nullptr);
}

void maximize() { gtk_window_maximize(GTK_WINDOW(webview_get_window(g_wv))); }

void bring_to_front() { gtk_window_present(GTK_WINDOW(webview_get_window(g_wv))); }

#endif

// ---------------------------------------------------------------- functions for the page

struct call_t {
  std::string id;
  std::vector<std::string> args;
};

// The dialog runs after the call has returned to the engine (webview_dispatch): no dialog inside an event handler.
void save_file_later(webview_t w, void *arg) {
  auto *c = static_cast<call_t *>(arg);
  auto a = [&](size_t i) { return i < c->args.size() ? c->args[i] : std::string(); };
  std::string name = a(0), ext = a(2);
  for (auto &ch : name) {   // a plain file name
    if (ch == '/' || ch == '\\' || ch == ':' || ch == '*' || ch == '?' || ch == '"' || ch == '<' || ch == '>' || ch == '|') ch = '_';
  }
  std::string path = save_dialog(name, ext, a(3), a(4));
  if (path.empty()) {
    webview_return(w, c->id.c_str(), 0, "{\"cancelled\":true}");
  } else if (write_file(path, a(1))) {
    webview_return(w, c->id.c_str(), 0, ("{\"path\":" + json_quote(path) + "}").c_str());
  } else {
    webview_return(w, c->id.c_str(), 1, json_quote("cannot write " + path).c_str());
  }
  delete c;
}

void bind_functions() {
  webview_bind(g_wv, "ttwOpenExternal", [](const char *id, const char *req, void *) {
    auto args = json_args(req ? req : "");
    std::string u = args.empty() ? "" : args[0];
    if (!is_external(u)) {
      webview_return(g_wv, id, 1, "\"only http, https and mailto addresses\"");
      return;
    }
    open_external(u);
    webview_return(g_wv, id, 0, "true");
  }, nullptr);
  webview_bind(g_wv, "ttwSaveFile", [](const char *id, const char *req, void *) {
    auto *c = new call_t{id ? id : "", json_args(req ? req : "")};
    webview_dispatch(g_wv, save_file_later, c);
  }, nullptr);
  webview_bind(g_wv, "ttwClose", [](const char *id, const char *, void *) {
    webview_return(g_wv, id, 0, "true");
    webview_terminate(g_wv);
  }, nullptr);
  webview_init(g_wv, (std::string("window.TTW = { version: ") + kVersion + " };").c_str());
}

// "1180x780" → 1180, 780 (no sscanf: it would need a newer C library on Linux)
bool parse_size(const std::string &s, int &w, int &h) {
  size_t x = s.find('x');
  if (x == std::string::npos || x == 0 || x + 1 >= s.size() || x > 5 || s.size() - x - 1 > 5) return false;
  w = h = 0;
  for (size_t i = 0; i < s.size(); i++) {
    if (i == x) continue;
    if (s[i] < '0' || s[i] > '9') return false;
    int &v = i < x ? w : h;
    v = v * 10 + (s[i] - '0');
  }
  return w >= 400 && h >= 300 && w <= 10000 && h <= 10000;
}

int run(const std::vector<std::string> &args) {
  std::string url, title = "Ttranslator", data, icon, lang;
  int width = 1180, height = 780;
  bool maximized = false;
  for (size_t i = 0; i < args.size(); i++) {
    const std::string &a = args[i];
    bool has = i + 1 < args.size();
    if (a == "--title" && has) title = args[++i];
    else if (a == "--data" && has) data = args[++i];
    else if (a == "--icon" && has) icon = args[++i];
    else if (a == "--lang" && has) lang = args[++i];
    else if (a == "--maximized") maximized = true;
    else if (a == "--size" && has) {
      int w = 0, h = 0;
      if (parse_size(args[++i], w, h)) {
        width = w;
        height = h;
      }
    } else if (url.empty() && !starts_with(a, "--")) url = a;
    else {
      std::fprintf(stderr, "unknown argument: %s\n", a.c_str());
      return 2;
    }
  }
  g_origin = local_origin(url);
  if (g_origin.empty()) {
    std::fprintf(stderr, "usage: ttranslator-window http://127.0.0.1:PORT/ [--title TEXT] [--size WxH] [--maximized] [--data DIR] [--icon FILE.png] [--lang CODE]\n");
    return 2;
  }
#if defined(_WIN32)
  if (!data.empty()) {
    CreateDirectoryW(widen(data).c_str(), nullptr);
    SetEnvironmentVariableW(L"TTRANSLATOR_WEBVIEW_DATA", widen(data).c_str());
  }
#elif defined(__APPLE__)
  prepare_app(lang);   // macOS: a regular app with its menu bar (the language of the interface)
#else
  g_set_prgname("ttranslator");   // Linux: the application id of the window (taskbar, .desktop file)
#endif
  g_wv = webview_create(0, nullptr);
  if (!g_wv) {
    std::fprintf(stderr, "the web engine is not available (Windows: Microsoft Edge WebView2 Runtime; Linux: WebKitGTK 4.1)\n");
    return 3;
  }
  {
#if defined(__APPLE__)
    autorelease_pool arp;   // what Cocoa makes before the run loop of the app runs
#endif
    webview_set_title(g_wv, title.c_str());
    webview_set_size(g_wv, width, height, WEBVIEW_HINT_NONE);
    if (maximized) maximize();
    set_icon(icon);
    bring_to_front();
    bind_functions();
    guard_navigation();
    webview_navigate(g_wv, url.c_str());
    say_ready();
  }
  webview_run(g_wv);
  webview_destroy(g_wv);
  return 0;
}

}   // namespace

#if defined(_WIN32)
int main() {   // the arguments in UTF-16 → UTF-8 (paths with non-Latin letters)
  int argc = 0;
  LPWSTR *argv = CommandLineToArgvW(GetCommandLineW(), &argc);
  std::vector<std::string> args;
  for (int i = 1; argv && i < argc; i++) args.push_back(narrow(argv[i]));
  if (argv) LocalFree(argv);
  return run(args);
}
#else
int main(int argc, char **argv) {
  std::vector<std::string> args(argv + 1, argv + argc);
  return run(args);
}
#endif
