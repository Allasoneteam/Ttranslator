package main

import (
	"bytes"
	"context"
	"crypto/sha256"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"encoding/xml"
	"fmt"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"testing"
	"time"
)

var hex64 = regexp.MustCompile(`^[0-9a-f]{64}$`)

// files of a voice made of parts: from the sherpa-onnx release, or from the Hugging Face page of its author, pinned
// to a commit
var hfPinned = regexp.MustCompile(`^https://huggingface\.co/csukuangfj/vits-piper-[A-Za-z0-9_-]+/resolve/[0-9a-f]{40}/[^/]+$`)

// the voices: official sherpa-onnx archives (or parts), pinned size and checksum, a known language, a licence
func TestVoiceCatalog(t *testing.T) {
	langs := map[string]bool{"ru": true, "en": true, "de": true, "fr": true, "es": true, "el": true, "zh": true, "la": true, "sv": true}
	seen := map[string]bool{}
	for _, v := range voiceSpecs {
		if seen[v.ID] {
			t.Errorf("%s: duplicate id", v.ID)
		}
		seen[v.ID] = true
		if !langs[v.Lang] || v.Name == "" || v.License == "" || (v.Gender != "female" && v.Gender != "male") {
			t.Errorf("%s: language, name, licence or gender: %+v", v.ID, v)
		}
		if !strings.HasPrefix(v.Dir, "vits-piper-") || !strings.HasSuffix(v.Model, ".onnx") || !strings.Contains(v.Dir, strings.TrimSuffix(v.Model, ".onnx")) {
			t.Errorf("%s: folder %s, model %s", v.ID, v.Dir, v.Model)
		}
		if len(v.Parts) == 0 && v.URL != voiceRelease+v.Dir+".tar.bz2" {
			t.Errorf("%s: archive %s", v.ID, v.URL)
		}
		if len(v.Parts) > 0 {
			var sum int64
			files := map[string]bool{}
			for _, p := range v.Parts {
				sum += p.Size
				files[p.File] = true
				if !(strings.HasPrefix(p.URL, voiceRelease) || hfPinned.MatchString(p.URL)) || path.Base(p.URL) != p.File || p.Size <= 0 || !hex64.MatchString(p.SHA256) {
					t.Errorf("%s: part %+v", v.ID, p)
				}
			}
			if len(files) != len(v.Parts) || !files[v.Model] || !files["tokens.txt"] || !files["espeak-ng-data.tar.bz2"] || sum != v.Size || v.URL != v.Parts[0].URL {
				t.Errorf("%s: parts %v, size %d of %d", v.ID, files, v.Size, sum)
			}
		}
		if v.Lexicon != "" && (v.Lexicon != "lexicon.txt" || len(v.Rules) == 0 || len(v.Parts) > 0) {
			t.Errorf("%s: lexicon %q, rules %v", v.ID, v.Lexicon, v.Rules)
		}
		for _, r := range v.Rules {
			if !strings.HasSuffix(r, ".fst") || strings.ContainsAny(r, `/\,`) {
				t.Errorf("%s: rule file %q", v.ID, r)
			}
		}
		if v.Size < 1<<20 || !hex64.MatchString(v.SHA256) || !strings.HasPrefix(v.Page, voiceSamples+"#") {
			t.Errorf("%s: size %d, sha %q, page %q", v.ID, v.Size, v.SHA256, v.Page)
		}
		if strings.Contains(v.License, "NC") != v.NC {
			t.Errorf("%s: licence %q and nc=%v disagree", v.ID, v.License, v.NC)
		}
	}
	// the voices the author asked for (0.9.3): Spanish es_ES-mls_9972-low and Chinese zh_CN-chaowen-medium
	if v := findVoice("es-mls-9972"); v == nil || v.Lang != "es" || len(v.Parts) != 3 || !strings.HasPrefix(v.URL, "https://huggingface.co/") {
		t.Errorf("Spanish voice: %+v", v)
	}
	if v := findVoice("zh-chaowen"); v == nil || v.Lang != "zh" || v.Lexicon == "" || len(v.Rules) != 3 {
		t.Errorf("Chinese voice: %+v", v)
	}
	for _, l := range []string{"ru", "en", "de", "sv", "es", "zh"} {
		free := false
		for _, v := range voiceSpecs {
			free = free || (v.Lang == l && !v.NC)
		}
		if !free {
			t.Errorf("%s: no voice with a free licence", l)
		}
	}
	if pkg, ok := currentTTSPackage(); ok {
		if !strings.Contains(pkg.Asset, ttsVersion) || !strings.HasSuffix(pkg.Asset, ".tar.bz2") || pkg.Size < 1<<20 || !hex64.MatchString(pkg.SHA256) {
			t.Errorf("sherpa-onnx package: %+v", pkg)
		}
	}
}

// arguments: paths relative to the voices folder, "--" before the text
func TestTTSArgs(t *testing.T) {
	v := &VoiceSpec{Dir: "vits-piper-ru_RU-ruslan-medium", Model: "ru_RU-ruslan-medium.onnx", SID: 0}
	args := ttsArgs(v, "--привет", 1, "tts-1.wav")
	n := len(args)
	if n < 3 || args[n-2] != "--" || args[n-1] != "--привет" {
		t.Fatalf("text is not after --: %q", args)
	}
	for _, a := range args[:n-1] {
		if strings.ContainsAny(a, `:\`) || strings.Contains(a, "..") {
			t.Errorf("not a plain relative argument: %q", a)
		}
		for _, r := range a {
			if r > 127 {
				t.Errorf("non-ASCII option: %q", a)
				break
			}
		}
	}
	if args[0] != "--vits-model=vits-piper-ru_RU-ruslan-medium/ru_RU-ruslan-medium.onnx" || !strings.Contains(strings.Join(args, " "), "--speed=1.00") ||
		!strings.Contains(strings.Join(args, " "), "--vits-data-dir=vits-piper-ru_RU-ruslan-medium/espeak-ng-data") {
		t.Errorf("args: %q", args)
	}
	// a voice with a lexicon (Chinese): lexicon and rules instead of espeak-ng-data
	zh := findVoice("zh-chaowen")
	if zh == nil {
		t.Fatal("no Chinese voice")
	}
	all := strings.Join(ttsArgs(zh, "你好。", 1, "tts-2.wav"), " ")
	if strings.Contains(all, "espeak-ng-data") || !strings.Contains(all, "--vits-lexicon=vits-piper-zh_CN-chaowen-medium/lexicon.txt") ||
		!strings.Contains(all, "--tts-rule-fsts=vits-piper-zh_CN-chaowen-medium/phone.fst,vits-piper-zh_CN-chaowen-medium/date.fst,vits-piper-zh_CN-chaowen-medium/number.fst") {
		t.Errorf("Chinese args: %s", all)
	}
}

// a voice made of parts: downloaded one after another into <Dir>.download (a finished part is not fetched again,
// an unfinished one resumes), then put together into the voice's folder; the progress counts all parts
func TestVoiceParts(t *testing.T) {
	espeak, _ := base64.StdEncoding.DecodeString("QlpoOTFBWSZTWVAFj9IAAJR/gMmAABBAAveAABAAAP7p3gAIKCAAkoSqaAMhoABpobUCqKJ6g0BiMgBoP2XLWVvEgzUiIQ4W+1ywlsWNCEJEx2eXRaoRRJDFUhgrYLF7c30x0qpZSuhwocNecHUPjtH9kosWQWKgXDGTjYkEJCugReiD+LuSKcKEgoAsfpA=")
	model := bytes.Repeat([]byte("onnx-model "), 30000)
	tokens := []byte("_ 0\n^ 1\n")
	files := map[string][]byte{"es_ES-x-low.onnx": model, "tokens.txt": tokens, "espeak-ng-data.tar.bz2": espeak}
	var mu sync.Mutex
	requests := map[string][]string{} // file → Range headers
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		name := path.Base(r.URL.Path)
		mu.Lock()
		requests[name] = append(requests[name], r.Header.Get("Range"))
		mu.Unlock()
		b, ok := files[name]
		if !ok {
			http.NotFound(w, r)
			return
		}
		http.ServeContent(w, r, name, time.Time{}, bytes.NewReader(b))
	}))
	defer srv.Close()
	part := func(name string) VoicePart {
		sum := sha256.Sum256(files[name])
		return VoicePart{URL: srv.URL + "/" + name, File: name, Size: int64(len(files[name])), SHA256: hex.EncodeToString(sum[:])}
	}
	v := partsVoice("es-x", "es", "X", "female", "CC0", false, "es_ES-x-low", part("es_ES-x-low.onnx"), part("tokens.txt"), part("espeak-ng-data.tar.bz2"))
	if v.Size != int64(len(model)+len(tokens)+len(espeak)) || v.URL != srv.URL+"/es_ES-x-low.onnx" || v.Dir != "vits-piper-es_ES-x-low" {
		t.Fatalf("spec: %+v", v)
	}
	a := testApp(t)
	a.modelsDir = t.TempDir()
	stage := filepath.Join(a.voicesDir(), v.Dir+".download")
	_ = os.MkdirAll(stage, 0o755)
	// tokens.txt finished earlier, the model half way
	_ = os.WriteFile(filepath.Join(stage, "tokens.txt"), tokens, 0o644)
	_ = os.WriteFile(filepath.Join(stage, "es_ES-x-low.onnx.part"), model[:len(model)/2], 0o644)
	if got, want := a.voicePartial(&v), int64(len(tokens)+len(model)/2); got != want {
		t.Errorf("partial: %d, want %d", got, want)
	}
	var maxDone int64
	a.vdl = DownloadState{}
	if err := a.downloadVoice(context.Background(), &v); err != nil {
		t.Fatal(err)
	}
	if !a.voicePresent(&v) {
		t.Fatal("voice not put together")
	}
	maxDone = a.vdl.Done
	if b, _ := os.ReadFile(filepath.Join(a.voiceDir(&v), "espeak-ng-data", "phontab")); string(b) != "phon" {
		t.Errorf("espeak-ng-data not unpacked into the voice folder: %q", b)
	}
	if b, _ := os.ReadFile(filepath.Join(a.voiceDir(&v), "es_ES-x-low.onnx")); !bytes.Equal(b, model) {
		t.Error("model differs")
	}
	if _, err := os.Stat(stage); err == nil {
		t.Error("the download folder is left")
	}
	mu.Lock()
	if len(requests["tokens.txt"]) != 0 || len(requests["es_ES-x-low.onnx"]) != 1 || requests["es_ES-x-low.onnx"][0] != fmt.Sprintf("bytes=%d-", len(model)/2) {
		t.Errorf("requests: %v", requests)
	}
	mu.Unlock()
	if maxDone != v.Size || a.vdl.Total != v.Size {
		t.Errorf("progress: done %d, total %d, size %d", maxDone, a.vdl.Total, v.Size)
	}
	// a broken part: the voice is not there, the error names the file
	files["tokens.txt"] = []byte("_ 0\n^ 2\n")
	_ = os.RemoveAll(a.voiceDir(&v))
	err := a.downloadVoice(context.Background(), &v)
	if err == nil || !strings.Contains(err.Error(), "tokens.txt") || a.voicePresent(&v) {
		t.Errorf("broken part: %v", err)
	}
	a.removeVoiceDownloads(&v)
	if _, err := os.Stat(stage); err == nil {
		t.Error("removeVoiceDownloads left the download folder")
	}
}

// the manifest of a Windows program: the default one of MSVC is replaced by one asking for UTF-8, same length
func TestPatchManifestUTF8(t *testing.T) {
	manifest := "<?xml version='1.0' encoding='UTF-8' standalone='yes'?>\r\n<assembly xmlns='urn:schemas-microsoft-com:asm.v1' manifestVersion='1.0'>\r\n  <trustInfo xmlns=\"urn:schemas-microsoft-com:asm.v3\">\r\n    <security>\r\n      <requestedPrivileges>\r\n        <requestedExecutionLevel level='asInvoker' uiAccess='false' />\r\n      </requestedPrivileges>\r\n    </security>\r\n  </trustInfo>\r\n</assembly>\r\n"
	if len(manifest) != 381 {
		t.Fatalf("test manifest has %d bytes, the real one 381", len(manifest))
	}
	head := append([]byte("MZ\x90\x00\x03\x00\x00\x00PE\x00\x00"), bytes.Repeat([]byte{0, 1, 2, 0xff}, 64)...)
	tail := bytes.Repeat([]byte{0xab, 0, 0}, 50)
	exe := append(append(append([]byte{}, head...), manifest...), tail...)
	out, ok := patchManifestUTF8(exe)
	if !ok || len(out) != len(exe) {
		t.Fatalf("patch: ok=%v, %d → %d bytes", ok, len(exe), len(out))
	}
	if !bytes.Equal(out[:len(head)], head) || !bytes.Equal(out[len(out)-len(tail):], tail) {
		t.Fatal("bytes outside the manifest changed")
	}
	m := out[len(head) : len(head)+len(manifest)]
	if !bytes.Contains(m, []byte(">UTF-8</activeCodePage>")) || !bytes.HasSuffix(m, []byte("\r\n")) {
		t.Fatalf("new manifest: %q", m)
	}
	d := xml.NewDecoder(bytes.NewReader(m))
	elems := 0
	for {
		tok, err := d.Token()
		if err == io.EOF {
			break
		}
		if err != nil {
			t.Fatalf("new manifest is not well-formed XML: %v\n%s", err, m)
		}
		if se, ok := tok.(xml.StartElement); ok {
			elems++
			if se.Name.Local == "activeCodePage" && se.Name.Space != "http://schemas.microsoft.com/SMI/2019/WindowsSettings" {
				t.Errorf("activeCodePage namespace: %q", se.Name.Space)
			}
		}
	}
	if elems != 4 {
		t.Errorf("elements in the manifest: %d", elems)
	}
	if _, ok := patchManifestUTF8(out); ok {
		t.Error("a manifest with activeCodePage is patched again")
	}
	if _, ok := patchManifestUTF8(append(append([]byte{}, head...), tail...)); ok {
		t.Error("a program without a manifest is patched")
	}
	two := append(append([]byte{}, exe...), "<assembly>"...)
	if _, ok := patchManifestUTF8(two); ok {
		t.Error("two manifests: patched anyway")
	}
	// the copy next to the program
	dir := t.TempDir()
	p := filepath.Join(dir, "sherpa-onnx-offline-tts.exe")
	_ = os.WriteFile(p, exe, 0o755)
	c, err := utf8Copy(p)
	if err != nil || c != filepath.Join(dir, "sherpa-onnx-offline-tts-utf8.exe") {
		t.Fatalf("utf8Copy: %q, %v", c, err)
	}
	if b, _ := os.ReadFile(c); !bytes.Equal(b, out) {
		t.Error("the copy is not the patched program")
	}
}

// tar.bz2: unpacked inside the folder; a path out of it is refused
func TestUntarBz2(t *testing.T) {
	good, _ := base64.StdEncoding.DecodeString("QlpoOTFBWSZTWfto6pEAAJX7gMmAACBAAf+ACIByYN5ACAggAHQSiTE0jCA8p+pNPT1QSUTQAGIGgD7ssBqANpNnSQhz+iBWD3XFBSIQwBik3EF7kiiiExQQZsBCsS3rTDY+E5NQmoNYW/viLwgXKn3Eo45lf9yRczNhED+LuSKcKEh9tHVIgA==")
	evil, _ := base64.StdEncoding.DecodeString("QlpoOTFBWSZTWZEan6MAAFtbgMmAYAHlgAIAYiQfQAgIIABUNKYhhNMaA0CSUZBo09QHqB9FCxCD2QIQ7Q+A+WNyBDAxXSGeYpsIGogqcDDP19rFDTOEuk9JuHxEQHBdyRThQkJEan6M")
	dir := t.TempDir()
	dest := filepath.Join(dir, "out")
	_ = os.MkdirAll(dest, 0o755)
	g := filepath.Join(dir, "good.tar.bz2")
	_ = os.WriteFile(g, good, 0o644)
	if err := untarbz2(g, dest); err != nil {
		t.Fatal(err)
	}
	if b, _ := os.ReadFile(filepath.Join(dest, "top", "sub", "b.txt")); string(b) != "there" {
		t.Errorf("unpacked file: %q", b)
	}
	e := filepath.Join(dir, "evil.tar.bz2")
	_ = os.WriteFile(e, evil, 0o644)
	if err := untarbz2(e, dest); err == nil {
		t.Error("a path out of the folder was accepted")
	}
	if _, err := os.Stat(filepath.Join(dir, "evil.txt")); err == nil {
		t.Error("a file was written out of the folder")
	}
}

func fakeVoice(t *testing.T, a *App, v *VoiceSpec) {
	t.Helper()
	d := a.voiceDir(v)
	_ = os.MkdirAll(filepath.Join(d, "espeak-ng-data"), 0o755)
	_ = os.WriteFile(filepath.Join(d, v.Model), []byte("onnx"), 0o644)
	_ = os.WriteFile(filepath.Join(d, "tokens.txt"), []byte("_ 0\n"), 0o644)
}

// which voice reads a language: the chosen one if it is there, else the first downloaded one; the HTTP API
func TestVoicesAPI(t *testing.T) {
	a := testApp(t)
	a.root = t.TempDir() // config.json is written here
	a.modelsDir = t.TempDir()
	a.engineDir = t.TempDir()
	saved := voiceSpecs
	defer func() { voiceSpecs = saved }()
	voiceSpecs = []VoiceSpec{
		piperVoice("ru-a", "ru", "A", "male", "CC0", false, "ru_RU-a-medium", 1<<21, strings.Repeat("a", 64)),
		piperVoice("ru-b", "ru", "B", "female", "CC0", false, "ru_RU-b-medium", 1<<21, strings.Repeat("b", 64)),
		piperVoice("en-c", "en", "C", "female", "CC0", false, "en_US-c-medium", 1<<21, strings.Repeat("c", 64)),
	}
	a.cfg = defaultConfig()
	if id := a.activeVoiceID("ru"); id != "" {
		t.Errorf("no voices yet: %q", id)
	}
	fakeVoice(t, a, &voiceSpecs[1])
	if id := a.activeVoiceID("ru"); id != "ru-b" {
		t.Errorf("only B is there: %q", id)
	}
	fakeVoice(t, a, &voiceSpecs[0])
	if id := a.activeVoiceID("ru"); id != "ru-a" {
		t.Errorf("both, none chosen: the first of the catalogue, got %q", id)
	}
	a.cfg.Voices = map[string]string{"ru": "ru-b"}
	if id := a.activeVoiceID("ru"); id != "ru-b" {
		t.Errorf("B chosen: %q", id)
	}
	a.cfg.Voices = map[string]string{"ru": "en-c"}
	if id := a.activeVoiceID("ru"); id != "ru-a" {
		t.Errorf("a voice of another language chosen: %q", id)
	}

	mux := http.NewServeMux()
	a.ttsRoutes(mux)
	call := func(method, path, body string) (int, map[string]any) {
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, httptest.NewRequest(method, path, strings.NewReader(body)))
		var j map[string]any
		_ = json.Unmarshal(rec.Body.Bytes(), &j)
		return rec.Code, j
	}
	if code, _ := call("POST", "/api/tts", `{"lang":"ru","text":"Привет"}`); code != 409 {
		t.Errorf("no sherpa-onnx yet: %d", code)
	}
	if code, _ := call("POST", "/api/tts", `{"lang":"ru","text":"  "}`); code != 400 {
		t.Errorf("empty text: %d", code)
	}
	if code, _ := call("POST", "/api/tts", `{"lang":"ru","text":"`+strings.Repeat("я", ttsMaxChars+1)+`"}`); code != 400 {
		t.Errorf("too long: %d", code)
	}
	if code, _ := call("POST", "/api/voice", `{"id":"nope"}`); code != 400 {
		t.Errorf("unknown voice: %d", code)
	}
	if code, _ := call("DELETE", "/api/voice/ru-a", ""); code != 200 || a.voicePresent(&voiceSpecs[0]) {
		t.Errorf("delete: %d", code)
	}
	a.cfg.Voices = map[string]string{"ru": "ru-b"}
	if code, _ := call("DELETE", "/api/voice/ru-b", ""); code != 200 || a.cfg.Voices["ru"] != "" {
		t.Errorf("deleting the chosen voice forgets the choice: %d %v", code, a.cfg.Voices)
	}
	st := a.ttsStateJSON()
	vs := st["voices"].([]map[string]any)
	if len(vs) != 3 || vs[0]["present"] != false || vs[2]["file"] != "vits-piper-en_US-c-medium.tar.bz2" {
		t.Errorf("state: %v", vs)
	}
}
