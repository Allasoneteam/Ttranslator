package io.github.allasoneteam.ttranslator;

import android.app.Notification;
import android.app.NotificationChannel;
import android.app.NotificationManager;
import android.app.PendingIntent;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.content.pm.ServiceInfo;
import android.os.Build;
import android.os.IBinder;
import android.os.SystemClock;

import org.json.JSONException;
import org.json.JSONObject;

import java.io.IOException;
import java.net.HttpURLConnection;

/**
 * The notification while Ttranslator works (1.2, the author's decision of 14.11.2026): a download (a model, a voice) or
 * the engine at work (a translation, a question to the model, the test). As a foreground service it keeps the app
 * running in the background: without it Android (Xiaomi especially) stops a long download or a translation when the
 * user switches to another app. The service watches the launcher (/api/state: download, tts.download, engine_busy)
 * and ends a few seconds after the work is over.
 */
public class WorkService extends Service {
    static final String CHANNEL = "work";
    private static final int NOTIFICATION = 1;
    /** the work may pause between two requests (the test, the variants one after another): end only after this */
    private static final long IDLE_MS = 8_000;

    private static volatile boolean running;
    private volatile boolean stop;
    private Thread watcher;

    /**
     * The page has started work (MainActivity sees its requests): the service starts unless it runs already. Android 12+
     * lets an app start one only while it is in front — it is: the user has just pressed a button.
     */
    static void begin(Context c) {
        if (running) return;
        try {
            c.startForegroundService(new Intent(c, WorkService.class));
        } catch (RuntimeException e) {
            // not allowed now (the app in the background): the work goes on without the notification
        }
    }

    @Override
    public int onStartCommand(Intent intent, int flags, int startId) {
        String lang = new Launcher(this).uiLanguage();
        Notification n = build(lang, Texts.working(lang), -1);
        try {
            if (Build.VERSION.SDK_INT >= 34) {
                startForeground(NOTIFICATION, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC
                    | ServiceInfo.FOREGROUND_SERVICE_TYPE_SPECIAL_USE);
            } else if (Build.VERSION.SDK_INT >= 29) {
                startForeground(NOTIFICATION, n, ServiceInfo.FOREGROUND_SERVICE_TYPE_DATA_SYNC);
            } else {
                startForeground(NOTIFICATION, n);
            }
        } catch (RuntimeException e) {
            stopSelf();
            return START_NOT_STICKY;
        }
        running = true;
        if (watcher == null) {
            watcher = new Thread(() -> watch(lang), "work-notification");
            watcher.setDaemon(true);
            watcher.start();
        }
        return START_NOT_STICKY;
    }

    /** Every 1.5 s: what the launcher is doing — the text and the progress of the notification; the end of the work. */
    private void watch(String lang) {
        NotificationManager nm = getSystemService(NotificationManager.class);
        long idleSince = SystemClock.elapsedRealtime();
        String last = "";
        while (!stop) {
            String text = null;
            int pct = -1;
            try {
                JSONObject s = state();
                JSONObject d = s.optJSONObject("download");
                JSONObject t = s.optJSONObject("tts");
                JSONObject v = t != null ? t.optJSONObject("download") : null;
                if (d != null && d.optBoolean("active")) {
                    text = Texts.downloading(lang, d.optString("name"));
                    pct = percent(d);
                } else if (v != null && v.optBoolean("active")) {
                    text = Texts.downloadingVoice(lang, v.optString("name"));
                    pct = percent(v);
                } else if (s.optBoolean("engine_busy")) {
                    text = Texts.working(lang);
                }
            } catch (IOException | JSONException e) {
                // the launcher has ended (Exit) or does not answer: as idle
            }
            long now = SystemClock.elapsedRealtime();
            if (text != null) {
                idleSince = now;
                String key = text + pct;
                if (!key.equals(last)) {
                    last = key;
                    nm.notify(NOTIFICATION, build(lang, text, pct));
                }
            } else if (now - idleSince > IDLE_MS) {
                break;
            }
            SystemClock.sleep(1500);
        }
        running = false;
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelf();
    }

    private static int percent(JSONObject d) {
        long total = d.optLong("total"), done = d.optLong("done");
        return total > 0 ? (int) Math.min(100, done * 100 / total) : -1;
    }

    private static JSONObject state() throws IOException, JSONException {
        HttpURLConnection c = Launcher.open("api/state");
        c.setConnectTimeout(2000);
        c.setReadTimeout(5000);
        try {
            if (c.getResponseCode() != 200) throw new IOException("HTTP " + c.getResponseCode());
            return new JSONObject(Launcher.readAll(c.getInputStream()));
        } finally {
            c.disconnect();
        }
    }

    /** The notification: Ttranslator, what it is doing, the progress of a download; a tap opens the app. */
    private Notification build(String lang, String text, int pct) {
        NotificationManager nm = getSystemService(NotificationManager.class);
        if (nm.getNotificationChannel(CHANNEL) == null) {
            NotificationChannel ch = new NotificationChannel(CHANNEL, Texts.channel(lang), NotificationManager.IMPORTANCE_LOW);
            ch.setShowBadge(false);
            nm.createNotificationChannel(ch);
        }
        Intent open = new Intent(this, MainActivity.class).addFlags(Intent.FLAG_ACTIVITY_SINGLE_TOP);
        PendingIntent pi = PendingIntent.getActivity(this, 0, open, PendingIntent.FLAG_IMMUTABLE | PendingIntent.FLAG_UPDATE_CURRENT);
        Notification.Builder b = new Notification.Builder(this, CHANNEL)
            .setSmallIcon(R.drawable.ic_launcher_foreground)
            .setContentTitle("Ttranslator")
            .setContentText(text)
            .setContentIntent(pi)
            .setOngoing(true)
            .setOnlyAlertOnce(true)
            .setCategory(Notification.CATEGORY_PROGRESS);
        if (pct >= 0) b.setProgress(100, pct, false);
        else if (!text.equals(Texts.working(lang))) b.setProgress(0, 0, true);
        if (Build.VERSION.SDK_INT >= 31) b.setForegroundServiceBehavior(Notification.FOREGROUND_SERVICE_IMMEDIATE);
        return b.build();
    }

    /** Android 15+: a data-sync service may run 6 hours a day — never reached by a download, but end then. */
    @Override
    public void onTimeout(int startId, int fgsType) {
        stop = true;
        running = false;
        stopForeground(STOP_FOREGROUND_REMOVE);
        stopSelf();
    }

    @Override
    public void onDestroy() {
        stop = true;
        running = false;
        super.onDestroy();
    }

    @Override
    public IBinder onBind(Intent intent) {
        return null;
    }
}
