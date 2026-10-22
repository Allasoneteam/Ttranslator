package main

import (
	"encoding/json"
	"net/http/httptest"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"testing"
)

// every message wrapped in tr("…") and every catalogue text has an English and a German translation
// with the same format verbs; the dictionaries hold nothing else
func TestTranslations(t *testing.T) {
	keys := map[string]bool{}
	files, _ := filepath.Glob("*.go")
	re := regexp.MustCompile(`\btr\(("(?:[^"\\]|\\.)*")\)`)
	for _, f := range files {
		if strings.HasSuffix(f, "_test.go") {
			continue
		}
		b, _ := os.ReadFile(f)
		for _, m := range re.FindAllStringSubmatch(string(b), -1) {
			s, err := strconv.Unquote(m[1])
			if err != nil {
				t.Fatalf("%s: %v", m[1], err)
			}
			keys[s] = true
		}
	}
	for _, m := range modelSpecs {
		keys[m.Note], keys[m.Group] = true, true
	}
	for _, s := range []string{groupCustom, "свой файл", "Тестовые модели", "Windows x64, процессор", "Linux x64, процессор"} {
		keys[s] = true
	}
	verbs := regexp.MustCompile(`%[a-z]`)
	for _, lang := range []struct {
		name string
		m    map[string]string
	}{{"en", msgEN}, {"de", msgDE}} {
		for k := range keys {
			v, ok := lang.m[k]
			if !ok {
				t.Errorf("%s: no translation for %q", lang.name, k)
				continue
			}
			if strings.Join(verbs.FindAllString(k, -1), "") != strings.Join(verbs.FindAllString(v, -1), "") {
				t.Errorf("%s: format verbs differ: %q / %q", lang.name, k, v)
			}
		}
		for k := range lang.m {
			if !keys[k] {
				t.Errorf("%s: translation of an unused message %q", lang.name, k)
			}
		}
	}
	setUILang("de")
	if tr("неверный запрос") != "ungültige Anfrage" || tr("нет такого текста") != "нет такого текста" {
		t.Errorf("tr in German")
	}
	setUILang("ru")
	if tr("неверный запрос") != "неверный запрос" {
		t.Errorf("tr in Russian")
	}
}

func TestSettings(t *testing.T) {
	a := testApp(t)
	a.root = t.TempDir()
	a.uiDir = filepath.Join(a.root, "ui")
	_ = os.MkdirAll(a.uiDir, 0o755)
	_ = os.WriteFile(filepath.Join(a.uiDir, "index.html"), []byte("<!doctype html>\n<html lang=\"ru\">\n<head></head><body>x</body></html>"), 0o644)
	a.cfg = defaultConfig()
	defer setUILang("ru")
	h := a.routes()
	call := func(method, path, body string) (int, string) {
		req := httptest.NewRequest(method, path, strings.NewReader(body))
		req.Host = "127.0.0.1:8765"
		rec := httptest.NewRecorder()
		h.ServeHTTP(rec, req)
		return rec.Code, rec.Body.String()
	}
	if code, body := call("GET", "/api/settings", ""); code != 200 || !strings.Contains(body, `"ui_language":"ru"`) || !strings.Contains(body, `"theme":"light"`) || !strings.Contains(body, `"font_scale":100`) {
		t.Fatalf("defaults: %d %s", code, body)
	}
	if code, body := call("GET", "/", ""); code != 200 || !strings.Contains(body, `<html lang="ru" data-theme="light" data-font="100">`) {
		t.Errorf("page: %d %s", code, body)
	}
	if code, body := call("POST", "/api/settings", `{"ui_language":"de","theme":"dark"}`); code != 200 || !strings.Contains(body, `"ui_language":"de"`) {
		t.Fatalf("change: %d %s", code, body)
	}
	if curLang() != "de" {
		t.Errorf("messages follow the language: %s", curLang())
	}
	var saved Config
	b, _ := os.ReadFile(filepath.Join(a.root, "config.json"))
	if err := json.Unmarshal(b, &saved); err != nil || saved.UILanguage != "de" || saved.Theme != "dark" || saved.FontScale != 100 || saved.ActiveModel != defaultModelID {
		t.Errorf("config.json: %s", b)
	}
	if _, body := call("GET", "/", ""); !strings.Contains(body, `<html lang="de" data-theme="dark" data-font="100">`) || !strings.Contains(body, "<head></head><body>x</body>") {
		t.Errorf("page after change: %s", body)
	}
	for _, bad := range []string{`{"ui_language":"fr"}`, `{"theme":"blue"}`, `{"font_scale":101}`, `not json`} {
		if code, body := call("POST", "/api/settings", bad); code != 400 {
			t.Errorf("%s: %d %s", bad, code, body)
		}
	}
	if code, body := call("POST", "/api/settings", `{"font_scale":130}`); code != 200 || !strings.Contains(body, `"font_scale":130`) || !strings.Contains(body, `"theme":"dark"`) {
		t.Errorf("font: %d %s", code, body)
	}
	// start options: welcome window, window kind, loading the model at start
	if _, body := call("GET", "/api/settings", ""); !strings.Contains(body, `"show_welcome":true`) || !strings.Contains(body, `"launch_mode":"window"`) || !strings.Contains(body, `"load_model_at_start":true`) || !strings.Contains(body, `"start_maximized":true`) {
		t.Errorf("start defaults: %s", body)
	}
	if code, body := call("POST", "/api/settings", `{"show_welcome":false,"launch_mode":"tab","load_model_at_start":false}`); code != 200 ||
		!strings.Contains(body, `"show_welcome":false`) || !strings.Contains(body, `"launch_mode":"tab"`) || !strings.Contains(body, `"load_model_at_start":false`) {
		t.Errorf("start options: %d %s", code, body)
	}
	b, _ = os.ReadFile(filepath.Join(a.root, "config.json"))
	if err := json.Unmarshal(b, &saved); err != nil || saved.ShowWelcome || saved.LaunchMode != "tab" || saved.LoadModelAtStart {
		t.Errorf("config.json with start options: %s", b)
	}
	if code, _ := call("POST", "/api/settings", `{"launch_mode":"kiosk"}`); code != 400 {
		t.Errorf("bad launch_mode accepted: %d", code)
	}
	if code, body := call("POST", "/api/settings", `{"launch_mode":"window","start_maximized":false}`); code != 200 || !strings.Contains(body, `"launch_mode":"window"`) || !strings.Contains(body, `"start_maximized":false`) {
		t.Errorf("the app window, not maximized: %d %s", code, body)
	}
	if code, _ := call("POST", "/api/settings", `{"launch_mode":"app"}`); code != 400 {
		t.Errorf("launch_mode app (before 0.9.2) is no longer a choice: %d", code)
	}
	// unknown values in config.json fall back to the defaults; an old config.json gets the new options on
	c := defaultConfig()
	c.UILanguage, c.Theme, c.FontScale, c.LaunchMode = "xx", "", 7, "x"
	normSettings(&c)
	if c.UILanguage != "ru" || c.Theme != "light" || c.FontScale != 100 || c.LaunchMode != "window" {
		t.Errorf("normSettings: %+v", c)
	}
	_ = os.WriteFile(filepath.Join(a.root, "config.json"), []byte(`{"active_model":"g4-e2b","ui_language":"en"}`), 0o644)
	if old := a.loadConfig(); !old.ShowWelcome || old.LaunchMode != "window" || !old.LoadModelAtStart || old.UILanguage != "en" || !old.StartMaximized {
		t.Errorf("config.json of an older version: %+v", old)
	}
	// 0.9.2: the Edge/Chrome window ("app", the default before) becomes the app window ("window")
	_ = os.WriteFile(filepath.Join(a.root, "config.json"), []byte(`{"active_model":"g4-e2b","launch_mode":"app"}`), 0o644)
	if old := a.loadConfig(); old.LaunchMode != "window" || !old.StartMaximized {
		t.Errorf("launch_mode app of 0.9.1: %+v", old)
	}
}

// The download catalogue: the four Gemma 4 files chosen by the author, each pinned to a repository commit with
// its size and SHA-256; the file name is the last part of the address.
func TestCatalog(t *testing.T) {
	want := []string{"Gemma 4 E2B · Q4_0", "Gemma 4 E2B · Q8_0", "Gemma 4 E4B · Q4_0", "Gemma 4 E4B · Q8_0"}
	if len(modelSpecs) != len(want) {
		t.Fatalf("catalogue: %d models", len(modelSpecs))
	}
	pinned := regexp.MustCompile(`^https://huggingface\.co/(google|ggml-org)/[^/]+/resolve/[0-9a-f]{40}/([^/]+)$`)
	hex64 := regexp.MustCompile(`^[0-9a-f]{64}$`)
	ids := map[string]bool{}
	for i, m := range modelSpecs {
		u := pinned.FindStringSubmatch(m.URL)
		if m.Name != want[i] || m.Family != "chat" || m.Group != groupGemma || u == nil || u[2] != m.File || !hex64.MatchString(m.SHA256) ||
			m.Size < 2e9 || m.Size > 9e9 || m.Note == "" || ids[m.ID] || !strings.Contains(m.Page, u[1]) {
			t.Errorf("model %d: %+v", i, m)
		}
		ids[m.ID] = true
	}
	if modelSpecs[0].ID != defaultModelID {
		t.Errorf("the first model is the default one: %s", modelSpecs[0].ID)
	}
}
