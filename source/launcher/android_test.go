package main

import (
	"encoding/json"
	"io"
	"log"
	"net"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"testing"
	"time"
)

// Android (1.2): with an access key every request needs it — in the cookie of the window or the header of the app.
func TestAccessKey(t *testing.T) {
	logger = log.New(io.Discard, "", 0)
	get := func(a *App, path string, set func(*http.Request)) int {
		req := httptest.NewRequest(http.MethodGet, path, nil)
		req.Host = "127.0.0.1:8765"
		if set != nil {
			set(req)
		}
		rec := httptest.NewRecorder()
		a.routes().ServeHTTP(rec, req)
		return rec.Code
	}
	cookie := func(v string) func(*http.Request) {
		return func(r *http.Request) { r.AddCookie(&http.Cookie{Name: accessCookie, Value: v}) }
	}
	header := func(v string) func(*http.Request) { return func(r *http.Request) { r.Header.Set("X-Tdoc-Key", v) } }

	desktop := &App{dataDir: t.TempDir()}
	if c := get(desktop, "/api/ping", nil); c != 200 {
		t.Fatalf("computer, no key: %d, want 200", c)
	}
	phone := &App{dataDir: t.TempDir(), accessKey: "3f9c2a7d41b8e650"}
	for _, tc := range []struct {
		name string
		set  func(*http.Request)
		want int
	}{
		{"no key", nil, 403},
		{"wrong cookie", cookie("3f9c2a7d41b8e651"), 403},
		{"empty cookie", cookie(""), 403},
		{"wrong header", header("x"), 403},
		{"cookie of the window", cookie("3f9c2a7d41b8e650"), 200},
		{"header of the app", header("3f9c2a7d41b8e650"), 200},
	} {
		for _, path := range []string{"/api/ping", "/api/saved-files", "/"} {
			if c := get(phone, path, tc.set); (c == 403) != (tc.want == 403) {
				t.Errorf("phone, %s, %s: %d, want %d", tc.name, path, c, tc.want)
			}
		}
	}
	// another site stays forbidden even with the key
	req := httptest.NewRequest(http.MethodGet, "/api/ping", nil)
	req.Host = "evil.example:8765"
	req.Header.Set("X-Tdoc-Key", "3f9c2a7d41b8e650")
	rec := httptest.NewRecorder()
	phone.routes().ServeHTTP(rec, req)
	if rec.Code != 403 {
		t.Errorf("another host with the key: %d, want 403", rec.Code)
	}
}

func TestTakeAccessKey(t *testing.T) {
	t.Setenv("TDOC_ACCESS_KEY", "k1")
	if k := takeAccessKey(); k != "k1" {
		t.Fatalf("key %q", k)
	}
	if _, ok := os.LookupEnv("TDOC_ACCESS_KEY"); ok {
		t.Fatal("the key stays in the environment of the engine")
	}
}

// With an access key the launcher never hands over to a copy already on the port (it would not know the key).
func TestListenWithAccessKey(t *testing.T) {
	logger = log.New(io.Discard, "", 0)
	other := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, 200, map[string]any{"app": appID, "version": appVersion})
	}))
	defer other.Close()
	_, ps, _ := net.SplitHostPort(strings.TrimPrefix(other.URL, "http://"))
	port, _ := strconv.Atoi(ps)

	if ln, existing := (&App{}).listen(port); ln != nil || existing == "" {
		t.Fatalf("computer: want the copy already running, got %v %q", ln, existing)
	}
	ln, existing := (&App{accessKey: "k"}).listen(port)
	if ln == nil || existing != "" {
		t.Fatalf("phone: want an own port, got %v %q", ln, existing)
	}
	defer ln.Close()
	if ln.Addr().(*net.TCPAddr).Port == port {
		t.Fatal("phone: the same port")
	}
}

func TestPortFile(t *testing.T) {
	logger = log.New(io.Discard, "", 0)
	p := filepath.Join(t.TempDir(), "port")
	writePortFile(p, 8765)
	b, err := os.ReadFile(p)
	if err != nil || string(b) != "8765\n" {
		t.Fatalf("port file: %q %v", b, err)
	}
	if st, _ := os.Stat(p); st.Mode().Perm() != 0o600 {
		t.Errorf("port file mode %v", st.Mode().Perm())
	}
	if _, err := os.Stat(p + ".tmp"); err == nil {
		t.Error("the temporary file stays")
	}
	writePortFile("", 1) // no variable: nothing written, no panic
}

// The catalog of a phone: E2B · Q4_0 always, E4B · Q4_0 from 12 GB (≈11 GiB in /proc/meminfo), Q8_0 never.
func TestPhoneCatalog(t *testing.T) {
	ids := func(ms []ModelSpec) string {
		var s []string
		for _, m := range ms {
			s = append(s, m.ID)
		}
		return strings.Join(s, " ")
	}
	for _, tc := range []struct {
		ram  float64
		want string
	}{
		{3.6, "g4-e2b"},         // a "4 GB" phone: E2B (the window warns about the memory)
		{7.4, "g4-e2b"},         // "8 GB" (the author's tablet)
		{11.2, "g4-e2b g4-e4b"}, // "12 GB" (the author's phone)
		{15.1, "g4-e2b g4-e4b"}, // "16 GB": still no Q8_0
	} {
		if got := ids(phoneCatalog(modelSpecs, tc.ram)); got != tc.want {
			t.Errorf("%.1f GiB: %q, want %q", tc.ram, got, tc.want)
		}
	}
	test := []ModelSpec{{ID: "tiny"}, {ID: "g4-e2b-q8"}}
	if got := ids(phoneCatalog(test, 7.4)); got != "tiny" {
		t.Errorf("test catalog: %q", got)
	}
	only := []ModelSpec{{ID: "g4-e4b-q8"}}
	if got := ids(phoneCatalog(only, 7.4)); got != "g4-e4b-q8" {
		t.Errorf("nothing left: the catalog must stay, got %q", got)
	}
	// a downloaded file of a hidden model is an own file then
	a := &App{modelsDir: t.TempDir()}
	saved := modelSpecs
	defer func() { modelSpecs = saved }()
	modelSpecs = phoneCatalog(modelSpecs, 7.4)
	if err := os.WriteFile(filepath.Join(a.modelsDir, "gemma-4-E4B_q4_0-it.gguf"), []byte("GGUF"), 0o644); err != nil {
		t.Fatal(err)
	}
	if cm := a.customModels(); len(cm) != 1 || cm[0].File != "gemma-4-E4B_q4_0-it.gguf" {
		t.Errorf("hidden model's file: %+v", cm)
	}
}

func TestDeviceInfo(t *testing.T) {
	m := Machine{CPU: "", OS: "Linux", RamGB: 7.4, Threads: 8}
	if got := deviceInfo(m); got != m {
		t.Errorf("no variables: %+v", got)
	}
	t.Setenv("TDOC_OS", "Android 16 (motorola edge 60 neo)")
	t.Setenv("TDOC_CPU", "MT6878")
	got := deviceInfo(m)
	if got.OS != "Android 16 (motorola edge 60 neo)" || got.CPU != "MT6878" || got.RamGB != 7.4 {
		t.Errorf("with variables: %+v", got)
	}
}

// Android: «Открыть папку» answers with a clear message instead of trying xdg-open.
func TestOpenFolderOnAndroid(t *testing.T) {
	logger = log.New(io.Discard, "", 0)
	defer func(v bool) { isAndroid = v }(isAndroid)
	isAndroid = true
	a := &App{dataDir: t.TempDir()}
	for _, lang := range []string{"ru", "en"} {
		setUILang(lang)
		req := httptest.NewRequest(http.MethodPost, "/api/open", strings.NewReader(`{"what":"saved"}`))
		req.Host = "127.0.0.1:8765"
		rec := httptest.NewRecorder()
		a.routes().ServeHTTP(rec, req)
		var res struct{ Error string }
		_ = json.Unmarshal(rec.Body.Bytes(), &res)
		if rec.Code != 400 || !strings.Contains(res.Error, "Android") || strings.Contains(res.Error, "xdg-open") {
			t.Errorf("%s: %d %s", lang, rec.Code, rec.Body.String())
		}
	}
	setUILang("ru")
}

// engine_busy (Android: the notification of the work): true while a request to the engine is under way.
func TestEngineBusy(t *testing.T) {
	logger = log.New(io.Discard, "", 0)
	release := make(chan struct{})
	eng := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		<-release
		_, _ = w.Write([]byte(`{"choices":[]}`))
	}))
	defer eng.Close()
	u, _ := url.Parse(eng.URL)
	port, _ := strconv.Atoi(u.Port())
	a := &App{engPort: port, engKey: "k", engStatus: "ready"}
	done := make(chan struct{})
	go func() {
		req := httptest.NewRequest(http.MethodPost, "/v1/chat/completions", strings.NewReader(`{}`))
		a.handleProxy(httptest.NewRecorder(), req)
		close(done)
	}()
	until := time.Now().Add(3 * time.Second)
	for a.engBusy.Load() == 0 && time.Now().Before(until) {
		time.Sleep(10 * time.Millisecond)
	}
	if a.engBusy.Load() != 1 {
		t.Fatal("not busy during the request")
	}
	close(release)
	<-done
	if a.engBusy.Load() != 0 {
		t.Fatal("still busy after the request")
	}
}
