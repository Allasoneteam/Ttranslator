package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
)

// Latin in Italian spelling with the stress marked, for the Italian voice (church pronunciation; latin.go)
func TestRespellLatinChurch(t *testing.T) {
	cases := map[string]string{
		// the author's sayings (the «Тест» phrases of 1.0)
		"Audentes fortuna iuvat.":                  "Audèntes fortuna iùvat.",
		"Ego cogito, ergo sum.":                    "Ego cògito, ergo sum.",
		"Corruptissima re publica plurimae leges.": "Corruptìssima re pùblica plùrime lèges.",
		"Ex aequo et bono.":                        "Ex equo et bono.",
		// diphthongs, ti, xc, h, stress after the rules of Latin
		"Pater noster, qui es in caelis, sanctificetur nomen tuum.":           "Pàter nòster, qui es in cèlis, sanctificètur nòmen tùum.",
		"Gloria in excelsis Deo et in terra pax hominibus bonae voluntatis.":  "Glòria in ekscèlsis Deo et in terra pax omìnibus bone voluntàtis.",
		"Ave Maria, gratia plena, Dominus tecum, benedicta tu in mulieribus.": "Ave Marìa, gràzia plena, Dòminus tècum, benedìcta tu in mulièribus.",
		"Tempora mutantur, nos et mutamur in illis.":                          "Tèmpora mutàntur, nos et mutàmur in ìllis.",
		"Requiem aeternam dona eis, Domine, et lux perpetua luceat eis.":      "Rèquiem etèrnam dona èis, Dòmine, et lux perpètua lùceat èis.",
		"Sapientia et veritas, caritas et pietas.":                            "Sapiènzia et vèritas, càritas et pìetas.",
		"Senatus populusque Romanus.":                                         "Senàtus populùsque Romànus.",
		"Errare humanum est, sed in errore perseverare diabolicum.":           "Errare umànum est, sed in errore perseverare diabòlicum.",
		"poeta poema aër Israel":                                              "poeta poema àer Ìsrael",
		"mihi nihil Mihi NIHIL ex nihilo":                                     "michi nìchil Michi NÌCHIL ex nìchilo",
		"hostia gratia Christianus mixtio Attius totíus":                      "òstia gràzia Christiànus mìxtio Àttius totìus",
		"fortūna Rōmānus legĕre":                                              "fortùna Romànus lègere",
		"cælum Cæsar CAELUM":                                                  "cèlum Cèsar CÈLUM",
		"PATER NOSTER":                                                        "PÀTER NÒSTER",
		"Habet hominem Johannes Jesus ejus major Troia":                       "Àbet òminem Ioànnes Ièsus èius màior Troia",
		"excelsis exhibeo lingua sanguis quae aliquis":                        "ekscèlsis exìbeo lingua sànguis que àliquis",
		"Ave мир, Pater — 3 et 4":                                             "Ave мир, Pàter — 3 et 4",
		"":                                                                    "",
	}
	for in, want := range cases {
		if got := respellLatinChurch(in); got != want {
			t.Errorf("%q\n got %q\nwant %q", in, got, want)
		}
	}
	// the catalogue: the Latin voice is the Italian Paola and its texts are respelled; other voices read as they are
	v := findVoice("la-paola")
	if v == nil || v.Lang != "la" || v.Via != "it" || v.Respell != "la-church" || v.Dir != "vits-piper-it_IT-paola-medium" || v.NC {
		t.Fatalf("Latin voice: %+v", v)
	}
	if got := respellFor(v, "Dominus vobiscum."); got != "Dòminus vobìscum." {
		t.Errorf("respellFor Latin: %q", got)
	}
	if ru := findVoice("ru-dmitri"); ru == nil || respellFor(ru, "Dominus") != "Dominus" {
		t.Errorf("another voice respelled the text")
	}
}

// /api/tts for Latin: the Italian voice gets the respelled text (a stand-in for sherpa-onnx writes down what it
// was given and returns a WAV header)
func TestLatinVoiceSpeaks(t *testing.T) {
	if runtime.GOOS == "windows" {
		t.Skip("the stand-in program is a shell script")
	}
	a := testApp(t)
	a.root, a.modelsDir, a.engineDir = t.TempDir(), t.TempDir(), t.TempDir()
	a.cfg = defaultConfig()
	v := findVoice("la-paola")
	if v == nil {
		t.Fatal("no Latin voice")
	}
	fakeVoice(t, a, v)
	exe := filepath.Join(a.engineDir, "fake", "bin", ttsExeName())
	_ = os.MkdirAll(filepath.Dir(exe), 0o755)
	script := "#!/bin/sh\nfor a in \"$@\"; do last=\"$a\"; case \"$a\" in --output-filename=*) out=\"${a#--output-filename=}\";; --vits-model=*) model=\"${a#--vits-model=}\";; esac; done\n" +
		"printf '%s' \"$last\" > \"" + filepath.Join(a.engineDir, "said.txt") + "\"\nprintf '%s' \"$model\" > \"" + filepath.Join(a.engineDir, "model.txt") + "\"\n" +
		"printf 'RIFF0000WAVEfmt 0000000000000000data0000000000000000' > \"$out\"\n"
	if err := os.WriteFile(exe, []byte(script), 0o755); err != nil {
		t.Fatal(err)
	}
	meta, _ := json.Marshal(ttsMeta{Version: "test", Exe: "fake/bin/" + ttsExeName()})
	_ = os.WriteFile(filepath.Join(a.engineDir, "tts.json"), meta, 0o644)
	mux := http.NewServeMux()
	a.ttsRoutes(mux)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("POST", "/api/tts", strings.NewReader(`{"lang":"la","text":"Gloria in excelsis Deo."}`)))
	if rec.Code != 200 || rec.Header().Get("X-Voice") != "la-paola" {
		t.Fatalf("/api/tts: %d %s", rec.Code, rec.Body.String())
	}
	said, _ := os.ReadFile(filepath.Join(a.engineDir, "said.txt"))
	model, _ := os.ReadFile(filepath.Join(a.engineDir, "model.txt"))
	if string(said) != "Glòria in ekscèlsis Deo." || string(model) != v.Dir+"/"+v.Model {
		t.Errorf("the voice was given %q, model %q", said, model)
	}

	// the classical pronunciation: the same folder, a copy of the model for espeak-ng's Latin, the stress marked
	cl := findVoice("la-paola-classical")
	_ = os.WriteFile(filepath.Join(a.voiceDir(cl), cl.Model), []byte("weights r\x0b\n\x05voice\x12\x02itr"), 0o644)
	a.cfg.Voices = map[string]string{"la": cl.ID}
	rec = httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("POST", "/api/tts", strings.NewReader(`{"lang":"la","text":"Senatus populusque Romanus."}`)))
	if rec.Code != 200 || rec.Header().Get("X-Voice") != cl.ID {
		t.Fatalf("/api/tts classical: %d %s", rec.Code, rec.Body.String())
	}
	said, _ = os.ReadFile(filepath.Join(a.engineDir, "said.txt"))
	model, _ = os.ReadFile(filepath.Join(a.engineDir, "model.txt"))
	copied, _ := os.ReadFile(filepath.Join(a.voiceDir(cl), "it_IT-paola-medium-la.onnx"))
	if string(said) != "Senātus populusque Romānus." || string(model) != cl.Dir+"/it_IT-paola-medium-la.onnx" || string(copied) != "weights r\x0b\n\x05voice\x12\x02lar" {
		t.Errorf("classical: the voice was given %q, model %q, the copy %q", said, model, copied)
	}
	// both entries share the folder: downloaded once, deleted together
	st := a.ttsStateJSON()["voices"].([]map[string]any)
	n := 0
	for _, x := range st {
		if x["lang"] == "la" && x["present"] == true {
			n++
		}
	}
	if n != 2 {
		t.Errorf("both Latin entries should be present: %v", st)
	}
}

// Latin for espeak-ng's Latin rules (the classical pronunciation): a macron where the stress falls on an open last
// but one syllable; the spelling stays Latin (latin.go)
func TestRespellLatinClassical(t *testing.T) {
	cases := map[string]string{
		"Audentes fortuna iuvat.":                                   "Audentes fortūna iuvat.",
		"Cogito, ergo sum.":                                         "Cogito, ergo sum.",
		"Corruptissima re publica plurimae leges.":                  "Corruptissima re publica plurimae leges.",
		"Ex aequo et bono.":                                         "Ex aequo et bono.",
		"Gallia est omnis divisa in partes tres.":                   "Gallia est omnis divīsa in partes tres.",
		"Errare humanum est.":                                       "Errāre humānum est.",
		"Pater noster, qui es in caelis, sanctificetur nomen tuum.": "Pater noster, qui es in caelis, sanctificētur nomen tuum.",
		"Ave Maria, gratia plena, Dominus tecum.":                   "Ave Marīa, gratia plena, Dominus tecum.",
		"Senatus populusque Romanus.":                               "Senātus populusque Romānus.",
		"Mens sana in corpore sano.":                                "Mens sana in corpore sano.",
		// marks of the text: accents and breves dropped, macrons kept, a diaeresis kept unless the vowel is stressed
		"Dóminus fortūna legĕre poëta aër Eurōpa": "Dominus fortūna legere poēta aër Eurōpa",
		// ligatures, capitals, mihi as it is, words in other letters
		"cælum Cæsar PATER ROMANUS mihi nihil Ave мир": "caelum Caesar PATER ROMĀNUS mihi nihil Ave мир",
		// the short i of the third declension and -bilis; the long last but one syllable before a vowel (Maria, illius)
		"lumine hominem virgines mobilis anima illius diei": "lumine hominem virgines mobilis anima illīus diēi",
		"Puella in horto ambulat, vesperi laborat.":         "Puella in horto ambulat, vesperi labōrat.",
		"": "",
	}
	for in, want := range cases {
		if got := respellLatinClassical(in); got != want {
			t.Errorf("%q\n got %q\nwant %q", in, got, want)
		}
	}
	v := findVoice("la-paola-classical")
	c := findVoice("la-paola")
	if v == nil || c == nil || v.Lang != "la" || v.Via != "it" || v.Respell != "la-classical" || v.Espeak != "la" ||
		v.Dir != c.Dir || v.URL != c.URL || v.SHA256 != c.SHA256 || v.Size != c.Size || c.Espeak != "" {
		t.Fatalf("classical Latin voice: %+v", v)
	}
	if got := respellFor(v, "Senatus Romanus"); got != "Senātus Romānus" {
		t.Errorf("respellFor classical: %q", got)
	}
}

// The copy of the model for another espeak-ng voice: the metadata "voice" it → la, nothing else moves
func TestEspeakModelCopy(t *testing.T) {
	model := []byte("\x08\x07weights\x00\x01r\x0b\n\x05voice\x12\x02itr\x0f\n\nhas_espeak\x12\x011tail r\x0b\n\x05voice\x12\x02it.")
	b := append([]byte(nil), model...)
	if n := patchEspeakVoice(b, "la"); n != 2 || len(b) != len(model) || !strings.Contains(string(b), "voice\x12\x02lar") || strings.Contains(string(b), "voice\x12\x02it") {
		t.Fatalf("patch: %d %q", n, b)
	}
	if n := patchEspeakVoice([]byte("no metadata \n\x05voice\x12\x03ita"), "la"); n != 0 {
		t.Errorf("a value of another length was changed")
	}
	a := testApp(t)
	a.modelsDir = t.TempDir()
	v := findVoice("la-paola-classical")
	d := a.voiceDir(v)
	_ = os.MkdirAll(d, 0o755)
	if err := os.WriteFile(filepath.Join(d, v.Model), model, 0o644); err != nil {
		t.Fatal(err)
	}
	name, err := a.espeakModel(v)
	if err != nil || name != "it_IT-paola-medium-la.onnx" {
		t.Fatalf("espeakModel: %q %v", name, err)
	}
	got, _ := os.ReadFile(filepath.Join(d, name))
	orig, _ := os.ReadFile(filepath.Join(d, v.Model))
	if len(got) != len(model) || strings.Count(string(got), "voice\x12\x02la") != 2 || string(orig) != string(model) {
		t.Errorf("the copy: %q (the original: %q)", got, orig)
	}
	_ = os.WriteFile(filepath.Join(d, name), []byte("made before"), 0o644) // made once: not written again
	if _, err := a.espeakModel(v); err != nil {
		t.Fatal(err)
	}
	if b, _ := os.ReadFile(filepath.Join(d, name)); string(b) != "made before" {
		t.Errorf("the copy was written again")
	}
	_ = os.Remove(filepath.Join(d, name))
	_ = os.WriteFile(filepath.Join(d, v.Model), []byte("onnx without metadata"), 0o644)
	if _, err := a.espeakModel(v); err == nil {
		t.Errorf("a model without the espeak-ng voice was copied")
	}
}

// TDOC_RESPELL_IN=<file> TDOC_RESPELL_OUT=<file>: the lines of a file respelled as for the Italian voice — for
// source/tests/voice_check.py, which speaks Latin test phrases the way the app does. TDOC_RESPELL_KIND=classical:
// as for the classical pronunciation (respellLatinClassical).
func TestDumpRespell(t *testing.T) {
	in, out := os.Getenv("TDOC_RESPELL_IN"), os.Getenv("TDOC_RESPELL_OUT")
	if in == "" || out == "" {
		t.Skip("TDOC_RESPELL_IN and TDOC_RESPELL_OUT are not set")
	}
	b, err := os.ReadFile(in)
	if err != nil {
		t.Fatal(err)
	}
	lines := strings.Split(strings.TrimRight(string(b), "\n"), "\n")
	respell := respellLatinChurch
	if os.Getenv("TDOC_RESPELL_KIND") == "classical" {
		respell = respellLatinClassical
	}
	for i, l := range lines {
		lines[i] = respell(l)
	}
	if err := os.WriteFile(out, []byte(strings.Join(lines, "\n")+"\n"), 0o644); err != nil {
		t.Fatal(err)
	}
}
