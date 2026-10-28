#!/usr/bin/env python3
# Does every voice of the catalogue read what it is given? Speaks test phrases with each voice (the official
# sherpa-onnx program for Linux, with the same options as the app), transcribes the speech with Whisper (the
# "base" model, run by sherpa-onnx) and reports, per voice, how long the speech is per character and how many
# words the recogniser got wrong.
#
#   python3 source/tests/voice_check.py [work-dir] [voice-id ...] [--keep] [--verbose] [--voices=FILE]
#
# Not part of run_all.sh: the first run downloads about 1 GB from github.com into the work dir (default
# /tmp/tdoc-voices): sherpa-onnx, Whisper base (208 MB) and every voice of the catalogue (60–115 MB each); the
# archives of run_all.sh are used if the work dir is the same. Run it before a voice goes into the catalogue
# (voiceSpecs in tts.go, read here through TestDumpVoiceCatalog) and after a new sherpa-onnx version.
# --keep keeps the WAV files (<work>/speech/) to listen to; --verbose shows every phrase; --voices=FILE checks the
# voices of a JSON list (VoiceSpec fields, as in the catalogue) instead — a candidate before it goes into tts.go.
#
# Why: es_ES-mls_9972-low (0.9.3) read short phrases as invented words, two to five times too long. The program and
# its tests were fine — only listening, or a recogniser, shows such a voice.
#
# Every language has eight phrases: two short ones and six of four words and more (Chinese: six characters and
# more). Only the six longer ones are scored — Whisper base often mishears a lone word; the short ones are spoken
# and listed (--verbose) to listen to. Verdict per voice: "ok", or "SLOW" (speech much longer than the text needs:
# more than 0.09 s per character of text on average, or one phrase over 0.16 s per character; Chinese, where a
# character is a whole syllable: 0.45 and 0.60 s) and/or "WORDS" (more than 60 % of the words wrong on average;
# Chinese: characters). A voice that reads another language (1.0: Latin by the Italian voice Paola, in Italian
# spelling as the app gives it) is heard by Whisper in its own language, which writes Italian words for Latin ones —
# there the letters are compared instead of the words (60 % too); measured: Paola 0.054–0.055 s per character, 39–44 %
# of the letters wrong with the church pronunciation, 48 % with the classical one (its own copy of the model with the
# espeak-ng voice "la", made here as the app makes it; Whisper hears Italian in both) — the words: over 100 %. Measured in October 2026: the voices of the catalogue and seven other Spanish voices
# 0.049–0.067 s per character (worst phrase 0.076), 0–34 % errors (Whisper base hears Russian worst);
# es_ES-mls_9972-low 0.115–0.123 s per character (worst phrase 0.23–0.27), 106–132 % errors. Speech differs a little
# from run to run (VITS draws noise), and so do the numbers. Exit code 1 if a voice is not "ok".
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import unicodedata
import urllib.request
import wave

HERE = os.path.dirname(os.path.abspath(__file__))
LAUNCHER = os.path.join(os.path.dirname(HERE), "launcher")
APP = os.path.dirname(os.path.dirname(HERE))
WHISPER = {"url": "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/sherpa-onnx-whisper-base.tar.bz2",
           "file": "sherpa-onnx-whisper-base.tar.bz2", "size": 207557382,
           "sha256": "911b2083efd7c0dca2ac3b358b75222660dc09fb716d64fbfc417ba6c99ff3de"}

# Test phrases: two short ones, six of four words and more; no numbers (Whisper writes digits) and nothing unusual.
PHRASES = {
    "ru": ["Привет.", "Доброе утро.", "Кошка спит дома на диване.", "Я люблю читать книги по вечерам.",
           "Завтра мы поедем к бабушке в деревню.", "Поезд уходит рано утром и прибывает в Москву вечером.",
           "Моя сестра работает в больнице у моря.", "Пожалуйста, закройте окно в комнате."],
    "en": ["Hello.", "Good morning.", "The cat sleeps at home on the sofa.", "I like to read books in the evening.",
           "Tomorrow we will visit our grandparents in the country.",
           "The train leaves early in the morning and arrives in London in the evening.",
           "My sister works in a hospital near the sea.", "Could you please close the window?"],
    "de": ["Hallo.", "Guten Morgen.", "Die Katze schläft zu Hause auf dem Sofa.", "Ich lese am Abend gern Bücher.",
           "Morgen besuchen wir unsere Großeltern auf dem Land.",
           "Der Zug fährt früh am Morgen ab und kommt am Abend in Berlin an.",
           "Meine Schwester arbeitet in einem Krankenhaus am Meer.", "Kannst du bitte das Fenster schließen?"],
    "es": ["Hola.", "Buenos días.", "El gato duerme en la casa.", "Me gusta leer libros por la noche.",
           "Mañana vamos a visitar a mis abuelos en el campo.",
           "El tren sale temprano y llega a Barcelona por la tarde.",
           "Mi hermana trabaja en un hospital cerca del mar.", "¿Puedes cerrar la ventana, por favor?"],
    "fr": ["Bonjour.", "Merci beaucoup.", "Le chat dort à la maison sur le canapé.", "J'aime lire des livres le soir.",
           "Demain nous allons voir nos grands-parents à la campagne.",
           "Le train part tôt le matin et arrive à Paris le soir.",
           "Ma sœur travaille dans un hôpital près de la mer.", "Peux-tu fermer la fenêtre, s'il te plaît ?"],
    "el": ["Γεια σου.", "Καλημέρα.", "Η γάτα κοιμάται στο σπίτι στον καναπέ.", "Μου αρέσει να διαβάζω βιβλία το βράδυ.",
           "Αύριο θα επισκεφτούμε τους παππούδες μας στο χωριό.",
           "Το τρένο φεύγει νωρίς το πρωί και φτάνει στην Αθήνα το βράδυ.",
           "Η αδελφή μου δουλεύει σε ένα νοσοκομείο κοντά στη θάλασσα.", "Μπορείς να κλείσεις το παράθυρο, σε παρακαλώ;"],
    "sv": ["Hej.", "God morgon.", "Katten sover hemma i soffan.", "Jag tycker om att läsa böcker på kvällen.",
           "I morgon ska vi besöka våra morföräldrar på landet.",
           "Tåget går tidigt på morgonen och kommer fram till Stockholm på kvällen.",
           "Min syster arbetar på ett sjukhus nära havet.", "Kan du stänga fönstret, tack?"],
    "zh": ["你好。", "早上好。", "猫在家里的沙发上睡觉。", "我喜欢在晚上看书。", "明天我们去乡下看望爷爷奶奶。",
           "火车早上出发，晚上到达北京。", "我的姐姐在海边的一家医院工作。", "请你把窗户关上，好吗？"],
    # Latin is read by an Italian voice in Italian spelling (latin.go): the phrases are respelled as the app does it,
    # and Whisper listens in Italian (the voice's own language) and is compared with the respelled text
    "la": ["Salve.", "Gratias tibi.", "Puella in horto cum cane ambulat.", "Libros legere vesperi mihi placet.",
           "Cras avum et aviam in villa visitabimus.", "Navis mane solvit et vesperi in portum venit.",
           "Soror mea in valetudinario prope mare laborat.", "Claude, quaeso, fenestram cubiculi."],
}
# characters Whisper may write in the traditional form
TRAD = str.maketrans("貓裡歡書們鄉車達爺發這個時間後來樣頭說話覺見", "猫里欢书们乡车达爷发这个时间后来样头说话觉见")


def fail(msg):
    print("ERROR: " + msg)
    sys.exit(2)


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for b in iter(lambda: f.read(1 << 20), b""):
            h.update(b)
    return h.hexdigest()


def fetch(work, url, name, size, sha):
    """A pinned download (size and SHA-256), cached in <work>/downloads or found in <work>/mirror (run_all.sh)."""
    for d in ("downloads", "mirror"):
        p = os.path.join(work, d, name)
        if os.path.exists(p) and os.path.getsize(p) == size and sha256(p) == sha:
            return p
    p = os.path.join(work, "downloads", name)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    print("downloading %s (%.0f MB)" % (url, size / 1e6), flush=True)
    with urllib.request.urlopen(url, timeout=120) as r, open(p + ".part", "wb") as f:
        shutil.copyfileobj(r, f, 1 << 20)
    if os.path.getsize(p + ".part") != size or sha256(p + ".part") != sha:
        fail("%s: size or SHA-256 differs from the pinned one" % name)
    os.replace(p + ".part", p)
    return p


def untar(archive, dest):
    with tarfile.open(archive, "r:bz2") as t:
        try:
            t.extractall(dest, filter="data")   # no paths out of dest (Python 3.12+, 3.11.4+)
        except TypeError:
            t.extractall(dest)


def catalogue(work):
    """The voice catalogue and the sherpa-onnx package, from tts.go (go test -run TestDumpVoiceCatalog)."""
    fb = os.path.join(LAUNCHER, "ui_fallback")   # go:embed needs it (made by run_all.sh and build.sh too)
    if not os.path.isdir(fb):
        os.makedirs(fb)
        for f in ("index.html", "tests.txt"):
            shutil.copy(os.path.join(APP, "ui", f), fb)
    out = os.path.join(work, "catalogue.json")
    r = subprocess.run(["go", "test", "-count=1", "-run", "^TestDumpVoiceCatalog$", "."], cwd=LAUNCHER,
                       env=dict(os.environ, TDOC_DUMP_VOICES=out), capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(out):
        fail("go test -run TestDumpVoiceCatalog:\n" + r.stdout + r.stderr)
    return json.load(open(out, encoding="utf-8"))


def respell(work, texts, kind):
    """The phrases as the app gives them to the voice (respellFor in tts.go: Latin in Italian spelling for the
    Italian voice), through go test -run TestDumpRespell."""
    if not kind:
        return texts
    if kind not in ("la-church", "la-classical"):
        fail("unknown respelling %s" % kind)
    src, dst = os.path.join(work, "respell-in.txt"), os.path.join(work, "respell-out.txt")
    open(src, "w", encoding="utf-8").write("\n".join(texts) + "\n")
    r = subprocess.run(["go", "test", "-count=1", "-run", "^TestDumpRespell$", "."], cwd=LAUNCHER,
                       env=dict(os.environ, TDOC_RESPELL_IN=src, TDOC_RESPELL_OUT=dst,
                                TDOC_RESPELL_KIND="classical" if kind == "la-classical" else ""), capture_output=True, text=True)
    if r.returncode != 0 or not os.path.exists(dst):
        fail("go test -run TestDumpRespell:\n" + r.stdout + r.stderr)
    out = open(dst, encoding="utf-8").read().rstrip("\n").split("\n")
    if len(out) != len(texts):
        fail("respelling: %d lines for %d" % (len(out), len(texts)))
    return out


def espeak_model(vd, v):
    """The model file the voice reads with: for a voice that reads with another espeak-ng voice (the classical Latin
    of Paola), the copy of the model with that voice in its metadata — as espeakModel in tts.go makes it."""
    if not v.get("espeak"):
        return v["model"]
    name = v["model"][:-len(".onnx")] + "-" + v["espeak"] + ".onnx"
    dst = os.path.join(vd, name)
    if not os.path.exists(dst):
        b = bytearray(open(os.path.join(vd, v["model"]), "rb").read())
        key, voice, n, i = b"\n\x05voice\x12", v["espeak"].encode(), 0, 0
        while True:
            j = b.find(key, i)
            if j < 0:
                break
            k = j + len(key)
            old = bytes(b[k + 1:k + 1 + len(voice)])
            if k < len(b) and b[k] == len(voice) and old.isalpha() and old.islower():
                b[k + 1:k + 1 + len(voice)] = voice
                n += 1
            i = k
        if not n:
            fail("%s: no espeak-ng voice in %s" % (v["id"], v["model"]))
        open(dst, "wb").write(bytes(b))
    return name


def install_voice(work, v):
    """The voice's folder under <work>/voices, as the app puts it together."""
    vd = os.path.join(work, "voices", v["dir"])
    if os.path.exists(os.path.join(vd, v["model"])) and os.path.exists(os.path.join(vd, "tokens.txt")):
        return vd
    parts = v.get("parts") or [{"url": v["url"], "file": os.path.basename(v["url"]), "size": v["size"], "sha256": v["sha256"]}]
    shutil.rmtree(vd, ignore_errors=True)
    for p in parts:
        name = p["file"] if v.get("parts") else os.path.basename(p["url"])
        f = fetch(work, p["url"], (v["dir"] + "--" + name) if v.get("parts") else name, p["size"], p["sha256"])
        if not v.get("parts"):
            untar(f, os.path.join(work, "voices"))
        elif name.endswith(".tar.bz2"):
            untar(f, vd)
        else:
            os.makedirs(vd, exist_ok=True)
            shutil.copy(f, os.path.join(vd, name))
    return vd


def wav_seconds(path):
    with wave.open(path) as w:
        return w.getnframes() / w.getframerate()


def words(s, lang):
    s = unicodedata.normalize("NFD", s.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    if lang == "zh":
        s = s.translate(TRAD)
        return [c for c in s if unicodedata.category(c).startswith("L")]
    return re.sub(r"[^\w\s]", " ", s).split()


def letters(s):
    s = unicodedata.normalize("NFD", s.lower())
    return [c for c in s if unicodedata.category(c).startswith("L")]


def error_rate(ref, hyp, lang, by_letters=False):
    r, h = (letters(ref), letters(hyp)) if by_letters else (words(ref, lang), words(hyp, lang))
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            prev, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
    return d[len(h)] / max(1, len(r))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    keep, verbose = "--keep" in sys.argv, "--verbose" in sys.argv
    other = [a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--voices=")]
    work = os.path.abspath(args[0]) if args else "/tmp/tdoc-voices"
    os.makedirs(work, exist_ok=True)
    cat = catalogue(work)
    voices = json.load(open(other[0], encoding="utf-8")) if other else cat["voices"]
    voices = [v for v in voices if not args[1:] or v["id"] in args[1:]]
    if not voices:
        fail("no such voice: %s" % " ".join(args[1:]))
    tts = cat["tts"]
    pkg = fetch(work, tts["url"], tts["asset"], tts["size"], tts["sha256"])
    top = os.path.join(work, tts["asset"][:-len(".tar.bz2")])
    if not os.path.isdir(top):
        untar(pkg, work)
    wpkg = fetch(work, WHISPER["url"], WHISPER["file"], WHISPER["size"], WHISPER["sha256"])
    wdir = os.path.join(work, "sherpa-onnx-whisper-base")
    if not os.path.isdir(wdir):
        untar(wpkg, work)
    env = dict(os.environ, LD_LIBRARY_PATH=os.path.join(top, "lib"))
    speech = os.path.join(work, "speech")
    os.makedirs(speech, exist_ok=True)
    bad = 0
    print("\n%-16s %-4s %8s %8s %8s  %s" % ("voice", "lang", "s/char", "worst", "errors", "verdict"))
    for v in voices:
        lang = v["lang"]
        if lang not in PHRASES:
            print("%-16s %-4s  no test phrases for this language" % (v["id"], lang))
            continue
        vd = install_voice(work, v)
        rel = os.path.relpath(vd, os.path.join(work, "voices"))
        rows = []
        hear = v.get("via") or lang   # the language Whisper listens in: the voice's own
        model = espeak_model(vd, v)
        for i, text in enumerate(respell(work, PHRASES[lang], v.get("respell")), 1):
            out = os.path.join(speech, "%s-%d.wav" % (v["id"], i))
            cmd = [os.path.join(top, "bin", "sherpa-onnx-offline-tts"), "--vits-model=%s/%s" % (rel, model),
                   "--vits-tokens=%s/tokens.txt" % rel]
            if v.get("lexicon"):
                cmd.append("--vits-lexicon=%s/%s" % (rel, v["lexicon"]))
                if v.get("rules"):
                    cmd.append("--tts-rule-fsts=" + ",".join("%s/%s" % (rel, r) for r in v["rules"]))
            else:
                cmd.append("--vits-data-dir=%s/espeak-ng-data" % rel)
            cmd += ["--num-threads=4", "--sid=%d" % v.get("sid", 0), "--speed=1.00", "--output-filename=" + out, "--", text]
            r = subprocess.run(cmd, cwd=os.path.join(work, "voices"), env=env, capture_output=True, text=True)
            if r.returncode != 0 or not os.path.exists(out):
                fail("%s: sherpa-onnx-offline-tts failed:\n%s" % (v["id"], (r.stdout + r.stderr)[-2000:]))
            rows.append([text, out, wav_seconds(out), ""])
        r = subprocess.run([os.path.join(top, "bin", "sherpa-onnx-offline"),
                            "--whisper-encoder=" + os.path.join(wdir, "base-encoder.int8.onnx"),
                            "--whisper-decoder=" + os.path.join(wdir, "base-decoder.int8.onnx"),
                            "--tokens=" + os.path.join(wdir, "base-tokens.txt"), "--whisper-language=" + hear,
                            "--whisper-task=transcribe", "--num-threads=4"] + [x[1] for x in rows],
                           env=env, capture_output=True, text=True)
        heard = re.findall(r'"text": "((?:[^"\\]|\\.)*)"', r.stdout + r.stderr)
        if r.returncode != 0 or len(heard) != len(rows):
            fail("%s: Whisper failed:\n%s" % (v["id"], (r.stdout + r.stderr)[-2000:]))
        for x, h in zip(rows, heard):
            x[3] = json.loads('"%s"' % h).strip()
        zh = lang == "zh"
        # the six longer phrases: four words and more (Chinese: six characters and more)
        scored = [x for x in rows if (len(words(x[0], lang)) >= 6 if zh else len(x[0].split()) >= 4)]
        per_char = sum(x[2] for x in scored) / sum(len(x[0]) for x in scored)
        worst = max(x[2] / len(x[0]) for x in scored)
        # a voice that reads another language (Latin by an Italian voice): Whisper hears it as Italian and writes
        # Italian words, so the letters are compared, not the words
        by_letters = bool(v.get("via"))
        errors = sum(error_rate(x[0], x[3], lang, by_letters) for x in scored) / len(scored)
        slow = per_char > (0.45 if zh else 0.09) or worst > (0.60 if zh else 0.16)
        verdict = " ".join(w for w, f in (("SLOW", slow), ("WORDS", errors > 0.6)) if f) or "ok"
        bad += verdict != "ok"
        print("%-16s %-4s %8.3f %8.3f %7.0f%%  %s" % (v["id"], lang, per_char, worst, 100 * errors, verdict), flush=True)
        if verbose or verdict != "ok":
            for text, out, sec, h in rows:
                print("      %5.2f s  %s  →  %s" % (sec, text, h))
        if not keep:
            for x in rows:
                os.remove(x[1])
    if keep:
        print("\nspeech kept in " + speech)
    print("\n%s" % ("ALL VOICES OK" if not bad else "VOICES TO LISTEN TO: %d" % bad))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
