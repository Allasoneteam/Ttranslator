package main

import (
	"encoding/json"
	"io"
	"log"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"unicode/utf16"
)

func testApp(t *testing.T) *App {
	t.Helper()
	logger = log.New(io.Discard, "", 0)
	return &App{dataDir: t.TempDir()}
}

func TestSavedName(t *testing.T) {
	ok := map[string]string{"Статья 1": "Статья 1.tsv", "laser.tsv": "laser.tsv", "notes.txt": "notes.txt.tsv", " v2 ": "v2.tsv"}
	for in, want := range ok {
		if got, err := savedName(in); err != nil || got != want {
			t.Errorf("savedName(%q) = %q, %v; want %q", in, got, err, want)
		}
	}
	for _, in := range []string{"", "../x", `a\b`, "con", ".x", "x."} {
		if got, err := savedName(in); err == nil {
			t.Errorf("savedName(%q) = %q, want an error", in, got)
		}
	}
}

func TestTSVCells(t *testing.T) {
	in := []string{`He said "yes"`, "a\tb", "line1\r\nline2\nline3", `"quoted"`, "", "plain"}
	cells := make([]string, len(in))
	for i, v := range in {
		cells[i] = tsvCell(v)
	}
	got := splitTSV(strings.Join(cells, "\t"))
	want := []string{`He said "yes"`, "a b", "line1 line2 line3", `"quoted"`, "", "plain"}
	if len(got) != len(want) {
		t.Fatalf("cells: %q", got)
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("cell %d: %q, want %q", i, got[i], want[i])
		}
	}
}

func TestReadWriteSavedFile(t *testing.T) {
	dir := t.TempDir()
	p := filepath.Join(dir, "s.tsv")
	text := "\ufeffid\tвремя\tс\tна\tстиль\tисходный текст\tперевод\tконтекст\tпримечание\r\n" +
		"a1\t2026-10-09T12:02:23+02:00\ten\tru\tНаучный\tClosed form.\tЗамкнутая форма.\t\tмоё\r\n" +
		"\r\n" +
		"\t\ten\tru\t\tTyped by hand\tВписано вручную\t\r\n" +
		"a1\t\ten\tde\t\tSame id\tGleiche id\t\r\n" +
		"b2\t\ten\tru\t\t\"A \"\"quoted\"\" word\"\tСлово\t\r\n"
	if err := os.WriteFile(p, []byte(text), 0o644); err != nil {
		t.Fatal(err)
	}
	tb, err := readSavedFile(p)
	if err != nil {
		t.Fatal(err)
	}
	if len(tb.items) != 4 {
		t.Fatalf("items: %d", len(tb.items))
	}
	if tb.items[0].ID != "a1" || tb.items[0].Translation != "Замкнутая форма." || len(tb.items[0].extra) != 1 || tb.items[0].extra[0] != "моё" {
		t.Errorf("row 1: %+v", tb.items[0])
	}
	if !strings.HasPrefix(tb.items[1].ID, "r") || len(tb.items[1].ID) != 11 {
		t.Errorf("row without id: %q", tb.items[1].ID)
	}
	if tb.items[2].ID != "a1-2" {
		t.Errorf("repeated id: %q", tb.items[2].ID)
	}
	if tb.items[3].Source != `A "quoted" word` {
		t.Errorf("quoted cell: %q", tb.items[3].Source)
	}
	if !strings.HasSuffix(tb.header, "\tпримечание") {
		t.Errorf("header: %q", tb.header)
	}
	// written back and read again: the same rows, the extra column and its header stay
	if err := writeSavedFile(p, tb); err != nil {
		t.Fatal(err)
	}
	again, err := readSavedFile(p)
	if err != nil {
		t.Fatal(err)
	}
	for i := range tb.items {
		a, b := tb.items[i], again.items[i]
		if a.ID != b.ID || a.Source != b.Source || a.Translation != b.Translation || strings.Join(a.extra, "|") != strings.Join(b.extra, "|") {
			t.Errorf("row %d changed: %+v -> %+v", i, a, b)
		}
	}
	raw, _ := os.ReadFile(p)
	if !strings.HasPrefix(string(raw), "\ufeffid\t") || !strings.Contains(string(raw), "\tмоё\r\n") || strings.Count(string(raw), "\r\n") != 5 {
		t.Errorf("file: %q", raw)
	}
	// a file saved by Excel as "Unicode text" (UTF-16)
	u := utf16.Encode([]rune("id\tвремя\tс\tна\tстиль\tисходный текст\tперевод\tконтекст\r\nx\t\tru\ten\t\tТекст\tText\t\r\n"))
	b16 := []byte{0xFF, 0xFE}
	for _, c := range u {
		b16 = append(b16, byte(c), byte(c>>8))
	}
	_ = os.WriteFile(p, b16, 0o644)
	if tb, err = readSavedFile(p); err != nil || len(tb.items) != 1 || tb.items[0].Source != "Текст" {
		t.Errorf("utf-16: %+v %v", tb.items, err)
	}
}

func TestMigrateSaved(t *testing.T) {
	a := testApp(t)
	old := "\ufeff" + savedHeader + "\r\nid1\t\ten\tru\t\tText\tТекст\t\r\n"
	_ = os.WriteFile(filepath.Join(a.dataDir, "saved.tsv"), []byte(old), 0o644)
	a.migrateSaved()
	moved, err := os.ReadFile(filepath.Join(a.savedDir(), savedDefault()))
	if err != nil || string(moved) != old {
		t.Fatalf("moved file: %q %v", moved, err)
	}
	if _, err := os.Stat(filepath.Join(a.dataDir, "saved.tsv")); !os.IsNotExist(err) {
		t.Errorf("old file is still there: %v", err)
	}
	// an old file appears again (an older version was started): it is moved under a free name
	_ = os.WriteFile(filepath.Join(a.dataDir, "saved.tsv"), []byte(old), 0o644)
	a.migrateSaved()
	if _, err := os.Stat(filepath.Join(a.savedDir(), "Сохранённые (2).tsv")); err != nil {
		t.Errorf("second move: %v", err)
	}
	// a fresh folder: nothing is created at the start; the first listing creates an empty default file named
	// in the interface language chosen by then (the first-start screen lets the user choose it)
	b := testApp(t)
	b.migrateSaved()
	if f := b.listSaved(); len(f) != 0 {
		t.Errorf("fresh folder after the start: %+v", f)
	}
	setUILang("en")
	defer setUILang("ru")
	mux := http.NewServeMux()
	b.savedRoutes(mux)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest(http.MethodGet, "/api/saved-files", nil))
	if f := b.listSaved(); rec.Code != 200 || len(f) != 1 || f[0].Name != "Saved.tsv" {
		t.Errorf("fresh folder after the first listing: %d %+v", rec.Code, f)
	}
}

func TestSavedRoutes(t *testing.T) {
	a := testApp(t)
	mux := http.NewServeMux()
	a.savedRoutes(mux)
	call := func(method, path, body string) (int, map[string]any) {
		req := httptest.NewRequest(method, path, strings.NewReader(body))
		rec := httptest.NewRecorder()
		mux.ServeHTTP(rec, req)
		var j map[string]any
		_ = json.Unmarshal(rec.Body.Bytes(), &j)
		return rec.Code, j
	}
	q := "?file=" + url.QueryEscape("Статья")
	if code, j := call("GET", "/api/saved-files", ""); code != 200 || len(j["files"].([]any)) != 1 {
		t.Fatalf("list: %d %v", code, j)
	}
	code, j := call("POST", "/api/saved"+q, `{"from":"en","to":"ru","style":"Научный","source":"Closed form.","translation":"Замкнутая форма."}`)
	if code != 200 || j["id"] == "" {
		t.Fatalf("add: %d %v", code, j)
	}
	code, j = call("POST", "/api/saved"+q, `{"items":[{"source":"a","translation":"б","time":"2026-01-01T10:00:00Z"},{"source":"c","translation":"д"},{"source":"e","translation":"ж"}]}`)
	ids := j["ids"].([]any)
	if code != 200 || len(ids) != 3 || ids[0] == ids[1] || ids[1] == ids[2] {
		t.Fatalf("add many: %d %v", code, j)
	}
	code, j = call("GET", "/api/saved"+q, "")
	items := j["items"].([]any)
	if code != 200 || len(items) != 4 || items[1].(map[string]any)["time"] != "2026-01-01T10:00:00Z" || j["file"] != "Статья.tsv" {
		t.Fatalf("read: %d %v", code, j)
	}
	if code, _ = call("DELETE", "/api/saved/"+ids[0].(string)+q, ""); code != 200 {
		t.Errorf("delete: %d", code)
	}
	if code, _ = call("DELETE", "/api/saved/nope"+q, ""); code != 404 {
		t.Errorf("delete unknown: %d", code)
	}
	if code, j = call("POST", "/api/saved-files", `{"name":"Копия","copy_from":"Статья.tsv"}`); code != 200 || j["name"] != "Копия.tsv" {
		t.Fatalf("copy: %d %v", code, j)
	}
	if _, j = call("GET", "/api/saved?file="+url.QueryEscape("Копия.tsv"), ""); len(j["items"].([]any)) != 3 {
		t.Errorf("copy has %d rows", len(j["items"].([]any)))
	}
	if code, _ = call("POST", "/api/saved-files", `{"name":"Копия"}`); code != 409 {
		t.Errorf("same name: %d", code)
	}
	if code, _ = call("POST", "/api/saved-files", `{"name":"../x"}`); code != 400 {
		t.Errorf("bad name: %d", code)
	}
	if code, _ = call("GET", "/api/saved?file=..%2Fx", ""); code != 400 {
		t.Errorf("bad file param: %d", code)
	}
	if code, j = call("GET", "/api/saved-files", ""); code != 200 || len(j["files"].([]any)) != 3 {
		t.Errorf("list after: %v", j)
	}
}
