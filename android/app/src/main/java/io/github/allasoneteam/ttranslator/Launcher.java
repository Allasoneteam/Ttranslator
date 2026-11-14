package io.github.allasoneteam.ttranslator;

import android.content.Context;
import android.content.pm.ApplicationInfo;
import android.content.res.AssetManager;
import android.os.Build;
import android.os.SystemClock;
import android.util.Log;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.BufferedReader;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.FileOutputStream;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.io.Writer;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.security.SecureRandom;
import java.text.SimpleDateFormat;
import java.util.ArrayDeque;
import java.util.Date;
import java.util.Locale;
import java.util.Map;

/**
 * The Ttranslator launcher on Android: the same Go program as on a computer (source/launcher), built for Android and
 * packed into the APK as libttranslator.so. Android starts an app's programs only from the app's library folder
 * (nativeLibraryDir), so the engine (llama-server of the official llama.cpp release for Android) and the
 * reading-aloud program are there too, as lib*.so files.
 *
 * The program folder (TDOC_ROOT) is the app's folder on the shared storage, Android/data/&lt;app&gt;/files: config.json,
 * data/ (saved translations, glossaries, test reports, logs), models/ (models and voices) and engine/. A computer
 * connected by USB sees it. On Android 9 and 10 other apps with the storage permission could read Android/data, so
 * there the folder is in the app's own internal storage (files/Ttranslator).
 *
 * Access (1.2): other apps of the phone can reach 127.0.0.1 too. At every start of the launcher the app makes a random
 * key and gives it to the launcher (TDOC_ACCESS_KEY), which then answers only requests with it: the window gets it in
 * a cookie, the app's own requests in the header X-Tdoc-Key. The launcher writes the port it really listens on into a
 * file in the app's private folder (TDOC_PORT_FILE): the window opens exactly this launcher.
 */
final class Launcher {
    static final String TAG = "Ttranslator";
    /** the port of config.json; another one only when it is taken (the port file says which) */
    static final int PORT = 8765;
    /** the cookie of the window with the access key (source/launcher/android.go) */
    static final String ACCESS_COOKIE = "tdoc_key";
    /** the version of sherpa-onnx whose libraries are in the APK (android/build.sh) */
    static final String TTS_VERSION = "v1.13.7";

    private static Process process; // the launcher started by this app process
    private static final ArrayDeque<String> lastOutput = new ArrayDeque<>();
    private static int port = PORT;          // the port of that launcher
    private static String accessKey = "";    // ...and its access key

    final File root;
    final String libDir;
    private final File cacheDir, homeDir, portFile, keyFile;
    private final AssetManager assets;
    /** the test APK: keeps a copy of the access key in its private folder for the check in the emulator (run-as) */
    private final boolean debuggable;

    Launcher(Context c) {
        File ext = Build.VERSION.SDK_INT >= 30 ? c.getExternalFilesDir(null) : null;
        root = ext != null ? ext : new File(c.getFilesDir(), "Ttranslator");
        libDir = c.getApplicationInfo().nativeLibraryDir;
        cacheDir = c.getCacheDir();
        homeDir = c.getFilesDir();
        portFile = new File(homeDir, "launcher.port");
        keyFile = new File(homeDir, "launcher.key");
        debuggable = (c.getApplicationInfo().flags & ApplicationInfo.FLAG_DEBUGGABLE) != 0;
        assets = c.getAssets();
    }

    /** The address of the launcher's page. */
    static synchronized String url() {
        return "http://127.0.0.1:" + port + "/";
    }

    static synchronized int port() {
        return port;
    }

    static synchronized String accessKey() {
        return accessKey;
    }

    /** Opens a request to the launcher of this app, with the access key. */
    static HttpURLConnection open(String path) throws IOException {
        HttpURLConnection c = (HttpURLConnection) new URL(url() + path).openConnection();
        c.setRequestProperty("X-Tdoc-Key", accessKey());
        return c;
    }

    /** Does the launcher started by this app answer (with our key)? */
    static boolean alive() {
        if (accessKey().isEmpty()) return false;
        try {
            HttpURLConnection c = open("api/ping");
            c.setConnectTimeout(1000);
            c.setReadTimeout(2000);
            try {
                return c.getResponseCode() == 200 && readAll(c.getInputStream()).contains("tdoc-translator");
            } finally {
                c.disconnect();
            }
        } catch (IOException e) {
            return false;
        }
    }

    static synchronized boolean ownProcessAlive() {
        return process != null && process.isAlive();
    }

    /** Prepares the program folder and starts the launcher unless ours answers; waits until it answers. */
    synchronized void ensureRunning() throws IOException {
        if (ownProcessAlive() && alive()) return;
        synchronized (Launcher.class) {
            if (process != null && process.isAlive()) {
                log("the launcher does not answer: stopping it");
                process.destroy();
            }
        }
        prepare();
        String key = newKey();
        for (File f : new File[]{portFile, keyFile}) {
            if (f.exists() && !f.delete()) throw new IOException("cannot remove " + f);
        }
        ProcessBuilder pb = new ProcessBuilder(libDir + "/libttranslator.so", "--no-window");
        Map<String, String> env = pb.environment();
        env.put("TDOC_ROOT", root.getAbsolutePath());
        env.put("TDOC_ACCESS_KEY", key);
        env.put("TDOC_PORT_FILE", portFile.getAbsolutePath());
        // the device for the test reports (the launcher would see only "Linux" and no processor name)
        env.put("TDOC_OS", "Android " + Build.VERSION.RELEASE + " (" + Build.MANUFACTURER + " " + Build.MODEL + ")");
        String soc = Build.HARDWARE;
        if (Build.VERSION.SDK_INT >= 31) soc = (Build.SOC_MANUFACTURER + " " + Build.SOC_MODEL).trim();
        if (soc != null && !soc.isEmpty() && !soc.toLowerCase(Locale.ROOT).contains("unknown")) env.put("TDOC_CPU", soc);
        // the engine's and the reading-aloud program's libraries are next to them (the launcher adds the folder too)
        env.put("LD_LIBRARY_PATH", libDir);
        env.put("TMPDIR", cacheDir.getAbsolutePath());
        env.put("HOME", homeDir.getAbsolutePath());
        // HTTPS of the downloads: Go reads the system's certificates from /system/etc/security/cacerts; since Android
        // 14 the current ones (updated through Google Play) are in the Conscrypt module — both, the newer first
        StringBuilder certs = new StringBuilder();
        for (String d : new String[]{"/apex/com.android.conscrypt/cacerts", "/system/etc/security/cacerts"}) {
            if (new File(d).isDirectory()) certs.append(certs.length() > 0 ? ":" : "").append(d);
        }
        if (certs.length() > 0) env.put("SSL_CERT_DIR", certs.toString());
        pb.directory(root);
        pb.redirectErrorStream(true);
        log("starting the launcher: " + libDir + "/libttranslator.so, folder " + root);
        final Process p = pb.start();
        synchronized (Launcher.class) {
            process = p;
            lastOutput.clear();
            accessKey = key;
            port = PORT;
        }
        if (debuggable) writeAtomically(keyFile, key);
        Thread t = new Thread(() -> drain(p), "launcher-output");
        t.setDaemon(true);
        t.start();
        long until = SystemClock.elapsedRealtime() + 30_000;
        boolean havePort = false;
        while (!havePort || !alive()) {
            if (!havePort && portFile.isFile()) {
                try {
                    int n = Integer.parseInt(readAll(Files.newInputStream(portFile.toPath())).trim());
                    synchronized (Launcher.class) {
                        port = n;
                    }
                    havePort = true;
                    if (n != PORT) log("the port " + PORT + " is taken: the launcher listens on " + n);
                } catch (NumberFormatException | IOException e) {
                    // written whole by the launcher (rename): read again
                }
            }
            if (!p.isAlive()) {
                throw new IOException("exit code " + p.exitValue() + "\n" + lastLines());
            }
            if (SystemClock.elapsedRealtime() > until) {
                throw new IOException("no answer in 30 s\n" + lastLines());
            }
            SystemClock.sleep(150);
        }
        log("the launcher answers at " + url());
    }

    /** A new random access key: 24 bytes, as hex. */
    private static String newKey() {
        byte[] b = new byte[24];
        new SecureRandom().nextBytes(b);
        StringBuilder s = new StringBuilder();
        for (byte x : b) s.append(String.format(Locale.ROOT, "%02x", x & 0xff));
        return s.toString();
    }

    /**
     * config.json: the engine is llama-server in the app's library folder (engine_path; the folder changes with every
     * update of the app, so it is written at every start). A new config.json gets the phone's language as
     * "ui_language" if it is one of the five of the interface, else English (the author's decision of 14.11.2026) —
     * the launcher reads a config.json without it as one of a version before 0.6 (Russian).
     * engine/android-&lt;arch&gt;/tts.json: the reading-aloud program, with a path relative to that folder (as the
     * launcher reads it).
     */
    void prepare() throws IOException {
        if (!root.isDirectory() && !root.mkdirs()) throw new IOException("cannot create " + root);
        File cfg = new File(root, "config.json");
        try {
            JSONObject o = cfg.isFile() ? new JSONObject(readAll(Files.newInputStream(cfg.toPath()))) : new JSONObject();
            if (!cfg.isFile()) {
                o.put("ui_language", phoneLanguage());
                // llama.cpp takes all cores by default; on a phone the small ones slow the generation down
                int big = bigCores();
                if (big > 0) o.put("threads", big);
            }
            o.put("engine_path", libDir + "/libllama-server.so");
            writeAtomically(cfg, o.toString(2) + "\n");
        } catch (JSONException e) {
            // a damaged config.json: the launcher itself falls back to the defaults and rewrites it
            log("config.json: " + e.getMessage());
        }
        // ui/tests.txt (the pairs of «Подробный тест») and ui/THIRD-PARTY.txt (the licences, «О программе»): from the APK
        // next to the page, where the launcher serves them (the page itself is inside the launcher); every start, so
        // an update of the app brings its own
        File ui = new File(root, "ui");
        if (!ui.isDirectory() && !ui.mkdirs()) throw new IOException("cannot create " + ui);
        for (String name : new String[]{"tests.txt", "THIRD-PARTY.txt"}) {
            try (InputStream in = assets.open(name)) {
                writeAtomically(new File(ui, name), readAll(in));
            } catch (IOException e) {
                log("asset " + name + ": " + e.getMessage());
            }
        }
        File engineDir = new File(root, "engine/android-" + goArch());
        if (!engineDir.isDirectory() && !engineDir.mkdirs()) throw new IOException("cannot create " + engineDir);
        File tts = new File(libDir, "libsherpa-onnx-offline-tts.so");
        if (tts.isFile()) {
            try {
                JSONObject m = new JSONObject();
                m.put("version", TTS_VERSION + "-android");
                m.put("exe", relative(engineDir, tts));
                writeAtomically(new File(engineDir, "tts.json"), m.toString(2) + "\n");
            } catch (JSONException e) {
                throw new IOException(e);
            }
        }
    }

    /**
     * The number of cores for the engine (config.json "threads", written once, with a new config.json): all but the small
     * energy-saving ones ("CPU part" in /proc/cpuinfo). A phone has 8 cores, often 4 of them small; generation with 8 threads is then about 40 % slower
     * than with 4 (open measurements of llama.cpp on a Snapdragon 778G). 0: unknown (the engine decides).
     */
    static int bigCores() {
        int all = 0, small = 0;
        try {
            for (String line : readAll(Files.newInputStream(new File("/proc/cpuinfo").toPath())).split("\n")) {
                if (!line.startsWith("CPU part")) continue;
                all++;
                String part = line.substring(line.indexOf(':') + 1).trim().toLowerCase(Locale.ROOT);
                // Arm Cortex-A53, A55, A510, A520; Qualcomm Kryo "Silver" (0x801, 0x803, 0x805: older Snapdragons)
                switch (part) {
                    case "0xd03": case "0xd05": case "0xd46": case "0xd80":
                    case "0x801": case "0x803": case "0x805":
                        small++;
                        break;
                    default:
                        break;
                }
            }
        } catch (IOException e) {
            return 0;
        }
        if (all == 0) return 0; // not ARM (the emulator): the engine decides
        return all - small > 0 ? all - small : all;
    }

    /** The interface language of a new installation: the phone's, if it is one of the five of the interface. */
    static String phoneLanguage() {
        String l = Locale.getDefault().getLanguage();
        switch (l) {
            case "ru": case "de": case "es": case "zh":
                return l;
            default:
                return "en";
        }
    }

    /** The architecture name of Go (runtime.GOARCH) for the app's library folder: lib/arm64 or lib/x86_64. */
    String goArch() {
        String abi = new File(libDir).getName();
        return abi.equals("x86_64") ? "amd64" : abi;
    }

    /** The interface language of config.json (for the few texts of the app itself). */
    String uiLanguage() {
        try {
            File cfg = new File(root, "config.json");
            if (cfg.isFile()) return new JSONObject(readAll(Files.newInputStream(cfg.toPath()))).optString("ui_language", "en");
        } catch (IOException | JSONException e) {
            // the default below
        }
        return "en";
    }

    static String relative(File from, File to) {
        String[] a = from.getAbsolutePath().split("/"), b = to.getAbsolutePath().split("/");
        int i = 0;
        while (i < a.length && i < b.length && a[i].equals(b[i])) i++;
        StringBuilder s = new StringBuilder();
        for (int j = i; j < a.length; j++) s.append("../");
        for (int j = i; j < b.length; j++) s.append(b[j]).append(j + 1 < b.length ? "/" : "");
        return s.toString();
    }

    private void drain(Process p) {
        try (BufferedReader r = new BufferedReader(new InputStreamReader(p.getInputStream(), StandardCharsets.UTF_8))) {
            String line;
            while ((line = r.readLine()) != null) {
                Log.i(TAG, "launcher: " + line);
                synchronized (Launcher.class) {
                    lastOutput.addLast(line);
                    while (lastOutput.size() > 20) lastOutput.removeFirst();
                }
            }
        } catch (IOException e) {
            // the launcher has ended
        }
        try {
            log("the launcher ended, code " + p.waitFor());
        } catch (InterruptedException e) {
            Thread.currentThread().interrupt();
        }
    }

    private static synchronized String lastLines() {
        return String.join("\n", lastOutput);
    }

    /** A line in logcat and in data/logs/android.log (next to the launcher's own log). */
    void log(String msg) {
        Log.i(TAG, msg);
        File dir = new File(root, "data/logs");
        if (!dir.isDirectory() && !dir.mkdirs()) return;
        File f = new File(dir, "android.log");
        if (f.length() > 512 * 1024) f.delete();
        String ts = new SimpleDateFormat("yyyy/MM/dd HH:mm:ss", Locale.ROOT).format(new Date());
        try (Writer w = new OutputStreamWriter(new FileOutputStream(f, true), StandardCharsets.UTF_8)) {
            w.write(ts + " " + msg + "\n");
        } catch (IOException e) {
            // logging must not break the app
        }
    }

    static String readAll(InputStream in) throws IOException {
        try (InputStream is = in) {
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            byte[] buf = new byte[16384];
            int n;
            while ((n = is.read(buf)) > 0) out.write(buf, 0, n);
            return out.toString("UTF-8");
        }
    }

    private static void writeAtomically(File f, String text) throws IOException {
        File tmp = new File(f.getPath() + ".tmp");
        try (FileOutputStream out = new FileOutputStream(tmp)) {
            out.write(text.getBytes(StandardCharsets.UTF_8));
            out.getFD().sync();
        }
        if (!tmp.renameTo(f)) throw new IOException("cannot write " + f);
    }
}
