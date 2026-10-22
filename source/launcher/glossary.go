package main

// Personal glossaries: plain table files in data/glossary (UTF-8 with BOM, tab-separated, Excel-friendly).
// The UI parses and writes the table; the launcher only lists, reads and stores the files.

import (
	"errors"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"unicode/utf16"
	"unicode/utf8"
)

const maxGlossaryBytes = 2 << 20

var glossaryExts = map[string]bool{".tsv": true, ".csv": true, ".txt": true}

func (a *App) glossaryDir() string { return filepath.Join(a.dataDir, "glossary") }

// glossaryName checks a file name sent by the UI: a plain name inside data/glossary.
// A name without a known extension gets ".tsv".
func glossaryName(raw string) (string, error) {
	return plainFileName(raw, glossaryExts, tr("недопустимое имя файла словаря"))
}

// plainFileName checks a file name sent by the UI: a plain name (no folders, no names Windows reserves),
// at most 100 characters. A name whose extension is not in exts gets ".tsv".
func plainFileName(raw string, exts map[string]bool, errText string) (string, error) {
	bad := errors.New(errText)
	name := strings.TrimSpace(raw)
	if name == "" || utf8.RuneCountInString(name) > 100 || strings.ContainsAny(name, "/\\:*?\"<>|") ||
		strings.HasPrefix(name, ".") || strings.HasSuffix(name, ".") || strings.Contains(name, "..") {
		return "", bad
	}
	for _, r := range name {
		if r < 32 || r == 0x7f {
			return "", bad
		}
	}
	if !exts[strings.ToLower(filepath.Ext(name))] {
		name += ".tsv"
	}
	// names Windows reserves for devices
	base := strings.ToUpper(strings.TrimSuffix(name, filepath.Ext(name)))
	switch base {
	case "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9",
		"LPT1", "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9":
		return "", bad
	}
	return name, nil
}

// Windows code pages for files saved by older programs ("Text (tab delimited)" in Excel).
const cp1251High = "\u0402\u0403\u201a\u0453\u201e\u2026\u2020\u2021\u20ac\u2030\u0409\u2039\u040a\u040c\u040b\u040f\u0452\u2018\u2019\u201c\u201d\u2022\u2013\u2014\ufffd\u2122\u0459\u203a\u045a\u045c\u045b\u045f\u00a0\u040e\u045e\u0408\u00a4\u0490\u00a6\u00a7\u0401\u00a9\u0404\u00ab\u00ac\u00ad\u00ae\u0407\u00b0\u00b1\u0406\u0456\u0491\u00b5\u00b6\u00b7\u0451\u2116\u0454\u00bb\u0458\u0405\u0455\u0457\u0410\u0411\u0412\u0413\u0414\u0415\u0416\u0417\u0418\u0419\u041a\u041b\u041c\u041d\u041e\u041f\u0420\u0421\u0422\u0423\u0424\u0425\u0426\u0427\u0428\u0429\u042a\u042b\u042c\u042d\u042e\u042f\u0430\u0431\u0432\u0433\u0434\u0435\u0436\u0437\u0438\u0439\u043a\u043b\u043c\u043d\u043e\u043f\u0440\u0441\u0442\u0443\u0444\u0445\u0446\u0447\u0448\u0449\u044a\u044b\u044c\u044d\u044e\u044f"
const cp1252Ctl = "\u20ac\ufffd\u201a\u0192\u201e\u2026\u2020\u2021\u02c6\u2030\u0160\u2039\u0152\ufffd\u017d\ufffd\ufffd\u2018\u2019\u201c\u201d\u2022\u2013\u2014\u02dc\u2122\u0161\u203a\u0153\ufffd\u017e\u0178"

// decodeText returns UTF-8 text from UTF-8 (with or without BOM), UTF-16 with BOM, or a Windows
// single-byte code page: Cyrillic (1251) when most non-ASCII bytes look like Cyrillic letters, else 1252.
func decodeText(b []byte) string {
	switch {
	case len(b) >= 2 && b[0] == 0xFF && b[1] == 0xFE:
		return decodeUTF16(b[2:], false)
	case len(b) >= 2 && b[0] == 0xFE && b[1] == 0xFF:
		return decodeUTF16(b[2:], true)
	case len(b) >= 3 && b[0] == 0xEF && b[1] == 0xBB && b[2] == 0xBF:
		return strings.ToValidUTF8(string(b[3:]), "�")
	}
	if utf8.Valid(b) {
		return string(b)
	}
	high, letters := 0, 0
	for _, c := range b {
		if c >= 0xC0 {
			high++
		}
		if c >= 0xC0 || (c|0x20 >= 'a' && c|0x20 <= 'z') {
			letters++
		}
	}
	cyr := []rune(cp1251High)
	ctl := []rune(cp1252Ctl)
	var sb strings.Builder
	for _, c := range b {
		switch {
		case c < 0x80:
			sb.WriteByte(c)
		case letters > 0 && high*10 > letters*3:
			sb.WriteRune(cyr[c-0x80])
		case c < 0xA0:
			sb.WriteRune(ctl[c-0x80])
		default:
			sb.WriteRune(rune(c)) // Latin-1 range of 1252
		}
	}
	return sb.String()
}

func decodeUTF16(b []byte, bigEndian bool) string {
	u := make([]uint16, 0, len(b)/2)
	for i := 0; i+1 < len(b); i += 2 {
		if bigEndian {
			u = append(u, uint16(b[i])<<8|uint16(b[i+1]))
		} else {
			u = append(u, uint16(b[i])|uint16(b[i+1])<<8)
		}
	}
	return string(utf16.Decode(u))
}

// dataFile describes a user's table file (a glossary or a collection of saved translations).
type dataFile struct {
	Name  string `json:"name"`
	Size  int64  `json:"size"`
	MTime int64  `json:"mtime"`
}

// listDataFiles lists the files with the given extensions in dir whose names pass check, sorted by name.
func listDataFiles(dir string, exts map[string]bool, check func(string) (string, error)) []dataFile {
	entries, _ := os.ReadDir(dir)
	files := []dataFile{}
	for _, e := range entries {
		if e.IsDir() || !exts[strings.ToLower(filepath.Ext(e.Name()))] || strings.HasPrefix(e.Name(), ".") {
			continue
		}
		if n, err := check(e.Name()); err != nil || n != e.Name() {
			continue
		}
		info, err := e.Info()
		if err != nil {
			continue
		}
		files = append(files, dataFile{e.Name(), info.Size(), info.ModTime().UnixMilli()})
	}
	sort.Slice(files, func(i, j int) bool { return strings.ToLower(files[i].Name) < strings.ToLower(files[j].Name) })
	return files
}

func (a *App) listGlossaries() []dataFile {
	return listDataFiles(a.glossaryDir(), glossaryExts, glossaryName)
}

func (a *App) glossaryRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/api/glossary", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet {
			jsonError(w, 405, "method not allowed")
			return
		}
		writeJSON(w, 200, map[string]any{"dir": a.glossaryDir(), "files": a.listGlossaries()})
	})
	// GET reads a glossary as UTF-8 text; PUT stores it (?create=1 refuses to overwrite an existing file).
	mux.HandleFunc("/api/glossary/", func(w http.ResponseWriter, r *http.Request) {
		name, err := glossaryName(strings.TrimPrefix(r.URL.Path, "/api/glossary/"))
		if err != nil {
			jsonError(w, 400, err.Error())
			return
		}
		p := filepath.Join(a.glossaryDir(), name)
		a.glossMu.Lock()
		defer a.glossMu.Unlock()
		switch r.Method {
		case http.MethodGet:
			b, err := os.ReadFile(p)
			if errors.Is(err, os.ErrNotExist) {
				jsonError(w, 404, tr("нет такого словаря"))
				return
			}
			if err != nil {
				jsonError(w, 500, err.Error())
				return
			}
			w.Header().Set("Content-Type", "text/plain; charset=utf-8")
			w.Header().Set("Cache-Control", "no-store")
			if st, err := os.Stat(p); err == nil {
				w.Header().Set("X-Mtime", strconv.FormatInt(st.ModTime().UnixMilli(), 10))
			}
			_, _ = io.WriteString(w, decodeText(b))
		case http.MethodPut:
			body, err := io.ReadAll(io.LimitReader(r.Body, maxGlossaryBytes+1))
			if err != nil {
				jsonError(w, 400, tr("не удалось прочитать запрос"))
				return
			}
			if len(body) > maxGlossaryBytes {
				jsonError(w, 413, tr("словарь больше 2 МБ"))
				return
			}
			if r.URL.Query().Get("create") == "1" {
				if _, err := os.Stat(p); err == nil {
					jsonError(w, 409, tr("словарь с таким именем уже есть"))
					return
				}
			}
			if err := os.MkdirAll(a.glossaryDir(), 0o755); err != nil {
				jsonError(w, 500, err.Error())
				return
			}
			tmp := p + ".tmp"
			if err := os.WriteFile(tmp, body, 0o644); err != nil {
				jsonError(w, 500, tr("не удалось записать файл: ")+err.Error())
				return
			}
			if err := os.Rename(tmp, p); err != nil {
				_ = os.Remove(tmp)
				jsonError(w, 500, tr("не удалось записать файл: ")+err.Error())
				return
			}
			var mtime int64
			if st, err := os.Stat(p); err == nil {
				mtime = st.ModTime().UnixMilli()
			}
			writeJSON(w, 200, map[string]any{"name": name, "size": len(body), "path": p, "mtime": mtime})
		default:
			jsonError(w, 405, "method not allowed")
		}
	})
}
