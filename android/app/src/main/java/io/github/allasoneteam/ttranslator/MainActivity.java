package io.github.allasoneteam.ttranslator;

import android.app.Activity;
import android.app.ActivityManager;
import android.content.ActivityNotFoundException;
import android.content.Intent;
import android.content.pm.ApplicationInfo;
import android.content.pm.PackageInfo;
import android.database.Cursor;
import android.graphics.Color;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.os.Handler;
import android.os.Looper;
import android.provider.OpenableColumns;
import android.util.Log;
import android.view.Gravity;
import android.view.View;
import android.view.ViewGroup;
import android.view.WindowInsets;
import android.view.WindowInsetsController;
import android.webkit.ConsoleMessage;
import android.webkit.JavascriptInterface;
import android.webkit.RenderProcessGoneDetail;
import android.webkit.ValueCallback;
import android.webkit.WebChromeClient;
import android.webkit.WebResourceError;
import android.webkit.WebResourceRequest;
import android.webkit.WebResourceResponse;
import android.webkit.WebSettings;
import android.webkit.WebView;
import android.webkit.WebViewClient;
import android.widget.Button;
import android.widget.FrameLayout;
import android.widget.LinearLayout;
import android.widget.TextView;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

/**
 * The window of Ttranslator on Android: the page of the launcher (ui/index.html, the same as on a computer) in a WebView.
 *
 * The page gets the functions of the app window of the computer version (source/window, ttranslator-window):
 * ttwSaveFile — the system's "Save as" (here: the Android file picker), ttwOpenExternal — a link in the browser or
 * the mail app, ttwClose — close the window. They are put into the page before its own scripts run (the page decides
 * at start whether it is in the app window: OWN_WINDOW), as ttranslator-window does it with webview's init script.
 */
public class MainActivity extends Activity {
    private static final int REQ_OPEN = 1, REQ_SAVE = 2;

    /**
     * The window functions over the bridge object TtwAndroid. Every call returns a Promise, as with ttranslator-window;
     * the app answers with __ttwDone(id, result).
     */
    private static final String WINDOW_FUNCTIONS = "<script>/* Ttranslator for Android: the functions of the app window */\n"
        + "(function () {\n"
        + "  var B = window.TtwAndroid; if (!B) return;\n"
        + "  var seq = 0, wait = {};\n"
        + "  window.__ttwDone = function (id, r) { var f = wait[id]; delete wait[id]; if (f) f(r || {}); };\n"
        + "  function call(fn) { return new Promise(function (res, rej) { var id = ++seq;\n"
        + "    wait[id] = function (r) { if (r.error) rej(new Error(r.error)); else res(r); };\n"
        + "    try { fn(id); } catch (e) { delete wait[id]; rej(e); } }); }\n"
        + "  window.ttwSaveFile = function (name, text, ext, title, label) { return call(function (id) {\n"
        + "    B.saveFile(id, String(name || ''), String(text == null ? '' : text), String(ext || ''), String(label || '')); }); };\n"
        + "  window.ttwOpenExternal = function (url) { return call(function (id) { B.openExternal(id, String(url)); }); };\n"
        + "  window.ttwClose = function () { return call(function (id) { B.close(id); }); };\n"
        + "})();\n</script>\n";

    private final Handler ui = new Handler(Looper.getMainLooper());
    private final ExecutorService work = Executors.newCachedThreadPool();
    private Launcher launcher;
    private FrameLayout root;
    private WebView web;
    private LinearLayout overlay;
    private TextView overlayText;
    private Button retryBtn;
    private String lang = "en";
    private boolean pageShown, starting, resumed;

    private ValueCallback<Uri[]> openCallback;
    private int saveId;
    private String saveText;

    @Override
    protected void onCreate(Bundle state) {
        super.onCreate(state);
        launcher = new Launcher(this);
        lang = launcher.uiLanguage();
        logDevice();
        if ((getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0) {
            WebView.setWebContentsDebuggingEnabled(true); // test APK: the CI checks the page over the DevTools protocol
        }

        root = new FrameLayout(this);
        root.setBackgroundColor(Color.parseColor("#f5f4ef"));
        root.setOnApplyWindowInsetsListener((v, in) -> {
            // the page is laid out between the system bars, the display cutout and the keyboard
            int l, t, r, b;
            if (Build.VERSION.SDK_INT >= 30) {
                android.graphics.Insets i = in.getInsets(WindowInsets.Type.systemBars()
                    | WindowInsets.Type.displayCutout() | WindowInsets.Type.ime());
                l = i.left; t = i.top; r = i.right; b = i.bottom;
            } else {
                l = in.getSystemWindowInsetLeft(); t = in.getSystemWindowInsetTop();
                r = in.getSystemWindowInsetRight(); b = in.getSystemWindowInsetBottom();
            }
            v.setPadding(l, t, r, b);
            return in;
        });

        web = new WebView(this);
        setUpWebView(web);
        root.addView(web, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));

        overlay = new LinearLayout(this);
        overlay.setOrientation(LinearLayout.VERTICAL);
        overlay.setGravity(Gravity.CENTER);
        overlay.setBackgroundColor(Color.parseColor("#f5f4ef"));
        overlayText = new TextView(this);
        overlayText.setTextColor(Color.parseColor("#1f1e1c"));
        overlayText.setTextSize(17);
        overlayText.setGravity(Gravity.CENTER);
        overlayText.setPadding(48, 24, 48, 24);
        retryBtn = new Button(this);
        retryBtn.setText(Texts.retry(lang));
        retryBtn.setVisibility(View.GONE);
        retryBtn.setOnClickListener(v -> start());
        overlay.addView(overlayText);
        overlay.addView(retryBtn);
        root.addView(overlay, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
        setContentView(root);
        start();
    }

    private void setUpWebView(WebView w) {
        WebSettings s = w.getSettings();
        s.setJavaScriptEnabled(true);
        s.setDomStorageEnabled(true); // the page keeps the chosen languages and styles in localStorage
        s.setMediaPlaybackRequiresUserGesture(false); // reading aloud plays phrase after phrase
        s.setAllowFileAccess(false);
        s.setAllowContentAccess(true); // files picked for import are content:// addresses
        s.setSupportMultipleWindows(false);
        s.setMixedContentMode(WebSettings.MIXED_CONTENT_NEVER_ALLOW);
        w.addJavascriptInterface(new Bridge(), "TtwAndroid");
        w.setWebViewClient(new Client());
        w.setWebChromeClient(new Chrome());
    }

    /** Starts the launcher (if none answers yet) off the main thread, then opens its page. */
    private void start() {
        if (starting) return;
        starting = true;
        showOverlay(Texts.starting(lang), false);
        work.execute(() -> {
            try {
                launcher.ensureRunning();
                ui.post(() -> {
                    starting = false;
                    lang = launcher.uiLanguage();
                    web.loadUrl(Launcher.URL);
                });
            } catch (IOException e) {
                launcher.log("start failed: " + e.getMessage());
                ui.post(() -> {
                    starting = false;
                    showOverlay(Texts.failed(lang) + "\n" + e.getMessage(), true);
                });
            }
        });
    }

    private void showOverlay(String text, boolean retry) {
        overlayText.setText(text);
        retryBtn.setText(Texts.retry(lang));
        retryBtn.setVisibility(retry ? View.VISIBLE : View.GONE);
        overlay.setVisibility(View.VISIBLE);
    }

    @Override
    protected void onResume() {
        super.onResume();
        resumed = true;
        web.onResume();
        if (!pageShown || starting) return;
        // back after a long while: the launcher may have ended (no window for a while, or Android stopped it)
        work.execute(() -> {
            if (!Launcher.alive()) {
                launcher.log("the launcher does not answer after a pause: starting it again");
                ui.post(() -> {
                    pageShown = false;
                    start();
                });
            }
        });
    }

    @Override
    protected void onPause() {
        resumed = false;
        web.onPause();
        super.onPause();
    }

    @Override
    public void onTrimMemory(int level) {
        super.onTrimMemory(level);
        launcher.log("onTrimMemory " + level + (resumed ? " (in front)" : " (in the background)") + ", " + memInfo());
    }

    @Override
    protected void onDestroy() {
        launcher.log("window closed" + (isFinishing() ? "" : " by the system"));
        if (web != null) {
            root.removeView(web);
            web.destroy();
        }
        work.shutdown();
        super.onDestroy();
    }

    // ------------------------------------------------------------ the page

    private static boolean isOurs(Uri u) {
        return u != null && "http".equals(u.getScheme()) && ("127.0.0.1".equals(u.getHost()) || "localhost".equals(u.getHost()))
            && u.getPort() == Launcher.PORT;
    }

    private class Client extends WebViewClient {
        @Override
        public WebResourceResponse shouldInterceptRequest(WebView view, WebResourceRequest req) {
            Uri u = req.getUrl();
            String p = u.getPath();
            if (req.isForMainFrame() && "GET".equals(req.getMethod()) && isOurs(u)
                && (p == null || p.isEmpty() || "/".equals(p) || "/index.html".equals(p))) {
                return pageWithWindowFunctions(u);
            }
            return null;
        }

        @Override
        public boolean shouldOverrideUrlLoading(WebView view, WebResourceRequest req) {
            if (isOurs(req.getUrl())) return false;
            try {
                openOutside(req.getUrl().toString()); // other sites and mail addresses: not inside the window
            } catch (ActivityNotFoundException e) {
                launcher.log("no app for " + req.getUrl());
            }
            return true;
        }

        @Override
        public void onPageFinished(WebView view, String url) {
            if (isOurs(Uri.parse(url))) {
                pageShown = true;
                overlay.setVisibility(View.GONE);
                matchBars();
            }
        }

        @Override
        public void onReceivedError(WebView view, WebResourceRequest req, WebResourceError err) {
            if (req.isForMainFrame()) {
                launcher.log("page error: " + err.getDescription());
                pageShown = false;
                showOverlay(Texts.failed(lang) + "\n" + err.getDescription(), true);
            }
        }

        @Override
        public boolean onRenderProcessGone(WebView view, RenderProcessGoneDetail detail) {
            // the page's process ended (Android needed its memory): a new WebView, the launcher keeps running
            launcher.log("the page's process ended" + (detail.didCrash() ? " (crash)" : " (memory)") + ", " + memInfo());
            root.removeView(view);
            view.destroy();
            web = new WebView(MainActivity.this);
            setUpWebView(web);
            root.addView(web, 0, new FrameLayout.LayoutParams(ViewGroup.LayoutParams.MATCH_PARENT, ViewGroup.LayoutParams.MATCH_PARENT));
            pageShown = false;
            start();
            return true;
        }
    }

    /** The launcher's index.html with the window functions put in before the page's own scripts. */
    private WebResourceResponse pageWithWindowFunctions(Uri u) {
        try {
            HttpURLConnection c = (HttpURLConnection) new URL(u.toString()).openConnection();
            c.setConnectTimeout(3000);
            c.setReadTimeout(15000);
            try {
                if (c.getResponseCode() != 200) return null;
                String html = Launcher.readAll(c.getInputStream());
                int i = html.indexOf("<head>");
                html = i >= 0 ? html.substring(0, i + 6) + "\n" + WINDOW_FUNCTIONS + html.substring(i + 6) : WINDOW_FUNCTIONS + html;
                Map<String, String> headers = new HashMap<>();
                headers.put("Cache-Control", "no-store");
                return new WebResourceResponse("text/html", "utf-8", 200, "OK", headers,
                    new ByteArrayInputStream(html.getBytes(StandardCharsets.UTF_8)));
            } finally {
                c.disconnect();
            }
        } catch (IOException e) {
            launcher.log("page: " + e.getMessage());
            return null; // the WebView asks the launcher itself: the page then works as in a browser tab
        }
    }

    /** The colour of the system bars follows the theme of the page (light or dark). */
    private void matchBars() {
        web.evaluateJavascript("document.documentElement.getAttribute('data-theme')", v -> {
            boolean dark = v != null && v.contains("dark");
            int bg = Color.parseColor(dark ? "#1c1b1a" : "#f5f4ef");
            root.setBackgroundColor(bg);
            getWindow().setStatusBarColor(bg);
            getWindow().setNavigationBarColor(bg);
            if (Build.VERSION.SDK_INT >= 30) {
                WindowInsetsController ic = getWindow().getInsetsController();
                if (ic != null) {
                    int light = WindowInsetsController.APPEARANCE_LIGHT_STATUS_BARS | WindowInsetsController.APPEARANCE_LIGHT_NAVIGATION_BARS;
                    ic.setSystemBarsAppearance(dark ? 0 : light, light);
                }
            }
        });
    }

    private class Chrome extends WebChromeClient {
        @Override
        public boolean onShowFileChooser(WebView view, ValueCallback<Uri[]> cb, FileChooserParams params) {
            // import of glossaries and saved translations: the system's file picker (all files: .tsv is often unknown)
            if (openCallback != null) openCallback.onReceiveValue(null);
            openCallback = cb;
            Intent i = new Intent(Intent.ACTION_OPEN_DOCUMENT);
            i.addCategory(Intent.CATEGORY_OPENABLE);
            i.setType("*/*");
            try {
                startActivityForResult(i, REQ_OPEN);
            } catch (ActivityNotFoundException e) {
                openCallback = null;
                cb.onReceiveValue(null);
            }
            return true;
        }

        @Override
        public boolean onConsoleMessage(ConsoleMessage m) {
            Log.i(Launcher.TAG, "page: " + m.message() + " (" + m.sourceId() + ":" + m.lineNumber() + ")");
            return true;
        }
    }

    @Override
    protected void onActivityResult(int req, int result, Intent data) {
        super.onActivityResult(req, result, data);
        Uri uri = result == RESULT_OK && data != null ? data.getData() : null;
        if (req == REQ_OPEN && openCallback != null) {
            openCallback.onReceiveValue(uri != null ? new Uri[]{uri} : null);
            openCallback = null;
        } else if (req == REQ_SAVE) {
            final int id = saveId;
            final String text = saveText;
            saveText = null;
            if (uri == null || text == null) {
                done(id, "{\"cancelled\":true}");
                return;
            }
            work.execute(() -> {
                try (OutputStream out = getContentResolver().openOutputStream(uri, "wt")) {
                    if (out == null) throw new IOException("no file");
                    out.write(text.getBytes(StandardCharsets.UTF_8));
                    done(id, json("path", displayName(uri)));
                } catch (IOException | SecurityException e) {
                    done(id, json("error", String.valueOf(e.getMessage())));
                }
            });
        }
    }

    private String displayName(Uri uri) {
        try (Cursor c = getContentResolver().query(uri, new String[]{OpenableColumns.DISPLAY_NAME}, null, null, null)) {
            if (c != null && c.moveToFirst()) return c.getString(0);
        } catch (RuntimeException e) {
            // the address below
        }
        return uri.getLastPathSegment();
    }

    private static String json(String key, String value) {
        try {
            return new JSONObject().put(key, value).toString();
        } catch (JSONException e) {
            return "{}";
        }
    }

    /** Answers a window function of the page. */
    private void done(int id, String resultJson) {
        ui.post(() -> {
            if (web != null) web.evaluateJavascript("window.__ttwDone && window.__ttwDone(" + id + "," + resultJson + ")", null);
        });
    }

    private void openOutside(String url) {
        Intent i = new Intent(url.startsWith("mailto:") ? Intent.ACTION_SENDTO : Intent.ACTION_VIEW, Uri.parse(url));
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK);
        startActivity(i);
    }

    /** The bridge behind the window functions (called on a thread of the WebView). */
    private class Bridge {
        @JavascriptInterface
        public void saveFile(int id, String name, String text, String ext, String label) {
            ui.post(() -> {
                if (saveText != null) done(saveId, "{\"cancelled\":true}"); // only one "Save as" at a time
                saveId = id;
                saveText = text;
                Intent i = new Intent(Intent.ACTION_CREATE_DOCUMENT);
                i.addCategory(Intent.CATEGORY_OPENABLE);
                i.setType("txt".equals(ext) ? "text/plain" : "tsv".equals(ext) ? "text/tab-separated-values" : "application/octet-stream");
                i.putExtra(Intent.EXTRA_TITLE, name);
                try {
                    startActivityForResult(i, REQ_SAVE);
                } catch (ActivityNotFoundException e) {
                    saveText = null;
                    done(id, json("error", Texts.noApp(lang)));
                }
            });
        }

        @JavascriptInterface
        public void openExternal(int id, String url) {
            ui.post(() -> {
                try {
                    openOutside(url);
                    done(id, "{}");
                } catch (ActivityNotFoundException e) {
                    done(id, json("error", Texts.noApp(lang)));
                }
            });
        }

        @JavascriptInterface
        public void close(int id) {
            ui.post(() -> {
                done(id, "{}");
                launcher.log("the page closed the window (Exit)");
                finishAndRemoveTask();
            });
        }
    }

    // ------------------------------------------------------------ for the logs (data/logs/android.log)

    private String memInfo() {
        ActivityManager am = getSystemService(ActivityManager.class);
        ActivityManager.MemoryInfo mi = new ActivityManager.MemoryInfo();
        am.getMemoryInfo(mi);
        return String.format(java.util.Locale.ROOT, "memory: %.1f of %.1f GB free%s", mi.availMem / 1e9, mi.totalMem / 1e9,
            mi.lowMemory ? ", low" : "");
    }

    private void logDevice() {
        String webView = "?";
        PackageInfo wv = WebView.getCurrentWebViewPackage();
        if (wv != null) webView = wv.packageName + " " + wv.versionName;
        launcher.log("start: " + Build.MANUFACTURER + " " + Build.MODEL + ", Android " + Build.VERSION.RELEASE
            + " (API " + Build.VERSION.SDK_INT + "), " + String.join(",", Build.SUPPORTED_ABIS) + ", libraries "
            + launcher.libDir + ", WebView " + webView + ", " + memInfo());
    }
}
