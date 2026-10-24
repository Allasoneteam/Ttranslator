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
		"Ego cogito, ergo sum.":                    "Ego cogito, ergo sum.",
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
	script := "#!/bin/sh\nfor a in \"$@\"; do last=\"$a\"; case \"$a\" in --output-filename=*) out=\"${a#--output-filename=}\";; esac; done\n" +
		"printf '%s' \"$last\" > \"" + filepath.Join(a.engineDir, "said.txt") + "\"\nprintf 'RIFF0000WAVEfmt 0000000000000000data0000000000000000' > \"$out\"\n"
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
	if string(said) != "Glòria in ekscèlsis Deo." {
		t.Errorf("the voice was given %q", said)
	}
}

// TDOC_RESPELL_IN=<file> TDOC_RESPELL_OUT=<file>: the lines of a file respelled as for the Italian voice — for
// source/tests/voice_check.py, which speaks Latin test phrases the way the app does.
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
	for i, l := range lines {
		lines[i] = respellLatinChurch(l)
	}
	if err := os.WriteFile(out, []byte(strings.Join(lines, "\n")+"\n"), 0o644); err != nil {
		t.Fatal(err)
	}
}
