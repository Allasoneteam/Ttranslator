package main

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// The picture files (vision.go): one per size of Gemma 4 in the catalogue, from the commits of the Q8_0 models, with
// size and SHA-256; own .gguf files read no pictures; an mmproj file is never listed as a model.
func TestVisionCatalog(t *testing.T) {
	for _, m := range modelSpecs {
		v := visionFor(m.ID)
		if v == nil {
			t.Errorf("%s: no picture file", m.ID)
			continue
		}
		size := "E2B"
		if strings.Contains(m.ID, "e4b") {
			size = "E4B"
		}
		if !strings.Contains(v.File, size) || !strings.Contains(v.Name, size) {
			t.Errorf("%s: picture file of another size: %s", m.ID, v.File)
		}
	}
	for _, v := range visionSpecs {
		if !strings.HasPrefix(v.File, "mmproj-") || !strings.HasSuffix(v.File, ".gguf") || len(v.SHA256) != 64 || v.Size < 400<<20 || v.Size > 700<<20 {
			t.Errorf("%s: %s, %d bytes, sha %q", v.ID, v.File, v.Size, v.SHA256)
		}
		if !strings.HasPrefix(v.URL, "https://huggingface.co/ggml-org/") || !strings.Contains(v.URL, "/resolve/") || !strings.HasSuffix(v.URL, "/"+v.File) {
			t.Errorf("%s: not a pinned official address: %s", v.ID, v.URL)
		}
		for _, id := range v.For {
			m := findModelSpec(id)
			if m == nil {
				t.Errorf("%s: for an unknown model %s", v.ID, id)
			} else if strings.HasSuffix(m.ID, "-q8") && !strings.HasPrefix(v.URL, strings.TrimSuffix(m.URL, m.File)) {
				t.Errorf("%s: not the commit of the Q8_0 model %s: %s", v.ID, m.ID, v.URL)
			}
		}
		if findVision(v.ID) == nil {
			t.Errorf("findVision(%s)", v.ID)
		}
	}
	if visionFor("file:own.gguf") != nil || visionFor("") != nil {
		t.Error("own files read pictures")
	}
	// the picture file is in the models folder, but it is not a model
	a := testApp(t)
	a.modelsDir = t.TempDir()
	_ = os.WriteFile(filepath.Join(a.modelsDir, visionSpecs[0].File), []byte("x"), 0o644)
	_ = os.WriteFile(filepath.Join(a.modelsDir, "own.gguf"), []byte("x"), 0o644)
	if ms := a.customModels(); len(ms) != 1 || ms[0].File != "own.gguf" {
		t.Errorf("own models: %v", ms)
	}
}

func findModelSpec(id string) *ModelSpec {
	for i := range modelSpecs {
		if modelSpecs[i].ID == id {
			return &modelSpecs[i]
		}
	}
	return nil
}

// The engine reads a picture as 1120 tokens, and they fit into one micro-batch.
func TestVisionArgs(t *testing.T) {
	args := visionArgs("models/mm.gguf")
	val := func(flag string) string {
		for i, a := range args {
			if a == flag && i+1 < len(args) {
				return args[i+1]
			}
		}
		return ""
	}
	if val("--mmproj") != "models/mm.gguf" || val("--image-min-tokens") != "1120" || val("--image-max-tokens") != "1120" {
		t.Errorf("args: %v", args)
	}
	ub, b := val("-ub"), val("-b")
	if ub == "" || b == "" || atoi(ub) < visionTokens || atoi(b) < atoi(ub) {
		t.Errorf("batch %s, micro-batch %s for %d tokens", b, ub, visionTokens)
	}
	if visionNote("") != "" || !strings.Contains(visionNote("models/mm.gguf"), "mm.gguf") {
		t.Error("visionNote")
	}
}

func atoi(s string) int {
	n := 0
	for _, c := range s {
		if c < '0' || c > '9' {
			return -1
		}
		n = n*10 + int(c-'0')
	}
	return n
}

// /api/vision: pictures are asked for in this run; without the file — nothing to load ("present": false), the
// download starts only on "download"; with it — the engine would restart (here it is not running); a model without
// a picture file — 409; the state tells the page; deleting the file.
func TestVisionRoutes(t *testing.T) {
	a := testApp(t)
	a.root = t.TempDir()
	a.modelsDir = t.TempDir()
	a.engineDir = t.TempDir()
	a.cfg = defaultConfig()
	a.cfg.ActiveModel = "g4-e4b"
	mux := http.NewServeMux()
	a.visionRoutes(mux)
	call := func(method, path, body string) (int, map[string]any) {
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, httptest.NewRequest(method, path, strings.NewReader(body)))
		var j map[string]any
		_ = json.Unmarshal(rec.Body.Bytes(), &j)
		return rec.Code, j
	}
	st := func() map[string]any { a.mu.Lock(); defer a.mu.Unlock(); return a.visionStateJSON() }
	if s := st(); s["current"] != "mm-e4b" || s["on"] != false || s["loaded"] != false || s["tokens"] != visionTokens {
		t.Errorf("state: %v", s)
	}
	for _, bad := range []string{`{}`, `{"action":"x"}`, `x`} {
		if code, _ := call("POST", "/api/vision", bad); code != 400 {
			t.Errorf("%s: %d", bad, code)
		}
	}
	if code, j := call("POST", "/api/vision", `{"action":"on"}`); code != 200 || j["present"] != false || !a.visionOn {
		t.Errorf("on without the file: %d %v", code, j)
	}
	if a.mdl.Active {
		t.Error("a download started without being asked")
	}
	// the file is there: "on" restarts a running engine only (not running here)
	v := findVision("mm-e4b")
	if err := os.WriteFile(a.visionPath(v), make([]byte, 16), 0o644); err != nil {
		t.Fatal(err)
	}
	if a.visionPresent(v) {
		t.Error("a file of the wrong size counts")
	}
	saved := visionSpecs
	defer func() { visionSpecs = saved }()
	visionSpecs = append([]VisionSpec{}, saved...)
	visionSpecs[1].Size = 16
	v = findVision("mm-e4b")
	if !a.visionPresent(v) {
		t.Fatal("the file is not seen")
	}
	if code, j := call("POST", "/api/vision", `{"action":"on"}`); code != 200 || j["present"] != true || j["restarting"] != false {
		t.Errorf("on with the file: %d %v", code, j)
	}
	a.mu.Lock()
	p, on := a.visionToLoad(a.findModel("g4-e4b"))
	p2, on2 := a.visionToLoad(a.findModel("g4-e2b"))
	a.mu.Unlock()
	if !on || p != a.visionPath(v) || on2 || p2 != "" {
		t.Errorf("visionToLoad: %q %v; E2B: %q %v", p, on, p2, on2)
	}
	files := st()["files"].([]map[string]any)
	if len(files) != 2 || files[1]["present"] != true || files[0]["present"] != false {
		t.Errorf("files: %v", files)
	}
	// own model: no pictures
	a.cfg.ActiveModel = "file:own.gguf"
	if code, _ := call("POST", "/api/vision", `{"action":"download"}`); code != 409 {
		t.Errorf("own model: %d", code)
	}
	if st()["current"] != "" {
		t.Error("own model has a picture file")
	}
	a.cfg.ActiveModel = "g4-e4b"
	// delete
	if code, _ := call("DELETE", "/api/vision/nope", ""); code != 404 {
		t.Errorf("unknown: %d", code)
	}
	if code, _ := call("GET", "/api/vision/mm-e4b", ""); code != 405 {
		t.Errorf("GET: %d", code)
	}
	if code, _ := call("DELETE", "/api/vision/mm-e4b", ""); code != 200 || a.visionPresent(v) {
		t.Errorf("delete: %d", code)
	}
	if code, _ := call("POST", "/api/vision", `{"action":"cancel"}`); code != 200 {
		t.Errorf("cancel: %d", code)
	}
	// the model menu downloads a given file without asking for pictures
	a.visionOn = false
	for _, bad := range []string{`{"action":"download","id":"nope"}`, `{"action":"on","id":"mm-e2b"}`} {
		if code, _ := call("POST", "/api/vision", bad); code != 400 {
			t.Errorf("%s: %d", bad, code)
		}
	}
	if err := os.WriteFile(a.visionPath(v), make([]byte, 16), 0o644); err != nil {
		t.Fatal(err)
	}
	if code, j := call("POST", "/api/vision", `{"action":"download","id":"mm-e4b"}`); code != 200 || j["present"] != true || a.visionOn || a.mdl.Active {
		t.Errorf("download of a present file: %d %v", code, j)
	}
}

// The PDF.js modules and decoders get their content types (module scripts are refused otherwise); a page of a scan
// fits into a request to the engine.
func TestStaticTypes(t *testing.T) {
	for name, want := range map[string]string{
		"pdfjs/pdf.min.mjs": "text/javascript; charset=utf-8", "pdfjs/wasm/jbig2.wasm": "application/wasm",
		"tests.txt": "text/plain; charset=utf-8", "pdfjs/README.md": "", "index.html": "",
	} {
		if got := staticType(name); got != want {
			t.Errorf("%s: %q", name, got)
		}
	}
	if maxEngineRequest < 16<<20 {
		t.Errorf("maxEngineRequest %d", maxEngineRequest)
	}
	a := testApp(t)
	a.uiDir = t.TempDir()
	_ = os.MkdirAll(filepath.Join(a.uiDir, "pdfjs"), 0o755)
	_ = os.WriteFile(filepath.Join(a.uiDir, "pdfjs", "pdf.min.mjs"), []byte("export {}"), 0o644)
	rec := httptest.NewRecorder()
	a.handleStatic(rec, httptest.NewRequest("GET", "/pdfjs/pdf.min.mjs", nil))
	if rec.Code != 200 || rec.Header().Get("Content-Type") != "text/javascript; charset=utf-8" || rec.Body.String() != "export {}" {
		t.Errorf("module: %d %q %q", rec.Code, rec.Header().Get("Content-Type"), rec.Body.String())
	}
}

// The line of the engine log shown when the engine fails with the picture file.
func TestEngineErrorLine(t *testing.T) {
	tail := "0.00.033.000 I srv    load_model: loading model\n" +
		"0.00.033.106 E gguf_init_from_reader: invalid magic characters: '.???', expected 'GGUF'\n" +
		"0.00.033.150 E srv    load_model: failed to load multimodal model, '/m/mmproj.gguf'\n"
	if got := engineErrorLine(tail); got != "gguf_init_from_reader: invalid magic characters: '.???', expected 'GGUF'" {
		t.Fatalf("first error line: %q", got)
	}
	if got := engineErrorLine("0.00.001 I all is well\nsegmentation fault"); got != "" {
		t.Fatalf("no error line: %q", got)
	}
	long := "0.1 E " + strings.Repeat("я", 300)
	if got := engineErrorLine(long); len([]rune(got)) != 241 || !strings.HasSuffix(got, "…") {
		t.Fatalf("long line: %d runes", len([]rune(got)))
	}
}
