package main

// Saved translations: table files in data/saved (UTF-8 with BOM, tab-separated, Excel-friendly), one file per
// collection (an article, a project, a topic). The UI chooses the file; the launcher reads it, adds rows and
// deletes rows, so a file edited in a spreadsheet is picked up on the next read.
// Versions up to 0.5 kept one file, data/saved.tsv; the first start of 0.5.1 moves it into the folder.

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"
)

const (
	maxSavedBytes   = 16 << 20 // a larger file is not read: it is not a collection of translations
	maxSavedRequest = 8 << 20  // one request: a whole imported file
)

var (
	savedHeader = "id\tвремя\tс\tна\tстиль\tисходный текст\tперевод\tконтекст"
	savedExts   = map[string]bool{".tsv": true}
)

type SavedItem struct {
	ID          string   `json:"id"`
	Time        string   `json:"time"`
	From        string   `json:"from"`
	To          string   `json:"to"`
	Style       string   `json:"style"`
	Source      string   `json:"source"`
	Translation string   `json:"translation"`
	Context     string   `json:"context"`
	extra       []string // columns after the eighth (added by hand in a spreadsheet): written back as they are
}

// savedTable is one file: its header line (kept with any extra column names) and its rows.
type savedTable struct {
	header string
	items  []SavedItem
}

func (a *App) savedDir() string { return filepath.Join(a.dataDir, "saved") }

// savedDefault is the name of the first collection: "Сохранённые.tsv" in the interface language.
func savedDefault() string { return tr("Сохранённые") + ".tsv" }

// savedName checks a file name sent by the UI: a plain name inside data/saved; ".tsv" is added when missing.
func savedName(raw string) (string, error) {
	return plainFileName(raw, savedExts, tr("недопустимое имя файла"))
}

func (a *App) listSaved() []dataFile { return listDataFiles(a.savedDir(), savedExts, savedName) }

// migrateSaved moves data/saved.tsv of version 0.5 and earlier into data/saved (as "Сохранённые.tsv",
// or "Сохранённые (2).tsv" if that name is taken). The default file of a fresh folder is not created here
// but on the first listing (ensureSavedFile): by then the user may have chosen the interface language on the
// first-start screen, and the file gets its name in that language.
func (a *App) migrateSaved() {
	a.savedMu.Lock()
	defer a.savedMu.Unlock()
	if err := os.MkdirAll(a.savedDir(), 0o755); err != nil {
		logger.Printf("saved: %v", err)
		return
	}
	old := filepath.Join(a.dataDir, "saved.tsv")
	if st, err := os.Stat(old); err == nil && !st.IsDir() {
		dst := freeName(a.savedDir(), savedDefault())
		if err := os.Rename(old, dst); err != nil {
			logger.Printf("saved: could not move %s: %v", old, err)
		} else {
			logger.Printf("saved: moved %s to %s", old, dst)
		}
	}
}

// ensureSavedFile creates the default file when the folder has none (the UI always has a file to show).
func (a *App) ensureSavedFile() {
	if len(a.listSaved()) > 0 {
		return
	}
	p := filepath.Join(a.savedDir(), savedDefault())
	if err := writeSavedFile(p, savedTable{header: savedHeader}); err != nil {
		logger.Printf("saved: %v", err)
	}
}

// freeName returns dir/name, or dir/"name (2).ext", "(3)"… if the name is taken.
func freeName(dir, name string) string {
	p := filepath.Join(dir, name)
	ext := filepath.Ext(name)
	for i := 2; ; i++ {
		if _, err := os.Stat(p); errors.Is(err, os.ErrNotExist) {
			return p
		}
		p = filepath.Join(dir, strings.TrimSuffix(name, ext)+" ("+strconv.Itoa(i)+")"+ext)
	}
}

// tsvCell prepares a value for one cell: line breaks and tabs become spaces; a value with a double quote is
// quoted the way spreadsheets do it ("…" with "" inside).
func tsvCell(s string) string {
	s = strings.NewReplacer("\r\n", " ", "\r", " ", "\n", " ", "\t", " ").Replace(s)
	if strings.Contains(s, `"`) {
		return `"` + strings.ReplaceAll(s, `"`, `""`) + `"`
	}
	return s
}

// splitTSV splits one line into cells; a cell that starts with a double quote is read the way spreadsheets
// write it.
func splitTSV(line string) []string {
	if !strings.Contains(line, `"`) {
		return strings.Split(line, "\t")
	}
	var out []string
	var cur strings.Builder
	inQ, start := false, true
	for i := 0; i < len(line); i++ {
		ch := line[i]
		switch {
		case inQ:
			if ch == '"' {
				if i+1 < len(line) && line[i+1] == '"' {
					cur.WriteByte('"')
					i++
				} else {
					inQ = false
				}
			} else {
				cur.WriteByte(ch)
			}
		case ch == '"' && start:
			inQ, start = true, false
		case ch == '\t':
			out = append(out, cur.String())
			cur.Reset()
			start = true
		default:
			cur.WriteByte(ch)
			start = false
		}
	}
	return append(out, cur.String())
}

// readSavedFile reads a collection. Rows typed in a spreadsheet without an id get one made from their text;
// repeated ids get a suffix, so every row can be deleted on its own.
func readSavedFile(p string) (savedTable, error) {
	t := savedTable{header: savedHeader, items: []SavedItem{}}
	st, err := os.Stat(p)
	if errors.Is(err, os.ErrNotExist) {
		return t, nil
	}
	if err != nil {
		return t, err
	}
	if st.Size() > maxSavedBytes {
		return t, errors.New(tr("файл больше 16 МБ — это не похоже на сохранённые переводы"))
	}
	b, err := os.ReadFile(p)
	if err != nil {
		return t, err
	}
	seen := map[string]int{}
	for i, line := range strings.Split(decodeText(b), "\n") {
		line = strings.TrimRight(line, "\r")
		if i == 0 {
			line = strings.TrimPrefix(line, "\ufeff")
			if strings.HasPrefix(strings.ToLower(line), "id\t") {
				t.header = line
				continue
			}
		}
		if strings.TrimSpace(line) == "" {
			continue
		}
		c := splitTSV(line)
		for len(c) < 8 {
			c = append(c, "")
		}
		it := SavedItem{ID: strings.TrimSpace(c[0]), Time: c[1], From: c[2], To: c[3], Style: c[4],
			Source: c[5], Translation: c[6], Context: c[7]}
		if len(c) > 8 {
			it.extra = c[8:]
		}
		if it.ID == "" {
			h := sha256.Sum256([]byte(line))
			it.ID = "r" + hex.EncodeToString(h[:5])
		}
		if n := seen[it.ID]; n > 0 {
			seen[it.ID] = n + 1
			it.ID += "-" + strconv.Itoa(n+1)
		} else {
			seen[it.ID] = 1
		}
		t.items = append(t.items, it)
	}
	return t, nil
}

func writeSavedFile(p string, t savedTable) error {
	var sb strings.Builder
	sb.WriteString("\ufeff" + t.header + "\r\n")
	for _, it := range t.items {
		cells := []string{it.ID, it.Time, it.From, it.To, it.Style, it.Source, it.Translation, it.Context}
		cells = append(cells, it.extra...)
		for i := range cells {
			cells[i] = tsvCell(cells[i])
		}
		sb.WriteString(strings.Join(cells, "\t") + "\r\n")
	}
	if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
		return err
	}
	tmp := p + ".tmp"
	if err := os.WriteFile(tmp, []byte(sb.String()), 0o644); err != nil {
		return errors.New(tr("не удалось записать файл: ") + err.Error())
	}
	if err := os.Rename(tmp, p); err != nil {
		_ = os.Remove(tmp)
		return errors.New(tr("не удалось записать файл (возможно, он открыт в другой программе, например в Excel): ") + err.Error())
	}
	return nil
}

// newSavedID returns a short id that grows with time and never repeats within this run (call under savedMu).
func (a *App) newSavedID() string {
	ms := time.Now().UnixMilli()
	if ms <= a.lastSavedID {
		ms = a.lastSavedID + 1
	}
	a.lastSavedID = ms
	return strconv.FormatInt(ms, 36)
}

// savedFileParam returns the checked file name of a request (?file=…); without it — the default file.
func savedFileParam(r *http.Request) (string, error) {
	f := r.URL.Query().Get("file")
	if f == "" {
		f = savedDefault()
	}
	return savedName(f)
}

func clip(s string, n int) string {
	if r := []rune(s); len(r) > n {
		return string(r[:n])
	}
	return s
}

func (a *App) savedRoutes(mux *http.ServeMux) {
	// GET lists the files; POST {name, copy_from} creates a file (empty or a copy of another one).
	mux.HandleFunc("/api/saved-files", func(w http.ResponseWriter, r *http.Request) {
		a.savedMu.Lock()
		defer a.savedMu.Unlock()
		switch r.Method {
		case http.MethodGet:
			a.ensureSavedFile()
			writeJSON(w, 200, map[string]any{"dir": a.savedDir(), "files": a.listSaved(), "default": savedDefault()})
		case http.MethodPost:
			var req struct {
				Name     string `json:"name"`
				CopyFrom string `json:"copy_from"`
			}
			if err := json.NewDecoder(io.LimitReader(r.Body, 4096)).Decode(&req); err != nil {
				jsonError(w, 400, tr("неверный запрос"))
				return
			}
			name, err := savedName(req.Name)
			if err != nil {
				jsonError(w, 400, err.Error())
				return
			}
			p := filepath.Join(a.savedDir(), name)
			if _, err := os.Stat(p); err == nil {
				jsonError(w, 409, tr("файл с таким именем уже есть"))
				return
			}
			t := savedTable{header: savedHeader}
			if req.CopyFrom != "" {
				from, err := savedName(req.CopyFrom)
				if err != nil {
					jsonError(w, 400, err.Error())
					return
				}
				if t, err = readSavedFile(filepath.Join(a.savedDir(), from)); err != nil {
					jsonError(w, 500, err.Error())
					return
				}
			}
			if err := writeSavedFile(p, t); err != nil {
				jsonError(w, 500, err.Error())
				return
			}
			writeJSON(w, 200, map[string]any{"name": name, "path": p})
		default:
			jsonError(w, 405, "method not allowed")
		}
	})
	// GET ?file= returns the rows; POST ?file= adds one row ({…}) or many ({"items": […]}).
	mux.HandleFunc("/api/saved", func(w http.ResponseWriter, r *http.Request) {
		name, err := savedFileParam(r)
		if err != nil {
			jsonError(w, 400, err.Error())
			return
		}
		p := filepath.Join(a.savedDir(), name)
		a.savedMu.Lock()
		defer a.savedMu.Unlock()
		switch r.Method {
		case http.MethodGet:
			t, err := readSavedFile(p)
			if err != nil {
				jsonError(w, 500, err.Error())
				return
			}
			var mtime int64
			if st, err := os.Stat(p); err == nil {
				mtime = st.ModTime().UnixMilli()
			}
			writeJSON(w, 200, map[string]any{"file": name, "path": p, "mtime": mtime, "items": t.items})
		case http.MethodPost:
			var req struct {
				Items []SavedItem `json:"items"`
				SavedItem
			}
			if err := json.NewDecoder(io.LimitReader(r.Body, maxSavedRequest)).Decode(&req); err != nil {
				jsonError(w, 400, tr("неверный запрос"))
				return
			}
			add := req.Items
			if add == nil {
				add = []SavedItem{req.SavedItem}
			}
			t, err := readSavedFile(p)
			if err != nil {
				jsonError(w, 500, err.Error())
				return
			}
			now := time.Now().Format(time.RFC3339)
			ids := make([]string, 0, len(add))
			for _, it := range add {
				it = SavedItem{ID: a.newSavedID(), Time: clip(strings.TrimSpace(it.Time), 40), From: clip(it.From, 20),
					To: clip(it.To, 20), Style: clip(it.Style, 300), Source: it.Source, Translation: it.Translation,
					Context: clip(it.Context, 2000)}
				if it.Time == "" {
					it.Time = now
				}
				t.items = append(t.items, it)
				ids = append(ids, it.ID)
			}
			if err := writeSavedFile(p, t); err != nil {
				jsonError(w, 500, err.Error())
				return
			}
			res := map[string]any{"ids": ids, "file": name}
			if len(ids) > 0 {
				res["id"] = ids[0]
			}
			writeJSON(w, 200, res)
		default:
			jsonError(w, 405, "method not allowed")
		}
	})
	// DELETE /api/saved/<id>?file= removes one row.
	mux.HandleFunc("/api/saved/", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodDelete {
			jsonError(w, 405, "method not allowed")
			return
		}
		name, err := savedFileParam(r)
		if err != nil {
			jsonError(w, 400, err.Error())
			return
		}
		id := strings.TrimPrefix(r.URL.Path, "/api/saved/")
		p := filepath.Join(a.savedDir(), name)
		a.savedMu.Lock()
		defer a.savedMu.Unlock()
		t, err := readSavedFile(p)
		if err != nil {
			jsonError(w, 500, err.Error())
			return
		}
		out := t.items[:0]
		for _, it := range t.items {
			if it.ID != id {
				out = append(out, it)
			}
		}
		if len(out) == len(t.items) {
			jsonError(w, 404, tr("запись не найдена — возможно, файл изменили в другой программе"))
			return
		}
		t.items = out
		if err := writeSavedFile(p, t); err != nil {
			jsonError(w, 500, err.Error())
			return
		}
		writeJSON(w, 200, map[string]any{"ok": true})
	})
}
