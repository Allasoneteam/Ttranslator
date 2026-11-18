package main

// Reading pictures: scans, photos of pages, screenshots, the pages of scanned PDFs (the author's choice of
// 18.11.2026: pictures and scans first). Gemma 4 reads them itself; llama.cpp needs a second file for that — the
// "mmproj" (the picture and sound encoders of the model). It is offered for download with the model's size (E2B or
// E4B) and loaded only when a picture is to be read in this run (/api/vision): it takes about 0.6 GB of memory more,
// and a page then fits into one batch of the engine (visionArgs).

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

type VisionSpec struct {
	ID     string   `json:"id"`
	Name   string   `json:"name"`
	For    []string `json:"for"` // the catalogue models (ModelSpec.ID) it reads pictures for
	File   string   `json:"file"`
	URL    string   `json:"url"`
	Page   string   `json:"page"`
	Size   int64    `json:"size"`
	SHA256 string   `json:"sha256"`
	Engine bool     `json:"engine,omitempty"` // tests only: give this file to the engine (a broken file — visionFallback)
}

// The Q8_0 files of ggml-org (the llama.cpp authors), from the same commits as the Q8_0 models: half the size of the
// BF16 files of Google and ggml-org, the same encoders; one file serves both models of its size (Q4_0 and Q8_0).
// Sizes and SHA-256 — the Hugging Face API of these commits (read on the author's computer, 18.11.2026).
var visionSpecs = []VisionSpec{
	{ID: "mm-e2b", Name: "Gemma 4 E2B", For: []string{"g4-e2b", "g4-e2b-q8"}, File: "mmproj-gemma-4-E2B-it-Q8_0.gguf",
		URL: hfG4E2BQ8 + "mmproj-gemma-4-E2B-it-Q8_0.gguf", Page: "huggingface.co/ggml-org/gemma-4-E2B-it-GGUF", Size: 557368064,
		SHA256: "9406f99c16d68cda4f1f0552192dcc99021ea1fc6d2fd50b1dc3ccf30d04b292"},
	{ID: "mm-e4b", Name: "Gemma 4 E4B", For: []string{"g4-e4b", "g4-e4b-q8"}, File: "mmproj-gemma-4-E4B-it-Q8_0.gguf",
		URL: hfG4E4BQ8 + "mmproj-gemma-4-E4B-it-Q8_0.gguf", Page: "huggingface.co/ggml-org/gemma-4-E4B-it-GGUF", Size: 559874816,
		SHA256: "197f49a93027f9843772bd24a6a9e0be2a32a788de5a3def330e9c585d86edd1"},
}

// The engine reads a picture as 1120 tokens — the largest budget of Gemma 4, the one meant for text, documents and
// handwriting (a smaller one blurs small print). Gemma 4 attends to all the tokens of a picture at once, so they
// must fit into one micro-batch: the default is 512, a page needs 1120 (else llama.cpp stops with "non-causal
// attention requires n_ubatch >= n_tokens").
const visionTokens = 1120

func visionArgs(mmproj string) []string {
	n := strconv.Itoa(visionTokens)
	return []string{"--mmproj", mmproj, "--image-min-tokens", n, "--image-max-tokens", n, "-ub", "1280", "-b", "2048"}
}

// visionFor: the picture file for a catalogue model, nil for other models (own .gguf files).
func visionFor(modelID string) *VisionSpec {
	for i := range visionSpecs {
		for _, id := range visionSpecs[i].For {
			if id == modelID {
				return &visionSpecs[i]
			}
		}
	}
	return nil
}

func findVision(id string) *VisionSpec {
	for i := range visionSpecs {
		if visionSpecs[i].ID == id {
			return &visionSpecs[i]
		}
	}
	return nil
}

func (a *App) visionPath(v *VisionSpec) string { return filepath.Join(a.modelsDir, v.File) }

func (a *App) visionPresent(v *VisionSpec) bool {
	if v == nil {
		return false
	}
	st, err := os.Stat(a.visionPath(v))
	return err == nil && st.Size() == v.Size
}

// visionFake (tests): the engine is started without the file — the tiny test model has no picture encoder — but
// the page is told that pictures can be read; the test answers the requests itself.
var visionFake bool

// visionTestOverrides: TDOC_TEST_VISION points to a JSON list of VisionSpec (the mirror of the tests).
func visionTestOverrides() {
	p := os.Getenv("TDOC_TEST_VISION")
	if p == "" {
		return
	}
	b, err := os.ReadFile(p)
	var vs []VisionSpec
	if err == nil && json.Unmarshal(b, &vs) == nil && len(vs) > 0 {
		visionSpecs, visionFake = vs, true
		logger.Printf("test picture files from %s (given to the engine only when marked \"engine\")", p)
	}
}

// visionToLoad: the file to give the engine for model m — when pictures were asked for in this run and the file is
// there. Caller holds a.mu.
func (a *App) visionToLoad(m *ModelSpec) (path string, on bool) {
	if !a.visionOn || m == nil {
		return "", false
	}
	v := visionFor(m.ID)
	if !a.visionPresent(v) {
		return "", false
	}
	if visionFake && !v.Engine {
		return "", true
	}
	return a.visionPath(v), true
}

// visionStateJSON: the picture file of the active model and every picture file of the catalogue (the model menu).
// Caller holds a.mu.
func (a *App) visionStateJSON() map[string]any {
	files := []map[string]any{}
	for i := range visionSpecs {
		v := &visionSpecs[i]
		p := a.visionPresent(v)
		var partial int64
		if !p {
			if st, err := os.Stat(a.visionPath(v) + ".part"); err == nil {
				partial = st.Size()
			}
		}
		files = append(files, map[string]any{"id": v.ID, "name": v.Name, "for": v.For, "file": v.File, "url": v.URL,
			"page": v.Page, "size": v.Size, "present": p, "partial": partial})
	}
	cur := ""
	if v := visionFor(a.cfg.ActiveModel); v != nil {
		cur = v.ID
	}
	return map[string]any{
		"files":    files,
		"current":  cur,              // "" — the active model reads no pictures (an own .gguf file)
		"on":       a.visionOn,       // pictures were asked for in this run
		"loaded":   a.engInfo.Vision, // the running engine reads pictures
		"tokens":   visionTokens,     // tokens of one picture
		"download": a.mdl,            // download of a picture file
		"ram_gb":   a.machine.RamGB,  // for the memory note of the page
		"model":    a.cfg.ActiveModel,
		"error":    a.visionErr, // the engine failed with the picture file: it works without it now
	}
}

// visionFallback: the engine started with the picture file has failed — it could not load the file (not enough
// memory, a damaged file) or it stopped while reading a picture. The model goes on without pictures in this run:
// the engine starts again without the file, and the window says why (vision.error: the engine's own words). False
// when pictures are no longer asked for (the file was deleted meanwhile) or the model was unloaded: a usual error.
func (a *App) visionFallback(msg, logTail string) bool {
	a.mu.Lock()
	if !a.visionOn || a.unloaded {
		a.mu.Unlock()
		return false
	}
	e := engineErrorLine(logTail)
	if e == "" {
		e = msg
	}
	a.visionOn, a.visionErr = false, e
	a.engStatus, a.engErr, a.engLog = "stopped", "", ""
	a.engInfo = EngineInfo{}
	a.mu.Unlock()
	logger.Printf("the engine failed with the picture file (%s): it starts again without it", e)
	a.maybeStartEngine()
	return true
}

// engineErrorLine: what the engine itself said — the first error line at the end of its log, without the time
// (llama.cpp writes "0.00.033.106 E gguf_init_from_reader: invalid magic characters…"); "" when there is none.
func engineErrorLine(tail string) string {
	for _, l := range strings.Split(tail, "\n") {
		f := strings.Fields(l)
		if len(f) >= 3 && f[1] == "E" {
			s := strings.Join(f[2:], " ")
			if r := []rune(s); len(r) > 240 {
				s = string(r[:240]) + "…"
			}
			return s
		}
	}
	return ""
}

func (a *App) setMDL(f func(d *DownloadState)) {
	a.mu.Lock()
	f(&a.mdl)
	a.mu.Unlock()
}

// startVisionDownload downloads the picture file v in the background (its own download state: the model, the
// translation and the window keep working). Then, if pictures are asked for, the engine restarts with it.
func (a *App) startVisionDownload(v *VisionSpec) error {
	a.mu.Lock()
	if a.mdl.Active {
		a.mu.Unlock()
		return errors.New(tr("идёт скачивание, дождитесь окончания"))
	}
	ctx, cancel := context.WithCancel(context.Background())
	a.mdlCancel = cancel
	a.mdl = DownloadState{Active: true, Item: "vision", Name: v.ID, Phase: "download", Total: v.Size}
	a.mu.Unlock()
	go func() {
		defer cancel()
		err := a.fetchTo(ctx, v.URL, a.visionPath(v), v.Size, v.SHA256, a.setMDL)
		a.mu.Lock()
		a.mdl.Active, a.mdl.Phase = false, ""
		if err != nil {
			if errors.Is(err, context.Canceled) {
				a.mdl.Error = tr("скачивание отменено")
			} else {
				a.mdl.Error = err.Error()
			}
		} else {
			a.mdl.Error = ""
		}
		a.mu.Unlock()
		if err != nil {
			logger.Printf("picture file download failed: %v", err)
			return
		}
		logger.Printf("picture file installed: %s", v.File)
		a.restartForVision()
	}()
	return nil
}

// restartForVision restarts a running (or starting) engine when it should read pictures now and does not, or the
// other way round. It returns true when the engine restarts.
func (a *App) restartForVision() bool {
	a.mu.Lock()
	m := a.findModel(a.cfg.ActiveModel)
	_, want := a.visionToLoad(m)
	running := a.engStatus == "ready" || a.engStatus == "starting"
	differs := running && want != a.engVision
	a.mu.Unlock()
	if !differs {
		return false
	}
	logger.Printf("engine restarts to %s pictures", map[bool]string{true: "read", false: "stop reading"}[want])
	a.stopEngine()
	a.mu.Lock()
	a.engStatus, a.engErr, a.engLog = "stopped", "", ""
	a.engInfo = EngineInfo{}
	a.mu.Unlock()
	a.maybeStartEngine()
	return true
}

func (a *App) visionRoutes(mux *http.ServeMux) {
	// {"action": "on"} — read pictures in this run: the engine restarts with the picture file of the model (if it
	// is there); "download" — download it (and then read pictures); "download" with "id" — download that file only
	// (the model menu: pictures are not asked for yet); "cancel" — stop the download.
	mux.HandleFunc("/api/vision", a.post(func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Action string `json:"action"`
			ID     string `json:"id"`
		}
		if err := json.NewDecoder(io.LimitReader(r.Body, 1024)).Decode(&req); err != nil {
			jsonError(w, 400, "bad request")
			return
		}
		a.mu.Lock()
		v := visionFor(a.cfg.ActiveModel)
		a.mu.Unlock()
		switch req.Action {
		case "cancel":
			a.mu.Lock()
			if a.mdlCancel != nil && a.mdl.Active {
				a.mdlCancel()
			}
			a.mu.Unlock()
			writeJSON(w, 200, map[string]any{"ok": true})
			return
		case "on", "download":
		default:
			jsonError(w, 400, "bad action")
			return
		}
		if req.ID != "" {
			f := findVision(req.ID)
			if f == nil || req.Action != "download" {
				jsonError(w, 400, tr("неизвестный файл"))
				return
			}
			if a.visionPresent(f) {
				writeJSON(w, 200, map[string]any{"ok": true, "present": true})
				return
			}
			if err := a.startVisionDownload(f); err != nil {
				jsonError(w, 409, err.Error())
				return
			}
			writeJSON(w, 200, map[string]any{"ok": true, "present": false, "downloading": true})
			return
		}
		if v == nil {
			jsonError(w, 409, tr("эта модель не читает картинки: нужна Gemma 4 из каталога"))
			return
		}
		a.mu.Lock()
		a.visionOn, a.visionErr = true, ""
		present := a.visionPresent(v)
		a.mu.Unlock()
		if !present {
			if req.Action != "download" {
				writeJSON(w, 200, map[string]any{"ok": true, "present": false})
				return
			}
			if err := a.startVisionDownload(v); err != nil {
				jsonError(w, 409, err.Error())
				return
			}
			writeJSON(w, 200, map[string]any{"ok": true, "present": false, "downloading": true})
			return
		}
		restarting := a.restartForVision()
		writeJSON(w, 200, map[string]any{"ok": true, "present": true, "restarting": restarting})
	}))
	mux.HandleFunc("/api/vision/", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodDelete {
			jsonError(w, 405, "method not allowed")
			return
		}
		v := findVision(strings.TrimPrefix(r.URL.Path, "/api/vision/"))
		if v == nil {
			jsonError(w, 404, tr("неизвестный файл"))
			return
		}
		a.mu.Lock()
		busy := a.mdl.Active && a.mdl.Name == v.ID
		inUse := a.engVision && visionFor(a.cfg.ActiveModel) == v
		if inUse {
			a.visionOn = false // the engine restarts without it below
		}
		a.mu.Unlock()
		if busy {
			jsonError(w, 409, tr("идёт скачивание, дождитесь окончания"))
			return
		}
		if inUse {
			a.restartForVision()
		}
		p := a.visionPath(v)
		if err := os.Remove(p); err != nil && !errors.Is(err, os.ErrNotExist) {
			jsonError(w, 500, tr("не удалось удалить файл: ")+err.Error())
			return
		}
		_ = os.Remove(p + ".part")
		logger.Printf("picture file deleted: %s", v.File)
		writeJSON(w, 200, map[string]any{"ok": true})
	})
}

// visionNote: the line of the engine log about the picture file (shown in «Подробности» when the engine fails).
func visionNote(path string) string {
	if path == "" {
		return ""
	}
	return fmt.Sprintf("pictures: %s, %d tokens", filepath.Base(path), visionTokens)
}
