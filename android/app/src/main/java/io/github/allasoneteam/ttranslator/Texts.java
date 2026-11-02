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
}
