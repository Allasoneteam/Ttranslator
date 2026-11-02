package io.github.allasoneteam.ttranslator;

import android.content.Context;
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
 * connected by USB sees it, so models can also be copied there instead of being downloaded.
 */
final class Launcher {
    static final String TAG = "Ttranslator";
    static final int PORT = 8765;
    static final String URL = "http://127.0.0.1:" + PORT + "/";
    /** the version of sherpa-onnx whose libraries are in the APK (android/build.sh) */
    static final String TTS_VERSION = "v1.13.7";

    private static Process process; // the launcher started by this app process
    private static final ArrayDeque<String> lastOutput = new ArrayDeque<>();

    final File root;
    final String libDir;
    private final File cacheDir, homeDir;

    Launcher(Context c) {
        File ext = c.getExternalFilesDir(null);
        root = ext != null ? ext : new File(c.getFilesDir(), "Ttranslator");
        libDir = c.getApplicationInfo().nativeLibraryDir;
        cacheDir = c.getCacheDir();
        homeDir = c.getFilesDir();
    }

    /** Does a Ttranslator launcher answer on the port (started now or before the window was opened again)? */
    static boolean alive() {
        try {
            HttpURLConnection c = (HttpURLConnection) new URL(URL + "api/ping").openConnection();
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

    /** Prepares the program folder and starts the launcher unless one answers; waits until it answers. */
    synchronized void ensureRunning() throws IOException {
        if (alive()) return;
        prepare();
        ProcessBuilder pb = new ProcessBuilder(libDir + "/libttranslator.so", "--no-window");
        Map<String, String> env = pb.environment();
        env.put("TDOC_ROOT", root.getAbsolutePath());
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
        }
        Thread t = new Thread(() -> drain(p), "launcher-output");
        t.setDaemon(true);
        t.start();
        long until = SystemClock.elapsedRealtime() + 30_000;
        while (!alive()) {
            if (!p.isAlive()) {
                throw new IOException("exit code " + p.exitValue() + "\n" + lastLines());
            }
            if (SystemClock.elapsedRealtime() > until) {
                throw new IOException("no answer in 30 s\n" + lastLines());
            }
            SystemClock.sleep(150);
        }
        log("the launcher answers at " + URL);
    }

    /**
     * config.json: the engine is llama-server in the app's library folder (engine_path; the folder changes with every
     * update of the app, so it is written at every start). A new config.json gets "ui_language": "en" — the
     * launcher reads a config.json without it as one of a version before 0.6 (Russian).
     * engine/android-&lt;arch&gt;/tts.json: the reading-aloud program, with a path relative to that folder (as the
     * launcher reads it).
     */
    void prepare() throws IOException {
        if (!root.isDirectory() && !root.mkdirs()) throw new IOException("cannot create " + root);
        File cfg = new File(root, "config.json");
        try {
            JSONObject o = cfg.isFile() ? new JSONObject(readAll(Files.newInputStream(cfg.toPath()))) : new JSONObject();
            if (!cfg.isFile()) {
                o.put("ui_language", "en");
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
