// Ttranslator launcher.
//
// One small program next to the UI and the model:
//   - on first run downloads the llama.cpp engine and the translation model (with progress and checks);
//   - starts llama-server on 127.0.0.1 and passes the UI's requests to it;
//   - serves the UI (ui/index.html), stores saved translations in data/saved, glossaries in data/glossary
//     and test reports in data/reports;
//   - on request downloads Piper voices and reads texts aloud with sherpa-onnx (tts.go);
//   - opens the UI as an app window (Edge/Chrome) and exits when that window is closed.
//
// Standard library only, so it builds offline for Windows and Linux.
package main

import (
	"archive/tar"
	"archive/zip"
	"bytes"
	"compress/gzip"
	"context"
	"crypto/rand"
	"crypto/sha256"
	"embed"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"io/fs"
	"log"
	"net"
	"net/http"
	"net/http/httputil"
	"net/url"
	"os"
	"os/exec"
	"os/signal"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

const (
	appID      = "tdoc-translator"
	appVersion = "0.9.4"

	// model selected on first start and when the configured one is gone
	defaultModelID = "g4-e2b"

	engineVersion = "b11435"
	engineRelease = "https://github.com/ggml-org/llama.cpp/releases/download/" + engineVersion + "/"
)

// ---------------------------------------------------------------- models

type ModelSpec struct {
	ID     string `json:"id"`
	Name   string `json:"name"`
	Group  string `json:"group"`
	Family string `json:"family"` // "hymt": Hy-MT translation prompts; "chat": general instruction prompts
	Note   string `json:"note"`
	File   string `json:"file"`
	URL    string `json:"url"`
	Page   string `json:"page"`
	Size   int64  `json:"size"`
	SHA256 string `json:"sha256"`
	Custom bool   `json:"custom"`
}

// Download URLs are pinned to repository commits, so the checksums below stay valid. The catalogue offers the
// four Gemma 4 files chosen by the author (18.10.2026); other models (for example Hy-MT2) can still be used as
// own .gguf files in the models folder.
const (
	hfG4E2B   = "https://huggingface.co/google/gemma-4-E2B-it-qat-q4_0-gguf/resolve/675cff42a74c774d6cb76f76d8eacb49b48c9b93/"
	hfG4E2BQ8 = "https://huggingface.co/ggml-org/gemma-4-E2B-it-GGUF/resolve/b4243c156154b6dca9324415f8c7ccc098b4aed1/"
	hfG4E4B   = "https://huggingface.co/google/gemma-4-E4B-it-qat-q4_0-gguf/resolve/4b4a2c1d584be7264f87aac328a1bc739ce81b6c/"
	hfG4E4BQ8 = "https://huggingface.co/ggml-org/gemma-4-E4B-it-GGUF/resolve/b8093469224f83f5c38f691eb906c380e9e63114/"

	groupGemma  = "Gemma 4 — универсальная: перевод, правка, вопросы (Google, Apache 2.0)"
	groupCustom = "Свои файлы из папки models"
)

// Speed notes are relative to Gemma 4 E2B · Q4_0: measured in test reports on a Ryzen 5 3600 where available,
// otherwise estimated from the file size (generation speed is limited by memory bandwidth).
var modelSpecs = []ModelSpec{
	{ID: "g4-e2b", Name: "Gemma 4 E2B · Q4_0", Group: groupGemma, Family: "chat",
		Note: "основная: быстрая, переводит, правит текст и отвечает на вопросы", File: "gemma-4-E2B_q4_0-it.gguf", URL: hfG4E2B + "gemma-4-E2B_q4_0-it.gguf",
		Page: "huggingface.co/google/gemma-4-E2B-it-qat-q4_0-gguf", Size: 3349516256,
		SHA256: "fa401b55b07ee70a54c6dae3903c783a6e65064312529ea57175cb5f8dec6634"},
	{ID: "g4-e2b-q8", Name: "Gemma 4 E2B · Q8_0", Group: groupGemma, Family: "chat",
		Note: "точнее Q4_0, медленнее примерно в 1,5 раза; нужно от 8 ГБ памяти", File: "gemma-4-E2B-it-Q8_0.gguf", URL: hfG4E2BQ8 + "gemma-4-E2B-it-Q8_0.gguf",
		Page: "huggingface.co/ggml-org/gemma-4-E2B-it-GGUF", Size: 4967497152,
		SHA256: "996d08777aadc6bfd3c7375ef70ba25a0f55240075860754fdb18d6d860aa63a"},
	{ID: "g4-e4b", Name: "Gemma 4 E4B · Q4_0", Group: groupGemma, Family: "chat",
		Note: "качественнее E2B, медленнее примерно в 2 раза", File: "gemma-4-E4B_q4_0-it.gguf", URL: hfG4E4B + "gemma-4-E4B_q4_0-it.gguf",
		Page: "huggingface.co/google/gemma-4-E4B-it-qat-q4_0-gguf", Size: 5154941280,
		SHA256: "676c35070db6dbe52f93e9c864ee0fba4eddea94b9c875d9cb10daff453fbaee"},
	{ID: "g4-e4b-q8", Name: "Gemma 4 E4B · Q8_0", Group: groupGemma, Family: "chat",
		Note: "лучшее качество Gemma E4B, медленнее E2B примерно в 3 раза; нужно от 12 ГБ памяти", File: "gemma-4-E4B-it-Q8_0.gguf", URL: hfG4E4BQ8 + "gemma-4-E4B-it-Q8_0.gguf",
		Page: "huggingface.co/ggml-org/gemma-4-E4B-it-GGUF", Size: 8031242688,
		SHA256: "34be82b17b4942d389b9b527170c4b058027abdd32531fda063d3d97dd8ce80a"},
}

// familyFor guesses the prompt family of a model file added by hand.
func familyFor(name string) string {
	l := strings.ToLower(name)
	if strings.Contains(l, "hy-mt") || strings.Contains(l, "hymt") || strings.Contains(l, "hunyuan-mt") {
		return "hymt"
	}
	return "chat"
}

// customModels lists .gguf files in models/ that are not in the catalog.
func (a *App) customModels() []ModelSpec {
	known := map[string]bool{}
	for _, m := range modelSpecs {
		known[strings.ToLower(m.File)] = true
	}
	entries, _ := os.ReadDir(a.modelsDir)
	var out []ModelSpec
	for _, e := range entries {
		n := e.Name()
		ln := strings.ToLower(n)
		if e.IsDir() || !strings.HasSuffix(ln, ".gguf") || known[ln] || strings.Contains(ln, "mmproj") {
			continue
		}
		info, err := e.Info()
		if err != nil || info.Size() == 0 {
			continue
		}
		out = append(out, ModelSpec{ID: "file:" + n, Name: strings.TrimSuffix(n, filepath.Ext(n)), Group: groupCustom,
			Family: familyFor(n), Note: "свой файл", File: n, Size: info.Size(), Custom: true})
	}
	return out
}

func (a *App) findModel(id string) *ModelSpec {
	for i := range modelSpecs {
		if modelSpecs[i].ID == id {
			m := modelSpecs[i]
			return &m
		}
	}
	if strings.HasPrefix(id, "file:") {
		for _, m := range a.customModels() {
			if m.ID == id {
				mm := m
				return &mm
			}
		}
	}
	return nil
}

// fallbackModelID is the default model, or the first catalog entry when the catalog is replaced for tests.
func fallbackModelID() string {
	for _, m := range modelSpecs {
		if m.ID == defaultModelID {
			return defaultModelID
		}
	}
	return modelSpecs[0].ID
}

// ensureActiveValid falls back to the default model if the configured one is gone. Caller holds a.mu.
func (a *App) ensureActiveValid() {
	m := a.findModel(a.cfg.ActiveModel)
	if m == nil || (m.Custom && !a.modelPresent(m)) {
		a.cfg.ActiveModel = fallbackModelID()
		a.saveConfig(a.cfg)
	}
}

// Test hooks, used only when the environment variables are set:
// TDOC_ENGINE_URL replaces the engine archive URL, TDOC_TEST_MODELS points to a JSON list of ModelSpec.
var engineURLOverride string

func applyTestOverrides() {
	engineURLOverride = os.Getenv("TDOC_ENGINE_URL")
	if p := os.Getenv("TDOC_TEST_MODELS"); p != "" {
		b, err := os.ReadFile(p)
		var ms []ModelSpec
		if err == nil && json.Unmarshal(b, &ms) == nil && len(ms) > 0 {
			for i := range ms {
				if ms[i].Family == "" {
					ms[i].Family = "hymt"
				}
				if ms[i].Group == "" {
					ms[i].Group = "Тестовые модели"
				}
			}
			modelSpecs = ms
			logger.Printf("test models from %s", p)
		}
	}
}

func (a *App) engineURL() string {
	if engineURLOverride != "" {
		return engineURLOverride
	}
	return engineRelease + a.pkg.Asset
}

// ---------------------------------------------------------------- engine package per platform

type enginePackage struct {
	Asset  string
	Label  string
	Server string
	Size   int64
	SHA256 string
}

// Sizes and checksums of the official llama.cpp b11435 release files.
func currentEnginePackage() (enginePackage, error) {
	switch runtime.GOOS + "/" + runtime.GOARCH {
	case "windows/amd64":
		return enginePackage{"llama-" + engineVersion + "-bin-win-cpu-x64.zip", "Windows x64, процессор", "llama-server.exe",
			19399527, "3ed50261147e260d80f5cdc7bdccfa13a94882be560a4438e7a69fa519c93fb7"}, nil
	case "linux/amd64":
		return enginePackage{"llama-" + engineVersion + "-bin-ubuntu-x64.tar.gz", "Linux x64, процессор", "llama-server",
			17692966, "ee617d7af304985e268fbc33bdd8fe44110f1dc2f599ecb27bdf08890e6e6e4c"}, nil
	}
	return enginePackage{}, fmt.Errorf(tr("платформа %s/%s пока не поддерживается"), runtime.GOOS, runtime.GOARCH)
}

// ---------------------------------------------------------------- config

type Config struct {
	ActiveModel     string   `json:"active_model"`
	UIPort          int      `json:"ui_port"`
	CtxSize         int      `json:"ctx_size"`
	Threads         int      `json:"threads"`
	EnginePath      string   `json:"engine_path"`
	ExtraEngineArgs []string `json:"extra_engine_args"`
	OpenWindow      bool     `json:"open_window"`
	// interface settings (the Settings panel): language, theme and font size in percent
	UILanguage string `json:"ui_language"`
	Theme      string `json:"theme"`
	FontScale  int    `json:"font_scale"`
	// start options (the welcome window and the Settings panel)
	ShowWelcome      bool   `json:"show_welcome"`        // show the welcome window in a new window
	LaunchMode       string `json:"launch_mode"`         // "window": the app window (own window, window.go; else Edge/Chrome); "tab": a tab of the default browser
	StartMaximized   bool   `json:"start_maximized"`     // the app window starts maximized
	LoadModelAtStart bool   `json:"load_model_at_start"` // load the chosen model when the program starts
	// read aloud: the voice chosen for each language (language code → voice id, tts.go)
	Voices map[string]string `json:"voices,omitempty"`
}

var (
	uiLanguages = map[string]bool{"ru": true, "en": true, "de": true}
	uiThemes    = map[string]bool{"light": true, "dark": true}
	fontScales  = map[int]bool{90: true, 100: true, 115: true, 130: true}
	// "app" (an Edge/Chrome window, the default before 0.9.2) is no longer a choice: it becomes "window", and an
	// Edge/Chrome window opens only when the own window cannot (window.go)
	launchModes = map[string]bool{"window": true, "tab": true}
)

// normSettings replaces unknown interface settings with the defaults.
func normSettings(c *Config) {
	if !uiLanguages[c.UILanguage] {
		c.UILanguage = "ru"
	}
	if !uiThemes[c.Theme] {
		c.Theme = "light"
	}
	if !fontScales[c.FontScale] {
		c.FontScale = 100
	}
	if !launchModes[c.LaunchMode] {
		c.LaunchMode = "window"
	}
}

func (a *App) settingsJSON() map[string]any { // call under a.mu
	return map[string]any{"ui_language": a.cfg.UILanguage, "theme": a.cfg.Theme, "font_scale": a.cfg.FontScale,
		"show_welcome": a.cfg.ShowWelcome, "launch_mode": a.cfg.LaunchMode, "load_model_at_start": a.cfg.LoadModelAtStart,
		"start_maximized": a.cfg.StartMaximized}
}

func defaultConfig() Config {
	return Config{ActiveModel: defaultModelID, UIPort: 8765, CtxSize: 4096, Threads: 0, OpenWindow: true, ExtraEngineArgs: []string{},
		UILanguage: "ru", Theme: "light", FontScale: 100, ShowWelcome: true, LaunchMode: "window", LoadModelAtStart: true,
		StartMaximized: true}
}

// ---------------------------------------------------------------- state

type DownloadState struct {
	Active bool    `json:"active"`
	Item   string  `json:"item"`
	Name   string  `json:"name"`
	Phase  string  `json:"phase"`
	Done   int64   `json:"done"`
	Total  int64   `json:"total"`
	Speed  float64 `json:"speed"`
	Error  string  `json:"error"`
}

type EngineInfo struct {
	Build   string `json:"build"`
	NCtx    int    `json:"n_ctx"`
	Threads int    `json:"threads"`
	LoadMs  int64  `json:"load_ms"`
}

type Machine struct {
	CPU     string  `json:"cpu"`
	Threads int     `json:"threads"`
	RamGB   float64 `json:"ram_gb"`
	OS      string  `json:"os"`
}

type App struct {
	root, uiDir, engineDir, modelsDir, dataDir, logsDir, reportsDir string

	mu             sync.Mutex
	cfg            Config
	pkg            enginePackage
	pkgErr         error
	engStatus      string // stopped, starting, ready, error
	unloaded       bool   // the user unloaded the model from memory: do not start the engine until asked
	noModelAtStart bool   // ...or chose not to load it when the program starts (load_model_at_start)
	startDone      bool   // the start is over: the welcome window has applied its choice, or the user loaded, unloaded or switched the model
	engErr         string
	engLog         string
	engCmd         *exec.Cmd
	engDone        chan struct{}
	engPort        int
	engKey         string
	engStopping    bool
	engInfo        EngineInfo
	dl             DownloadState
	dlCancel       context.CancelFunc
	vdl            DownloadState // download of a voice for reading aloud (and of sherpa-onnx), separate from dl
	vdlCancel      context.CancelFunc
	ttsNoUTF8      bool // Windows: the copy of sherpa-onnx with the UTF-8 manifest does not start here
	machine        Machine

	// Open windows. Every page sends its own id with /api/events and, when the window is closed or reloaded,
	// with /api/closing (pagehide): a page that said it is closing no longer counts as open even if its event
	// stream lingers (some systems keep such connections open).
	pages         map[string]int       // page id → open event streams
	bye           map[string]time.Time // pages that said they are closing
	everConnected bool
	lastGone      time.Time // when the last window went away
	lastGoneBye   bool      // ...and it had said so: exit after byeGrace instead of goneGrace
	started       time.Time

	// the own window (launch_mode "window", window.go)
	windowCmd  *exec.Cmd     // the running window program started by this launcher
	windowDone chan struct{} // closed when it has ended
	windowErr  string        // why it did not open (shown in the settings)
	windowGone time.Time     // when it ended: the window is closed for sure
	ownPages   int           // event streams of pages inside the own window

	savedMu     sync.Mutex
	lastSavedID int64 // last id given to a saved row (milliseconds), under savedMu
	glossMu     sync.Mutex
	ttsMu       sync.Mutex // one phrase is spoken at a time
	uiURL       string
	quit        chan struct{}
	quitOnce    sync.Once
}

//go:embed ui_fallback
var fallbackUI embed.FS

var logger *log.Logger

func main() {
	noWindow := flag.Bool("no-window", false, "do not open the app window")
	portFlag := flag.Int("port", 0, "UI port (default from config.json)")
	flag.Parse()

	exe, err := os.Executable()
	if err != nil {
		fatal("Не удалось определить папку программы: " + err.Error())
	}
	if p, err := filepath.EvalSymlinks(exe); err == nil {
		exe = p
	}
	root := filepath.Dir(exe)
	if env := os.Getenv("TDOC_ROOT"); env != "" {
		root = env
	}

	a := &App{
		root:      root,
		uiDir:     filepath.Join(root, "ui"),
		engineDir: filepath.Join(root, "engine", runtime.GOOS+"-"+runtime.GOARCH),
		modelsDir: filepath.Join(root, "models"),
		dataDir:   filepath.Join(root, "data"),
		engStatus: "stopped",
		started:   time.Now(),
		quit:      make(chan struct{}),
	}
	a.logsDir = filepath.Join(a.dataDir, "logs")
	a.reportsDir = filepath.Join(a.dataDir, "reports")
	for _, d := range []string{a.engineDir, a.modelsDir, a.dataDir, a.logsDir, a.reportsDir} {
		if err := os.MkdirAll(d, 0o755); err != nil {
			fatal("Не удалось создать папку " + d + ": " + err.Error() + "\nВозможно, программа лежит в папке, куда нельзя писать.")
		}
	}
	lf, err := openLauncherLog(a.logsDir)
	if err == nil {
		logger = log.New(lf, "", log.LstdFlags)
	} else {
		logger = log.New(os.Stderr, "", log.LstdFlags)
	}
	logger.Printf("Ttranslator %s, root %s, %s/%s", appVersion, root, runtime.GOOS, runtime.GOARCH)

	a.cfg = a.loadConfig()
	setUILang(a.cfg.UILanguage)
	uiPort := a.cfg.UIPort // the --port flag (tests) is not written to config.json
	if *portFlag > 0 {
		uiPort = *portFlag
	}
	a.pkg, a.pkgErr = currentEnginePackage()
	applyTestOverrides()
	applyTTSTestOverrides()
	a.mu.Lock()
	a.ensureActiveValid()
	if !a.cfg.LoadModelAtStart {
		a.unloaded, a.noModelAtStart = true, true
	}
	a.mu.Unlock()
	a.machine = machineInfo()
	platformInit()

	ln, existing := a.listen(uiPort)
	if existing != "" {
		logger.Printf("already running at %s", existing)
		if !*noWindow {
			a.openUI(existing, true)
		}
		return
	}
	a.uiURL = fmt.Sprintf("http://127.0.0.1:%d/", ln.Addr().(*net.TCPAddr).Port)
	logger.Printf("UI at %s", a.uiURL)
	if a.noModelAtStart {
		logger.Printf("the model is not loaded at start (load_model_at_start is off)")
	}
	a.migrateSaved() // only the running copy touches data: a second copy has returned above
	a.cleanTTSLeftovers()

	srv := &http.Server{Handler: a.routes(), ReadHeaderTimeout: 10 * time.Second}
	go func() {
		if err := srv.Serve(ln); err != nil && !errors.Is(err, http.ErrServerClosed) {
			logger.Printf("http server: %v", err)
		}
	}()

	a.maybeStartEngine()
	if a.cfg.OpenWindow && !*noWindow {
		a.openUI(a.uiURL, false)
	}

	go a.watchdog()
	sig := make(chan os.Signal, 1)
	signal.Notify(sig, os.Interrupt, syscall.SIGTERM, syscall.SIGHUP)
	select {
	case <-sig:
		logger.Printf("signal received")
	case <-a.quit:
	}
	a.closeOwnWindow()
	a.stopEngine()
	ctx, cancel := context.WithTimeout(context.Background(), 2*time.Second)
	defer cancel()
	_ = srv.Shutdown(ctx)
	logger.Printf("bye")
}

func (a *App) shutdown() { a.quitOnce.Do(func() { close(a.quit) }) }

// openLauncherLog appends to data/logs/launcher.log. A second copy of the program (which only
// opens the window of the first one) must not truncate the log the first copy is writing.
// A log over 1 MB is moved to launcher.prev.log; that fails harmlessly while another copy holds it.
func openLauncherLog(dir string) (*os.File, error) {
	p := filepath.Join(dir, "launcher.log")
	if st, err := os.Stat(p); err == nil && st.Size() > 1<<20 {
		_ = os.Rename(p, filepath.Join(dir, "launcher.prev.log"))
	}
	return os.OpenFile(p, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
}

// listen binds the UI port. If our app already runs there, returns its URL instead.
func (a *App) listen(port int) (net.Listener, string) {
	addr := fmt.Sprintf("127.0.0.1:%d", port)
	ln, err := net.Listen("tcp", addr)
	if err == nil {
		return ln, ""
	}
	c := http.Client{Timeout: 2 * time.Second}
	if resp, err2 := c.Get("http://" + addr + "/api/ping"); err2 == nil {
		var p struct{ App string }
		_ = json.NewDecoder(resp.Body).Decode(&p)
		resp.Body.Close()
		if p.App == appID {
			return nil, "http://" + addr + "/"
		}
	}
	ln, err = net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		fatal(tr("Не удалось открыть локальный порт: ") + err.Error())
	}
	return ln, ""
}

func (a *App) loadConfig() Config {
	cfg := defaultConfig()
	p := filepath.Join(a.root, "config.json")
	b, err := os.ReadFile(p)
	if err == nil {
		if err := json.Unmarshal(b, &cfg); err != nil {
			logger.Printf("config.json: %v (using defaults)", err)
			cfg = defaultConfig()
		}
	}
	if cfg.ActiveModel == "" {
		cfg.ActiveModel = defaultModelID
	}
	if cfg.UIPort <= 0 || cfg.UIPort > 65535 {
		cfg.UIPort = 8765
	}
	if cfg.CtxSize < 1024 {
		cfg.CtxSize = 4096
	}
	if cfg.ExtraEngineArgs == nil {
		cfg.ExtraEngineArgs = []string{}
	}
	normSettings(&cfg)
	if err != nil {
		a.saveConfig(cfg)
	}
	return cfg
}

func (a *App) saveConfig(cfg Config) {
	b, _ := json.MarshalIndent(cfg, "", "  ")
	tmp := filepath.Join(a.root, "config.json.tmp")
	if err := os.WriteFile(tmp, append(b, '\n'), 0o644); err == nil {
		_ = os.Rename(tmp, filepath.Join(a.root, "config.json"))
	}
}

// ---------------------------------------------------------------- presence checks

type engineMeta struct {
	Version string `json:"version"`
	Server  string `json:"server"`
}

func (a *App) serverPath() string {
	if a.cfg.EnginePath != "" {
		if st, err := os.Stat(a.cfg.EnginePath); err == nil && !st.IsDir() {
			return a.cfg.EnginePath
		}
		return ""
	}
	if b, err := os.ReadFile(filepath.Join(a.engineDir, "engine.json")); err == nil {
		var m engineMeta
		if json.Unmarshal(b, &m) == nil && m.Server != "" {
			p := filepath.Join(a.engineDir, filepath.FromSlash(m.Server))
			if st, err := os.Stat(p); err == nil && !st.IsDir() {
				return p
			}
		}
	}
	// engine unpacked by hand: look for the server binary and remember it
	if a.pkg.Server == "" || a.dl.Active {
		return ""
	}
	found := ""
	_ = filepath.WalkDir(a.engineDir, func(p string, d fs.DirEntry, err error) error {
		if err == nil && !d.IsDir() && d.Name() == a.pkg.Server && found == "" {
			found = p
		}
		return nil
	})
	if found != "" {
		if rel, err := filepath.Rel(a.engineDir, found); err == nil {
			meta, _ := json.MarshalIndent(engineMeta{Version: "manual", Server: filepath.ToSlash(rel)}, "", "  ")
			_ = os.WriteFile(filepath.Join(a.engineDir, "engine.json"), meta, 0o644)
		}
		if runtime.GOOS != "windows" {
			_ = os.Chmod(found, 0o755)
		}
	}
	return found
}

func (a *App) modelPath(m *ModelSpec) string { return filepath.Join(a.modelsDir, m.File) }

func (a *App) modelPresent(m *ModelSpec) bool {
	if m == nil {
		return false
	}
	st, err := os.Stat(a.modelPath(m))
	if m.Custom {
		return err == nil && !st.IsDir() && st.Size() > 0
	}
	return err == nil && st.Size() == m.Size
}

// ---------------------------------------------------------------- state for the UI

func (a *App) stateJSON() map[string]any {
	a.mu.Lock()
	defer a.mu.Unlock()
	a.ensureActiveValid()
	server := a.serverPath()
	active := a.findModel(a.cfg.ActiveModel)
	activePresent := a.modelPresent(active)

	phase := "ready"
	switch {
	case a.dl.Active:
		phase = "downloading"
	case server == "" || !activePresent:
		phase = "setup"
	case a.unloaded:
		phase = "unloaded"
	case a.engStatus == "error":
		phase = "error"
	case a.engStatus == "ready":
		phase = "ready"
	default:
		phase = "starting"
	}
	if a.pkgErr != nil && server == "" {
		phase = "error"
	}

	models := []map[string]any{}
	anyModel := false
	all := append(append([]ModelSpec{}, modelSpecs...), a.customModels()...)
	for i := range all {
		m := &all[i]
		p := a.modelPresent(m)
		anyModel = anyModel || p
		var partial int64
		if !p && !m.Custom {
			if st, err := os.Stat(a.modelPath(m) + ".part"); err == nil {
				partial = st.Size()
			}
		}
		models = append(models, map[string]any{
			"id": m.ID, "name": m.Name, "group": tr(m.Group), "family": m.Family, "note": tr(m.Note),
			"file": m.File, "url": m.URL, "page": m.Page, "size": m.Size, "present": p,
			"custom": m.Custom, "partial": partial,
		})
	}
	var engSize int64
	if server != "" {
		if st, err := os.Stat(server); err == nil {
			engSize = st.Size()
		}
	}
	errText := a.engErr
	if a.pkgErr != nil && server == "" {
		errText = a.pkgErr.Error()
	}
	return map[string]any{
		"app": appID, "version": appVersion, "phase": phase,
		"error":      errText,
		"engine_log": a.engLog,
		"engine": map[string]any{
			"present": server != "", "version": engineVersion, "platform_label": tr(a.pkg.Label),
			"url": a.engineURL(), "page": "github.com/ggml-org/llama.cpp, " + tr("выпуск") + " " + engineVersion, "dir": a.engineDir, "size": engSize, "download_size": a.pkg.Size,
		},
		"unloaded":          a.unloaded,
		"no_model_at_start": a.noModelAtStart,
		"start_done":        a.startDone,
		"models":            models,
		"had_model":         anyModel,
		"active_model":      a.cfg.ActiveModel,
		"models_dir":        a.modelsDir,
		"download":          a.dl,
		"machine":           a.machine,
		"engine_info":       a.engInfo,
		"saved_dir":         a.savedDir(),
		"settings":          a.settingsJSON(),
		"data_dir":          a.dataDir,
		"tts":               a.ttsStateJSON(),
		"window":            a.windowStateJSON(),
	}
}

// ---------------------------------------------------------------- engine process

func (a *App) maybeStartEngine() {
	a.mu.Lock()
	server := a.serverPath()
	m := a.findModel(a.cfg.ActiveModel)
	ok := server != "" && a.modelPresent(m) && !a.dl.Active && !a.unloaded && (a.engStatus == "stopped" || a.engStatus == "error")
	a.mu.Unlock()
	if ok {
		go a.startEngine()
	}
}

func freePort() (int, error) {
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		return 0, err
	}
	defer ln.Close()
	return ln.Addr().(*net.TCPAddr).Port, nil
}

func randomKey() string {
	b := make([]byte, 16)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

func (a *App) startEngine() {
	a.mu.Lock()
	if a.engStatus == "starting" || a.engStatus == "ready" || a.unloaded {
		a.mu.Unlock()
		return
	}
	server := a.serverPath()
	m := a.findModel(a.cfg.ActiveModel)
	cfg := a.cfg
	a.engStatus, a.engErr, a.engLog = "starting", "", ""
	a.engInfo = EngineInfo{}
	a.mu.Unlock()

	fail := func(msg, logTail string) {
		logger.Printf("engine error: %s", msg)
		a.mu.Lock()
		a.engStatus, a.engErr, a.engLog = "error", msg, logTail
		a.mu.Unlock()
	}

	port, err := freePort()
	if err != nil {
		fail(tr("Не удалось выбрать порт для движка: ")+err.Error(), "")
		return
	}
	key := randomKey()
	args := []string{
		"-m", a.modelPath(m),
		"--host", "127.0.0.1", "--port", strconv.Itoa(port),
		"-c", strconv.Itoa(cfg.CtxSize),
		"-np", "1",
		"--no-ui",
		"--jinja",
		"-cram", "256",
		"-rea", "off",
		"--api-key", key,
	}
	if cfg.Threads > 0 {
		args = append(args, "-t", strconv.Itoa(cfg.Threads))
	}
	args = append(args, cfg.ExtraEngineArgs...)
	logPath := filepath.Join(a.logsDir, "engine.log")
	_ = os.Rename(logPath, filepath.Join(a.logsDir, "engine.prev.log"))
	lf, err := os.Create(logPath)
	if err != nil {
		fail(tr("Не удалось создать журнал движка: ")+err.Error(), "")
		return
	}
	cmd := exec.Command(server, args...)
	cmd.Dir = filepath.Dir(server)
	cmd.Stdout, cmd.Stderr = lf, lf
	cmd.Env = engineEnv(filepath.Dir(server))
	setChildAttrs(cmd)
	logger.Printf("starting engine: %s %s", server, strings.Join(redact(args, key), " "))
	t0 := time.Now()
	if err := cmd.Start(); err != nil {
		lf.Close()
		fail(tr("Не удалось запустить движок: ")+err.Error(), "")
		return
	}
	attachChild(cmd)
	done := make(chan struct{})
	a.mu.Lock()
	// "unload" pressed while the process was being started: stop it right away
	unloadedMeanwhile := a.unloaded
	a.engCmd, a.engDone, a.engPort, a.engKey, a.engStopping = cmd, done, port, key, unloadedMeanwhile
	a.mu.Unlock()
	if unloadedMeanwhile {
		terminate(cmd)
	}

	go func() {
		werr := cmd.Wait()
		lf.Close()
		close(done)
		a.mu.Lock()
		stopping := a.engStopping
		if a.engCmd == cmd {
			a.engCmd = nil
		}
		a.mu.Unlock()
		if stopping {
			a.mu.Lock()
			a.engStatus = "stopped"
			a.mu.Unlock()
			return
		}
		code := -1
		if cmd.ProcessState != nil {
			code = cmd.ProcessState.ExitCode()
		}
		fail(exitMessage(code, werr), tailFile(logPath, 40))
	}()

	client := http.Client{Timeout: 3 * time.Second}
	deadline := time.Now().Add(4 * time.Minute)
	for {
		select {
		case <-done:
			return
		default:
		}
		if time.Now().After(deadline) {
			a.stopEngine()
			fail(tr("Движок не ответил за 4 минуты."), tailFile(logPath, 40))
			return
		}
		resp, err := client.Get(fmt.Sprintf("http://127.0.0.1:%d/health", port))
		if err == nil {
			io.Copy(io.Discard, resp.Body)
			resp.Body.Close()
			if resp.StatusCode == 200 {
				break
			}
		}
		time.Sleep(300 * time.Millisecond)
	}
	info := EngineInfo{LoadMs: time.Since(t0).Milliseconds(), NCtx: cfg.CtxSize}
	req, _ := http.NewRequest("GET", fmt.Sprintf("http://127.0.0.1:%d/props", port), nil)
	req.Header.Set("Authorization", "Bearer "+key)
	if resp, err := client.Do(req); err == nil {
		var p struct {
			BuildInfo string `json:"build_info"`
			Gen       struct {
				NCtx int `json:"n_ctx"`
			} `json:"default_generation_settings"`
		}
		_ = json.NewDecoder(resp.Body).Decode(&p)
		resp.Body.Close()
		info.Build = p.BuildInfo
		if p.Gen.NCtx > 0 {
			info.NCtx = p.Gen.NCtx
		}
	}
	info.Threads = parseThreads(logPath)
	if info.Build == "" {
		info.Build = engineVersion
	}
	a.mu.Lock()
	if a.engCmd == cmd {
		a.engStatus, a.engInfo = "ready", info
	}
	a.mu.Unlock()
	logger.Printf("engine ready in %d ms, build %s, threads %d", info.LoadMs, info.Build, info.Threads)
}

func redact(args []string, key string) []string {
	out := make([]string, len(args))
	for i, s := range args {
		if s == key {
			s = "***"
		}
		out[i] = s
	}
	return out
}

var reThreads = regexp.MustCompile(`n_threads = (\d+)`)

func parseThreads(logPath string) int {
	b, err := os.ReadFile(logPath)
	if err != nil {
		return 0
	}
	m := reThreads.FindSubmatch(b)
	if m == nil {
		return 0
	}
	n, _ := strconv.Atoi(string(m[1]))
	return n
}

func tailFile(p string, n int) string {
	b, err := os.ReadFile(p)
	if err != nil {
		return ""
	}
	lines := strings.Split(strings.TrimRight(string(b), "\n"), "\n")
	if len(lines) > n {
		lines = lines[len(lines)-n:]
	}
	return strings.Join(lines, "\n")
}

func (a *App) stopEngine() {
	a.mu.Lock()
	cmd, done := a.engCmd, a.engDone
	if cmd == nil {
		if a.engStatus != "error" {
			a.engStatus = "stopped"
		}
		a.mu.Unlock()
		return
	}
	a.engStopping = true
	a.mu.Unlock()
	terminate(cmd)
	select {
	case <-done:
	case <-time.After(5 * time.Second):
		_ = cmd.Process.Kill()
		<-done
	}
	a.mu.Lock()
	a.engStatus = "stopped"
	a.mu.Unlock()
}

// ---------------------------------------------------------------- downloads

func (a *App) startDownloads() error {
	a.mu.Lock()
	if a.dl.Active {
		a.mu.Unlock()
		return nil
	}
	if a.pkgErr != nil && a.serverPath() == "" {
		a.mu.Unlock()
		return a.pkgErr
	}
	needEngine := a.serverPath() == ""
	m := a.findModel(a.cfg.ActiveModel)
	needModel := !a.modelPresent(m)
	ctx, cancel := context.WithCancel(context.Background())
	a.dlCancel = cancel
	a.dl = DownloadState{Active: true}
	a.mu.Unlock()

	go func() {
		defer cancel()
		var err error
		if needEngine {
			err = a.downloadEngine(ctx)
		}
		if err == nil && needModel {
			err = a.downloadModel(ctx, m)
		}
		a.mu.Lock()
		a.dl.Active = false
		a.dl.Phase = ""
		if err != nil {
			if errors.Is(err, context.Canceled) {
				a.dl.Error = tr("скачивание отменено")
			} else {
				a.dl.Error = err.Error()
			}
			logger.Printf("download failed: %v", err)
		} else {
			a.dl.Error = ""
		}
		a.mu.Unlock()
		if err == nil {
			a.maybeStartEngine()
		}
	}()
	return nil
}

func (a *App) setDL(f func(d *DownloadState)) {
	a.mu.Lock()
	f(&a.dl)
	a.mu.Unlock()
}

func (a *App) downloadEngine(ctx context.Context) error {
	pkg := a.pkg
	a.setDL(func(d *DownloadState) {
		*d = DownloadState{Active: true, Item: "engine", Name: pkg.Asset, Phase: "download", Total: pkg.Size}
	})
	archive := filepath.Join(a.engineDir, pkg.Asset)
	size, sum := pkg.Size, pkg.SHA256
	if engineURLOverride != "" {
		size, sum = 0, ""
	}
	if err := a.fetch(ctx, a.engineURL(), archive, size, sum); err != nil {
		return fmt.Errorf(tr("движок: %w"), err)
	}
	a.setDL(func(d *DownloadState) { d.Phase = "extract" })
	dest := filepath.Join(a.engineDir, engineVersion)
	_ = os.RemoveAll(dest)
	var err error
	if strings.HasSuffix(pkg.Asset, ".zip") {
		err = unzip(archive, dest)
	} else {
		err = untargz(archive, dest)
	}
	if err != nil {
		return fmt.Errorf(tr("распаковка движка: %w"), err)
	}
	server := ""
	_ = filepath.WalkDir(dest, func(p string, d fs.DirEntry, err error) error {
		if err == nil && !d.IsDir() && d.Name() == pkg.Server && server == "" {
			server = p
		}
		return nil
	})
	if server == "" {
		return fmt.Errorf(tr("в архиве движка нет файла %s"), pkg.Server)
	}
	if runtime.GOOS != "windows" {
		_ = os.Chmod(server, 0o755)
	}
	rel, _ := filepath.Rel(a.engineDir, server)
	meta, _ := json.MarshalIndent(engineMeta{Version: engineVersion, Server: filepath.ToSlash(rel)}, "", "  ")
	if err := os.WriteFile(filepath.Join(a.engineDir, "engine.json"), meta, 0o644); err != nil {
		return err
	}
	_ = os.Remove(archive)
	logger.Printf("engine installed: %s", server)
	return nil
}

func (a *App) downloadModel(ctx context.Context, m *ModelSpec) error {
	a.setDL(func(d *DownloadState) {
		*d = DownloadState{Active: true, Item: "model", Name: m.File, Phase: "download", Total: m.Size}
	})
	if err := a.fetch(ctx, m.URL, a.modelPath(m), m.Size, m.SHA256); err != nil {
		return fmt.Errorf(tr("модель: %w"), err)
	}
	logger.Printf("model installed: %s", m.File)
	return nil
}

// fetch downloads url to dest via dest+".part", resuming if possible, and checks size and SHA-256.
func (a *App) fetch(ctx context.Context, rawURL, dest string, wantSize int64, wantSHA string) error {
	return a.fetchTo(ctx, rawURL, dest, wantSize, wantSHA, a.setDL)
}

// fetchTo is fetch that reports progress through setDL (the model download or the voice download).
func (a *App) fetchTo(ctx context.Context, rawURL, dest string, wantSize int64, wantSHA string, setDL func(func(d *DownloadState))) error {
	part := dest + ".part"
	var offset int64
	if st, err := os.Stat(part); err == nil {
		offset = st.Size()
		if wantSize > 0 && offset > wantSize {
			_ = os.Remove(part)
			offset = 0
		}
	}
	h := sha256.New()
	if offset > 0 && wantSHA != "" {
		setDL(func(d *DownloadState) { d.Phase = "verify"; d.Done = offset })
		f, err := os.Open(part)
		if err != nil {
			return err
		}
		n, err := io.Copy(h, f)
		f.Close()
		if err != nil || n != offset {
			_ = os.Remove(part)
			offset = 0
			h.Reset()
		}
	}

	rctx, cancel := context.WithCancel(ctx)
	defer cancel()
	req, err := http.NewRequestWithContext(rctx, "GET", rawURL, nil)
	if err != nil {
		return err
	}
	req.Header.Set("User-Agent", "Ttranslator/"+appVersion)
	if offset > 0 {
		req.Header.Set("Range", fmt.Sprintf("bytes=%d-", offset))
	}
	client := &http.Client{Transport: &http.Transport{
		Proxy:                 http.ProxyFromEnvironment,
		DialContext:           (&net.Dialer{Timeout: 30 * time.Second}).DialContext,
		TLSHandshakeTimeout:   30 * time.Second,
		ResponseHeaderTimeout: 60 * time.Second,
	}}
	resp, err := client.Do(req)
	if err != nil {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		return fmt.Errorf(tr("нет соединения с %s (%v)"), hostOf(rawURL), err)
	}
	defer resp.Body.Close()
	flags := os.O_CREATE | os.O_WRONLY
	switch {
	case resp.StatusCode == http.StatusPartialContent && offset > 0:
		flags |= os.O_APPEND
	case resp.StatusCode == http.StatusOK:
		flags |= os.O_TRUNC
		offset = 0
		h.Reset()
	case resp.StatusCode == http.StatusRequestedRangeNotSatisfiable:
		_ = os.Remove(part)
		return errors.New(tr("сервер не принял докачку, нажмите «Повторить»"))
	default:
		return fmt.Errorf(tr("сервер %s ответил %s"), hostOf(rawURL), resp.Status)
	}
	total := wantSize
	if total <= 0 && resp.ContentLength > 0 {
		total = offset + resp.ContentLength
	}
	f, err := os.OpenFile(part, flags, 0o644)
	if err != nil {
		return err
	}
	setDL(func(d *DownloadState) { d.Phase = "download"; d.Done = offset; d.Total = total })

	// stall watchdog: cancel if no bytes arrive for 60 s
	progress := make(chan struct{}, 1)
	go func() {
		t := time.NewTimer(60 * time.Second)
		defer t.Stop()
		for {
			select {
			case <-rctx.Done():
				return
			case <-progress:
				if !t.Stop() {
					<-t.C
				}
				t.Reset(60 * time.Second)
			case <-t.C:
				cancel()
				return
			}
		}
	}()

	buf := make([]byte, 256*1024)
	done := offset
	lastT, lastB := time.Now(), done
	speed := 0.0
	var werr error
	for {
		n, rerr := resp.Body.Read(buf)
		if n > 0 {
			if _, err := f.Write(buf[:n]); err != nil {
				werr = err
				break
			}
			h.Write(buf[:n])
			done += int64(n)
			select {
			case progress <- struct{}{}:
			default:
			}
			if dt := time.Since(lastT); dt > 700*time.Millisecond {
				inst := float64(done-lastB) / dt.Seconds()
				if speed == 0 {
					speed = inst
				} else {
					speed = 0.7*speed + 0.3*inst
				}
				lastT, lastB = time.Now(), done
				d0, s0 := done, speed
				setDL(func(d *DownloadState) { d.Done = d0; d.Speed = s0 })
			}
		}
		if rerr == io.EOF {
			break
		}
		if rerr != nil {
			werr = rerr
			break
		}
	}
	cerr := f.Close()
	if werr != nil {
		if ctx.Err() != nil {
			return ctx.Err()
		}
		if rctx.Err() != nil {
			return errors.New(tr("скачивание остановилось: больше минуты не приходили данные; нажмите «Повторить», докачка продолжится"))
		}
		return fmt.Errorf(tr("ошибка при скачивании (%v); нажмите «Повторить», докачка продолжится"), werr)
	}
	if cerr != nil {
		return cerr
	}
	setDL(func(d *DownloadState) { d.Done = done })
	if wantSize > 0 && done != wantSize {
		if done > wantSize {
			_ = os.Remove(part)
		}
		return fmt.Errorf(tr("размер файла не совпал (%d вместо %d байт); нажмите «Повторить»"), done, wantSize)
	}
	if wantSHA != "" {
		setDL(func(d *DownloadState) { d.Phase = "verify" })
		if got := hex.EncodeToString(h.Sum(nil)); !strings.EqualFold(got, wantSHA) {
			_ = os.Remove(part)
			return errors.New(tr("контрольная сумма не совпала — файл повреждён и удалён; нажмите «Повторить»"))
		}
	}
	_ = os.Remove(dest)
	return os.Rename(part, dest)
}

func hostOf(raw string) string {
	if u, err := url.Parse(raw); err == nil {
		return u.Host
	}
	return raw
}

func safeJoin(dest, name string) (string, error) {
	p := filepath.Join(dest, filepath.FromSlash(name))
	rel, err := filepath.Rel(dest, p)
	if err != nil || rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) || filepath.IsAbs(rel) {
		return "", fmt.Errorf(tr("недопустимый путь в архиве: %s"), name)
	}
	return p, nil
}

func unzip(archive, dest string) error {
	r, err := zip.OpenReader(archive)
	if err != nil {
		return err
	}
	defer r.Close()
	for _, f := range r.File {
		p, err := safeJoin(dest, f.Name)
		if err != nil {
			return err
		}
		if f.FileInfo().IsDir() {
			if err := os.MkdirAll(p, 0o755); err != nil {
				return err
			}
			continue
		}
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			return err
		}
		rc, err := f.Open()
		if err != nil {
			return err
		}
		mode := os.FileMode(0o644)
		if f.Mode()&0o111 != 0 {
			mode = 0o755
		}
		w, err := os.OpenFile(p, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, mode)
		if err != nil {
			rc.Close()
			return err
		}
		_, err = io.Copy(w, rc)
		rc.Close()
		if cerr := w.Close(); err == nil {
			err = cerr
		}
		if err != nil {
			return err
		}
	}
	return nil
}

func untargz(archive, dest string) error {
	f, err := os.Open(archive)
	if err != nil {
		return err
	}
	defer f.Close()
	gz, err := gzip.NewReader(f)
	if err != nil {
		return err
	}
	defer gz.Close()
	return untar(gz, dest)
}

// untar unpacks a tar stream into dest: files, folders and symbolic links that stay inside dest.
func untar(r io.Reader, dest string) error {
	tr := tar.NewReader(r)
	for {
		hdr, err := tr.Next()
		if err == io.EOF {
			return nil
		}
		if err != nil {
			return err
		}
		p, err := safeJoin(dest, hdr.Name)
		if err != nil {
			return err
		}
		switch hdr.Typeflag {
		case tar.TypeDir:
			if err := os.MkdirAll(p, 0o755); err != nil {
				return err
			}
		case tar.TypeReg:
			if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
				return err
			}
			mode := os.FileMode(0o644)
			if hdr.Mode&0o111 != 0 {
				mode = 0o755
			}
			w, err := os.OpenFile(p, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, mode)
			if err != nil {
				return err
			}
			_, err = io.Copy(w, tr)
			if cerr := w.Close(); err == nil {
				err = cerr
			}
			if err != nil {
				return err
			}
		case tar.TypeSymlink:
			target := filepath.Join(filepath.Dir(p), hdr.Linkname)
			if _, err := safeJoin(dest, mustRel(dest, target)); err != nil || filepath.IsAbs(hdr.Linkname) {
				continue
			}
			if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
				return err
			}
			_ = os.Remove(p)
			if err := os.Symlink(hdr.Linkname, p); err != nil {
				return err
			}
		}
	}
}

func mustRel(base, p string) string {
	r, err := filepath.Rel(base, p)
	if err != nil {
		return ".."
	}
	return filepath.ToSlash(r)
}

// ---------------------------------------------------------------- HTTP

func writeJSON(w http.ResponseWriter, code int, v any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(v)
}

func jsonError(w http.ResponseWriter, code int, msg string) {
	writeJSON(w, code, map[string]any{"error": msg})
}

// guard rejects requests from other sites (DNS rebinding / cross-site POST).
func (a *App) guard(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		host := r.Host
		if h, _, err := net.SplitHostPort(host); err == nil {
			host = h
		}
		if host != "127.0.0.1" && host != "localhost" {
			http.Error(w, "forbidden", http.StatusForbidden)
			return
		}
		if r.Method != http.MethodGet && r.Method != http.MethodHead {
			if o := r.Header.Get("Origin"); o != "" {
				u, err := url.Parse(o)
				if err != nil || (u.Hostname() != "127.0.0.1" && u.Hostname() != "localhost") || u.Port() != portOf(r.Host) {
					http.Error(w, "forbidden", http.StatusForbidden)
					return
				}
			}
		}
		next.ServeHTTP(w, r)
	})
}

func portOf(hostport string) string {
	if _, p, err := net.SplitHostPort(hostport); err == nil {
		return p
	}
	return ""
}

func (a *App) routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("/api/ping", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, 200, map[string]any{"app": appID, "version": appVersion})
	})
	mux.HandleFunc("/api/state", func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, 200, a.stateJSON())
	})
	mux.HandleFunc("/api/events", a.handleEvents)
	mux.HandleFunc("/api/closing", a.post(a.handleClosing))
	mux.HandleFunc("/api/setup", a.post(func(w http.ResponseWriter, r *http.Request) {
		a.mu.Lock()
		a.dl.Error = ""
		a.unloaded, a.noModelAtStart, a.startDone = false, false, true
		a.mu.Unlock()
		if err := a.startDownloads(); err != nil {
			jsonError(w, 400, err.Error())
			return
		}
		writeJSON(w, 200, map[string]any{"ok": true})
	}))
	mux.HandleFunc("/api/cancel", a.post(func(w http.ResponseWriter, r *http.Request) {
		a.mu.Lock()
		if a.dlCancel != nil {
			a.dlCancel()
		}
		a.mu.Unlock()
		writeJSON(w, 200, map[string]any{"ok": true})
	}))
	mux.HandleFunc("/api/restart", a.post(func(w http.ResponseWriter, r *http.Request) {
		a.stopEngine()
		a.mu.Lock()
		a.engStatus, a.engErr, a.engLog = "stopped", "", ""
		a.unloaded, a.noModelAtStart, a.startDone = false, false, true
		a.mu.Unlock()
		a.maybeStartEngine()
		writeJSON(w, 200, map[string]any{"ok": true})
	}))
	// Unload the model from memory (the engine process exits, the file stays) and load it again.
	// {"at_start": true} — from the welcome window at start: the page then says the model is not loaded at start.
	mux.HandleFunc("/api/unload", a.post(func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			AtStart bool `json:"at_start"`
		}
		_ = json.NewDecoder(io.LimitReader(r.Body, 1024)).Decode(&req)
		a.mu.Lock()
		a.unloaded, a.noModelAtStart, a.startDone = true, req.AtStart, true
		a.mu.Unlock()
		a.stopEngine()
		a.mu.Lock()
		a.engStatus, a.engErr, a.engLog = "stopped", "", ""
		a.engInfo = EngineInfo{}
		a.mu.Unlock()
		logger.Printf("model unloaded from memory")
		writeJSON(w, 200, map[string]any{"ok": true})
	}))
	mux.HandleFunc("/api/load", a.post(func(w http.ResponseWriter, r *http.Request) {
		a.mu.Lock()
		a.unloaded, a.noModelAtStart, a.startDone = false, false, true
		if a.engStatus == "error" {
			a.engStatus, a.engErr, a.engLog = "stopped", "", ""
		}
		a.mu.Unlock()
		logger.Printf("model load requested")
		a.maybeStartEngine()
		writeJSON(w, 200, map[string]any{"ok": true})
	}))
	// The welcome window has been closed: its choice (load the model at start or not) is not applied again by
	// another window of this run.
	mux.HandleFunc("/api/start-done", a.post(func(w http.ResponseWriter, r *http.Request) {
		a.mu.Lock()
		a.startDone = true
		a.mu.Unlock()
		writeJSON(w, 200, map[string]any{"ok": true})
	}))
	mux.HandleFunc("/api/model", a.post(func(w http.ResponseWriter, r *http.Request) {
		var req struct{ ID string }
		_ = json.NewDecoder(io.LimitReader(r.Body, 4096)).Decode(&req)
		m := a.findModel(req.ID)
		if m == nil || (m.Custom && !a.modelPresent(m)) {
			jsonError(w, 400, tr("неизвестная модель"))
			return
		}
		a.mu.Lock()
		busy := a.dl.Active
		a.mu.Unlock()
		if busy {
			jsonError(w, 409, tr("идёт скачивание, дождитесь окончания"))
			return
		}
		a.stopEngine()
		a.mu.Lock()
		a.cfg.ActiveModel = m.ID
		cfg := a.cfg
		a.engStatus, a.engErr, a.engLog = "stopped", "", ""
		a.unloaded, a.noModelAtStart, a.startDone = false, false, true // choosing a model means: load it
		present := a.modelPresent(m)
		a.mu.Unlock()
		a.saveConfig(cfg)
		if present {
			a.maybeStartEngine()
		} else if err := a.startDownloads(); err != nil {
			jsonError(w, 400, err.Error())
			return
		}
		writeJSON(w, 200, map[string]any{"ok": true})
	}))
	mux.HandleFunc("/api/model/", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodDelete {
			jsonError(w, 405, "method not allowed")
			return
		}
		id := strings.TrimPrefix(r.URL.Path, "/api/model/")
		m := a.findModel(id)
		if m == nil {
			jsonError(w, 404, tr("неизвестная модель"))
			return
		}
		a.mu.Lock()
		active, busy := a.cfg.ActiveModel, a.dl.Active
		a.mu.Unlock()
		if id == active {
			jsonError(w, 409, tr("эта модель сейчас работает; сначала выберите другую"))
			return
		}
		if busy {
			jsonError(w, 409, tr("идёт скачивание, дождитесь окончания"))
			return
		}
		p := a.modelPath(m)
		if err := os.Remove(p); err != nil && !errors.Is(err, os.ErrNotExist) {
			jsonError(w, 500, tr("не удалось удалить файл: ")+err.Error())
			return
		}
		_ = os.Remove(p + ".part")
		logger.Printf("model file deleted: %s", m.File)
		writeJSON(w, 200, map[string]any{"ok": true})
	})
	mux.HandleFunc("/api/report", a.post(func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Markdown string          `json:"markdown"`
			JSON     json.RawMessage `json:"json"`
		}
		if err := json.NewDecoder(io.LimitReader(r.Body, 8*1024*1024)).Decode(&req); err != nil {
			jsonError(w, 400, tr("неверный запрос"))
			return
		}
		name := "test-" + time.Now().Format("2006-01-02_15-04-05")
		md := filepath.Join(a.reportsDir, name+".md")
		if err := os.WriteFile(md, []byte(req.Markdown), 0o644); err != nil {
			jsonError(w, 500, err.Error())
			return
		}
		if len(req.JSON) > 0 {
			_ = os.WriteFile(filepath.Join(a.reportsDir, name+".json"), req.JSON, 0o644)
		}
		writeJSON(w, 200, map[string]any{"path": md})
	}))
	mux.HandleFunc("/api/open", a.post(func(w http.ResponseWriter, r *http.Request) {
		var req struct{ What string }
		_ = json.NewDecoder(io.LimitReader(r.Body, 4096)).Decode(&req)
		p := a.dataDir
		switch req.What {
		case "logs":
			p = a.logsDir
		case "glossary":
			p = a.glossaryDir()
			_ = os.MkdirAll(p, 0o755)
		case "saved":
			p = a.savedDir()
			_ = os.MkdirAll(p, 0o755)
		}
		if err := openFolder(p); err != nil {
			jsonError(w, 500, err.Error())
			return
		}
		writeJSON(w, 200, map[string]any{"ok": true})
	}))
	// GET returns the interface settings; POST changes some of them ({ui_language, theme, font_scale}) in config.json.
	mux.HandleFunc("/api/settings", func(w http.ResponseWriter, r *http.Request) {
		switch r.Method {
		case http.MethodGet:
			a.mu.Lock()
			st := a.settingsJSON()
			a.mu.Unlock()
			writeJSON(w, 200, st)
		case http.MethodPost:
			var req struct {
				UILanguage       *string `json:"ui_language"`
				Theme            *string `json:"theme"`
				FontScale        *int    `json:"font_scale"`
				ShowWelcome      *bool   `json:"show_welcome"`
				LaunchMode       *string `json:"launch_mode"`
				LoadModelAtStart *bool   `json:"load_model_at_start"`
				StartMaximized   *bool   `json:"start_maximized"`
			}
			if err := json.NewDecoder(io.LimitReader(r.Body, 4096)).Decode(&req); err != nil {
				jsonError(w, 400, tr("неверный запрос"))
				return
			}
			if (req.UILanguage != nil && !uiLanguages[*req.UILanguage]) || (req.Theme != nil && !uiThemes[*req.Theme]) ||
				(req.FontScale != nil && !fontScales[*req.FontScale]) || (req.LaunchMode != nil && !launchModes[*req.LaunchMode]) {
				jsonError(w, 400, tr("неверное значение настройки"))
				return
			}
			a.mu.Lock()
			if req.UILanguage != nil {
				a.cfg.UILanguage = *req.UILanguage
			}
			if req.Theme != nil {
				a.cfg.Theme = *req.Theme
			}
			if req.FontScale != nil {
				a.cfg.FontScale = *req.FontScale
			}
			if req.ShowWelcome != nil {
				a.cfg.ShowWelcome = *req.ShowWelcome
			}
			if req.LaunchMode != nil {
				a.cfg.LaunchMode = *req.LaunchMode
			}
			if req.LoadModelAtStart != nil {
				a.cfg.LoadModelAtStart = *req.LoadModelAtStart
			}
			if req.StartMaximized != nil {
				a.cfg.StartMaximized = *req.StartMaximized
			}
			a.saveConfig(a.cfg)
			lang := a.cfg.UILanguage
			st := a.settingsJSON()
			a.mu.Unlock()
			setUILang(lang)
			logger.Printf("settings: %v", st)
			writeJSON(w, 200, st)
		default:
			jsonError(w, 405, "method not allowed")
		}
	})
	mux.HandleFunc("/api/quit", a.post(func(w http.ResponseWriter, r *http.Request) {
		writeJSON(w, 200, map[string]any{"ok": true})
		go func() { time.Sleep(200 * time.Millisecond); a.shutdown() }()
	}))
	a.glossaryRoutes(mux)
	a.savedRoutes(mux)
	a.ttsRoutes(mux)
	mux.HandleFunc("/api/", func(w http.ResponseWriter, r *http.Request) { jsonError(w, 404, "not found") })

	proxy := http.HandlerFunc(a.handleProxy)
	mux.Handle("/v1/", proxy)
	mux.Handle("/health", proxy)
	mux.Handle("/props", proxy)
	mux.HandleFunc("/", a.handleStatic)
	return a.guard(mux)
}

func (a *App) post(h http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodPost {
			jsonError(w, 405, "method not allowed")
			return
		}
		h(w, r)
	}
}

// engineTransport opens a fresh local connection per request: the engine closes the
// connection after every streamed reply, so a reused keep-alive connection fails a POST.
var engineTransport = &http.Transport{
	DisableKeepAlives: true,
	DialContext:       (&net.Dialer{Timeout: 5 * time.Second}).DialContext,
}

func (a *App) handleProxy(w http.ResponseWriter, r *http.Request) {
	a.mu.Lock()
	port, key, ready, starting := a.engPort, a.engKey, a.engStatus == "ready", a.engStatus == "starting" && !a.unloaded
	a.mu.Unlock()
	if !ready {
		// The text "Please load a model." is fixed by the author (always English); the UI (NEED_MODEL_MSG) shows it as is.
		msg := "Please load a model."
		if starting {
			msg = tr("Модель ещё загружается, подождите.")
		}
		writeJSON(w, 503, map[string]any{"error": map[string]any{"code": 503, "message": msg, "type": "unavailable_error"}})
		return
	}
	// read the (small) request body first, so the engine request does not depend on the browser connection
	if r.Body != nil {
		body, err := io.ReadAll(io.LimitReader(r.Body, 4<<20))
		r.Body.Close()
		if err != nil {
			jsonError(w, 400, tr("не удалось прочитать запрос"))
			return
		}
		r.Body = io.NopCloser(bytes.NewReader(body))
		r.ContentLength = int64(len(body))
		r.Header.Set("Content-Length", strconv.Itoa(len(body)))
	}
	target := &url.URL{Scheme: "http", Host: fmt.Sprintf("127.0.0.1:%d", port)}
	rp := httputil.NewSingleHostReverseProxy(target)
	rp.Transport = engineTransport
	rp.ErrorLog = logger
	rp.FlushInterval = -1
	orig := rp.Director
	rp.Director = func(req *http.Request) {
		orig(req)
		req.Host = target.Host
		req.Header.Set("Authorization", "Bearer "+key)
		req.Header.Del("Origin")
		req.Header.Del("Cookie")
	}
	rp.ErrorHandler = func(w http.ResponseWriter, req *http.Request, err error) {
		if req.Context().Err() != nil {
			return
		}
		writeJSON(w, 502, map[string]any{"error": map[string]any{"code": 502, "message": tr("Движок не отвечает: ") + err.Error()}})
	}
	rp.ServeHTTP(w, r)
}

func (a *App) handleStatic(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodGet && r.Method != http.MethodHead {
		http.Error(w, "method not allowed", http.StatusMethodNotAllowed)
		return
	}
	name := strings.TrimPrefix(r.URL.Path, "/")
	if name == "" {
		name = "index.html"
	}
	if strings.Contains(name, "..") || strings.ContainsAny(name, "\\:") {
		http.NotFound(w, r)
		return
	}
	w.Header().Set("Cache-Control", "no-store")
	w.Header().Set("X-Content-Type-Options", "nosniff")
	if strings.HasSuffix(name, ".txt") {
		w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	}
	p := filepath.Join(a.uiDir, filepath.FromSlash(name))
	if name == "index.html" {
		// the page gets the interface language, theme and font size right in <html>: no flash of the default look
		b, err := os.ReadFile(p)
		if err != nil {
			if b, err = fallbackUI.ReadFile("ui_fallback/index.html"); err != nil {
				http.NotFound(w, r)
				return
			}
		}
		a.mu.Lock()
		b = injectSettings(b, a.cfg.UILanguage, a.cfg.Theme, a.cfg.FontScale)
		a.mu.Unlock()
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
		_, _ = w.Write(b)
		return
	}
	if st, err := os.Stat(p); err == nil && !st.IsDir() {
		http.ServeFile(w, r, p)
		return
	}
	b, err := fallbackUI.ReadFile("ui_fallback/" + name)
	if err != nil {
		http.NotFound(w, r)
		return
	}
	if strings.HasSuffix(name, ".html") {
		w.Header().Set("Content-Type", "text/html; charset=utf-8")
	}
	_, _ = w.Write(b)
}

// injectSettings replaces the page's <html …> tag with one that carries the interface settings.
func injectSettings(b []byte, lang, theme string, font int) []byte {
	i := bytes.Index(b, []byte("<html"))
	if i < 0 {
		return b
	}
	j := bytes.IndexByte(b[i:], '>')
	if j < 0 {
		return b
	}
	tag := fmt.Sprintf(`<html lang="%s" data-theme="%s" data-font="%d">`, lang, theme, font)
	out := make([]byte, 0, len(b)+len(tag))
	out = append(out, b[:i]...)
	out = append(out, tag...)
	return append(out, b[i+j+1:]...)
}

func (a *App) handleEvents(w http.ResponseWriter, r *http.Request) {
	fl, ok := w.(http.Flusher)
	if !ok {
		http.Error(w, "streaming unsupported", 500)
		return
	}
	w.Header().Set("Content-Type", "text/event-stream")
	w.Header().Set("Cache-Control", "no-store")
	id := clip(r.URL.Query().Get("page"), 64)
	own := r.URL.Query().Get("ttw") == "1" // a page inside the own window (window.go)
	a.mu.Lock()
	if a.pages == nil {
		a.pages = map[string]int{}
	}
	a.pages[id]++
	a.everConnected = true
	if own {
		if a.ownPages++; a.ownPages == 1 {
			logger.Printf("page connected in the own window")
		}
	}
	a.mu.Unlock()
	defer func() {
		a.mu.Lock()
		if a.pages[id]--; a.pages[id] <= 0 {
			delete(a.pages, id)
		}
		if own {
			a.ownPages--
		}
		_, said := a.bye[id]
		a.lastGone, a.lastGoneBye = time.Now(), said
		a.mu.Unlock()
	}()
	fmt.Fprint(w, "retry: 2000\n\n")
	fl.Flush()
	t := time.NewTicker(15 * time.Second)
	defer t.Stop()
	for {
		select {
		case <-r.Context().Done():
			return
		case <-a.quit:
			return
		case <-t.C:
			fmt.Fprint(w, ": ping\n\n")
			fl.Flush()
		}
	}
}

// handleClosing: the page is being closed or reloaded (pagehide, sent with navigator.sendBeacon). A reloaded
// page opens a new event stream within a second; a closed one does not, and the program exits after byeGrace.
func (a *App) handleClosing(w http.ResponseWriter, r *http.Request) {
	if id := clip(r.URL.Query().Get("page"), 64); id != "" {
		a.mu.Lock()
		if a.bye == nil {
			a.bye = map[string]time.Time{}
		}
		a.bye[id] = time.Now()
		a.lastGone, a.lastGoneBye = time.Now(), true
		a.mu.Unlock()
	}
	w.WriteHeader(http.StatusNoContent)
}

// openWindows counts pages with an open event stream that have not said they are closing (under a.mu).
func (a *App) openWindows() int {
	n := 0
	for id, c := range a.pages {
		if _, said := a.bye[id]; c > 0 && !said {
			n++
		}
	}
	return n
}

// How long the program waits before exiting once no window is open: shortly after a window said it was closing
// (a reload reconnects well within that time), longer when a connection just dropped.
const (
	byeGrace  = 5 * time.Second
	goneGrace = 20 * time.Second
)

// watchdog exits (stopping the engine, which frees the model's memory) when the app window has been closed.
func (a *App) watchdog() {
	t := time.NewTicker(time.Second)
	defer t.Stop()
	for range t.C {
		a.mu.Lock()
		open, ever, gone, bye, dl := a.openWindows(), a.everConnected, a.lastGone, a.lastGoneBye, a.dl.Active || a.vdl.Active
		// the own window was closed: its page could not say goodbye
		bye = bye || (!a.windowGone.IsZero() && time.Since(a.windowGone) < time.Minute)
		for id, at := range a.bye { // forget old goodbyes of pages whose streams are gone
			if a.pages[id] == 0 && time.Since(at) > time.Minute {
				delete(a.bye, id)
			}
		}
		a.mu.Unlock()
		if open > 0 || dl {
			continue
		}
		grace := goneGrace
		if bye {
			grace = byeGrace
		}
		if ever && time.Since(gone) > grace {
			logger.Printf("window closed, exiting")
			a.shutdown()
			return
		}
		if !ever && time.Since(a.started) > 10*time.Minute {
			logger.Printf("no window connected for 10 minutes, exiting")
			a.shutdown()
			return
		}
	}
}
