package main

import (
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// «Пропустить» on the first-start screen (0.9.5): the main window without a model (phase "nomodel") until there is a
// model; config.json keeps the choice; once a model is downloaded or chosen, a missing model is the first-start
// screen again, as before
func TestSkipSetup(t *testing.T) {
	a := testApp(t)
	a.root = t.TempDir()
	a.modelsDir = filepath.Join(a.root, "models")
	a.engineDir = filepath.Join(a.root, "engine", "linux-amd64")
	_ = os.MkdirAll(a.modelsDir, 0o755)
	_ = os.MkdirAll(a.engineDir, 0o755)
	a.cfg = defaultConfig()
	a.pkg, _ = currentEnginePackage()
	a.engStatus = "stopped"
	phase := func() string { return a.stateJSON()["phase"].(string) }
	if p := phase(); p != "setup" {
		t.Fatalf("first start: phase %q", p)
	}
	h := a.routes()
	call := func(method, path string) int {
		rec := httptest.NewRecorder()
		req := httptest.NewRequest(method, path, nil)
		req.Host = "127.0.0.1:8765"
		h.ServeHTTP(rec, req)
		return rec.Code
	}
	if code := call("GET", "/api/skip-setup"); code != 405 {
		t.Errorf("GET /api/skip-setup: %d", code)
	}
	if code := call("POST", "/api/skip-setup"); code != 200 || !a.cfg.SetupSkipped {
		t.Fatalf("skip: %d, setup_skipped %v", code, a.cfg.SetupSkipped)
	}
	if b, _ := os.ReadFile(filepath.Join(a.root, "config.json")); !strings.Contains(string(b), `"setup_skipped": true`) {
		t.Errorf("config.json keeps the choice: %s", b)
	}
	if p := phase(); p != "nomodel" {
		t.Errorf("after «Пропустить»: phase %q", p)
	}
	// the engine is there, still no model: the main window
	server := filepath.Join(a.engineDir, "b1", a.pkg.Server)
	_ = os.MkdirAll(filepath.Dir(server), 0o755)
	_ = os.WriteFile(server, []byte("exe"), 0o755)
	_ = os.WriteFile(filepath.Join(a.engineDir, "engine.json"), []byte(`{"version": "b1", "server": "b1/`+a.pkg.Server+`"}`), 0o644)
	if p := phase(); p != "nomodel" {
		t.Errorf("engine, no model: phase %q", p)
	}
	// an own .gguf file put into models: still the main window, the file is chosen in the model menu
	_ = os.WriteFile(filepath.Join(a.modelsDir, "my-model.gguf"), []byte("GGUF"), 0o644)
	if p := phase(); p != "nomodel" {
		t.Errorf("own file, nothing chosen: phase %q", p)
	}
	st := a.stateJSON()
	if st["had_model"] != true {
		t.Errorf("had_model with an own file: %v", st["had_model"])
	}
	// a model is there now: the choice is forgotten (config.json too)
	a.clearSetupSkipped()
	if a.cfg.SetupSkipped {
		t.Error("setup_skipped is still set")
	}
	if b, _ := os.ReadFile(filepath.Join(a.root, "config.json")); strings.Contains(string(b), "setup_skipped") {
		t.Errorf("config.json after the first model: %s", b)
	}
	if p := phase(); p != "setup" {
		t.Errorf("the active model is missing again, after a model was there: phase %q (want the screen «Нужно скачать модель»)", p)
	}
}
