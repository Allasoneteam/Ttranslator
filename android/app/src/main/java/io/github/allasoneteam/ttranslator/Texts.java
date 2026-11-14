package io.github.allasoneteam.ttranslator;

/**
 * The few texts of the Android window itself, in the five interface languages (the language of config.json). Everything
 * else is the page ui/index.html with its own translations.
 */
final class Texts {
    private Texts() {}

    // English, Russian, German, Spanish, Chinese (simplified)
    private static final String[] STARTING = {
        "Starting Ttranslator…", "Запуск Ttranslator…", "Ttranslator wird gestartet…", "Iniciando Ttranslator…",
        "正在启动 Ttranslator…"};
    private static final String[] FAILED = {
        "Ttranslator could not start:", "Не удалось запустить Ttranslator:", "Ttranslator konnte nicht gestartet werden:",
        "No se pudo iniciar Ttranslator:", "无法启动 Ttranslator："};
    private static final String[] RETRY = {"Try again", "Повторить", "Erneut versuchen", "Reintentar", "重试"};
    private static final String[] NO_APP = {
        "no app can open it", "нет приложения, которое может это открыть", "keine App kann das öffnen",
        "ninguna aplicación puede abrirlo", "没有可以打开它的应用"};
    // {v}: the installed version of the WebView
    private static final String[] OLD_WEBVIEW = {
        "Ttranslator needs a newer “Android System WebView” (version 80 or later; installed: {v}). Please update it in Google Play.",
        "Ttranslator нужна более новая версия «Android System WebView» (80 или новее; сейчас {v}). Обновите её в Google Play.",
        "Ttranslator benötigt eine neuere Version von „Android System WebView“ (80 oder neuer; installiert: {v}). Bitte in Google Play aktualisieren.",
        "Ttranslator necesita una versión más reciente de «Android System WebView» (80 o posterior; instalada: {v}). Actualícela en Google Play.",
        "Ttranslator 需要更新版本的“Android System WebView”（80 或更高版本；当前：{v}）。请在 Google Play 中更新。"};
    private static final String[] OPEN_PLAY = {
        "Open Google Play", "Открыть Google Play", "Google Play öffnen", "Abrir Google Play", "打开 Google Play"};

    private static int col(String lang) {
        switch (lang) {
            case "ru": return 1;
            case "de": return 2;
            case "es": return 3;
            case "zh": return 4;
            default: return 0;
        }
    }

    static String starting(String lang) { return STARTING[col(lang)]; }
    static String failed(String lang) { return FAILED[col(lang)]; }
    static String retry(String lang) { return RETRY[col(lang)]; }
    static String noApp(String lang) { return NO_APP[col(lang)]; }
    static String oldWebView(String lang, String version) { return OLD_WEBVIEW[col(lang)].replace("{v}", version); }
    static String openPlay(String lang) { return OPEN_PLAY[col(lang)]; }
}
