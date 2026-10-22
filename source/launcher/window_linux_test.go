package main

import (
	"bytes"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// fakeWindow puts a shell script in place of the window program: it writes its arguments to args.txt and runs body.
func fakeWindow(t *testing.T, a *App, body string) string {
	t.Helper()
	args := filepath.Join(a.root, "args.txt")
	script := "#!/bin/sh\nprintf '%s\\n' \"$@\" > '" + args + "'\n" + body + "\n"
	if err := os.WriteFile(filepath.Join(a.root, windowHelperName), []byte(script), 0o755); err != nil {
		t.Fatal(err)
	}
	return args
}

func TestOwnWindow(t *testing.T) {
	a := testApp(t)
	a.root = t.TempDir()
	a.cfg = defaultConfig()
	u := "http://127.0.0.1:8765/"

	// no window program in the folder
	if err := a.startOwnWindow(u, false, true); err == nil || !strings.Contains(err.Error(), "нет программы окна "+windowHelperName) {
		t.Errorf("missing program: %v", err)
	}
	if a.windowStateJSON()["available"] != false {
		t.Errorf("available without the program: %v", a.windowStateJSON())
	}

	// the program cannot start its window: exit codes and the last line of stderr explain why
	for _, c := range []struct{ body, want string }{
		{"exit 3", "нет веб-движка системы: в Windows нужен Microsoft Edge WebView2 Runtime, в Linux — WebKitGTK 4.1"},
		{"echo 'error while loading shared libraries: libwebkit2gtk-4.1.so.0' >&2; exit 127", "не хватает системных библиотек (нужен WebKitGTK 4.1): error while loading shared libraries: libwebkit2gtk-4.1.so.0"},
		{"echo first >&2; echo 'second line' >&2; exit 1", "программа окна завершилась с кодом 1: second line"},
		{"exit 5", "программа окна завершилась с кодом 5"},
	} {
		fakeWindow(t, a, c.body)
		err := a.startOwnWindow(u, false, true)
		if err == nil || err.Error() != c.want {
			t.Errorf("%s: %v, want %q", c.body, err, c.want)
		}
	}

	// a working window: "ready", the arguments (maximized), the icon; closing it marks the window as gone
	args := fakeWindow(t, a, "echo ready; exec sleep 30")
	start := time.Now()
	if err := a.startOwnWindow(u, false, true); err != nil {
		t.Fatalf("working window: %v", err)
	}
	if time.Since(start) > 5*time.Second {
		t.Errorf("waited %v for ready", time.Since(start))
	}
	b, _ := os.ReadFile(args)
	data := filepath.Join(a.dataDir, "webview")
	icon := filepath.Join(data, "ttranslator.png")
	want := strings.Join([]string{u, "--title", "Ttranslator", "--size", windowSize, "--data", data, "--icon", icon, "--maximized"}, "\n") + "\n"
	if string(b) != want {
		t.Errorf("arguments:\n%s\nwant\n%s", b, want)
	}
	if png, err := os.ReadFile(icon); err != nil || !bytes.Equal(png, windowIconPNG) || !bytes.HasPrefix(png, []byte("\x89PNG")) {
		t.Errorf("icon: %v, %d bytes", err, len(png))
	}
	a.mu.Lock()
	running := a.windowCmd != nil
	st := a.windowStateJSON()
	a.mu.Unlock()
	if !running || st["available"] != true || st["error"] != "" {
		t.Errorf("state of a running window: %v %v", running, st)
	}
	a.closeOwnWindow()
	for i := 0; i < 50; i++ {
		a.mu.Lock()
		gone := !a.windowGone.IsZero()
		a.mu.Unlock()
		if gone {
			break
		}
		time.Sleep(100 * time.Millisecond)
	}
	if a.windowGone.IsZero() || a.windowCmd != nil {
		t.Errorf("closing the window: gone %v, cmd %v", a.windowGone, a.windowCmd)
	}

	// a window for another running copy is not kept by this one; not maximized when start_maximized is off
	args = fakeWindow(t, a, "echo ready; exec sleep 1")
	a.windowGone = time.Time{}
	if err := a.startOwnWindow(u, true, false); err != nil || a.windowCmd != nil {
		t.Errorf("second copy: %v, cmd %v", err, a.windowCmd)
	}
	if b, _ := os.ReadFile(args); strings.Contains(string(b), "--maximized") {
		t.Errorf("not maximized, arguments:\n%s", b)
	}
}

// The Edge/Chrome window (when the own window cannot open): maximized or of the usual size.
func TestAppWindowArgs(t *testing.T) {
	u := "http://127.0.0.1:8765/"
	if got := strings.Join(appWindowArgs(u, true), " "); got != "--app="+u+" --start-maximized --no-first-run --no-default-browser-check" {
		t.Errorf("maximized: %s", got)
	}
	if got := strings.Join(appWindowArgs(u, false), " "); got != "--app="+u+" --window-size=1180,780 --no-first-run --no-default-browser-check" {
		t.Errorf("usual size: %s", got)
	}
}

// Pages inside the own window say so (ttw=1) when they open their event stream.
func TestOwnWindowPages(t *testing.T) {
	a := testApp(t)
	a.root = t.TempDir()
	a.quit = make(chan struct{})
	srv := httptest.NewServer(http.HandlerFunc(a.handleEvents))
	defer srv.Close()
	count := func() int {
		a.mu.Lock()
		defer a.mu.Unlock()
		return a.ownPages
	}
	plain, err := http.Get(srv.URL + "/api/events?page=p1")
	if err != nil {
		t.Fatal(err)
	}
	own, err := http.Get(srv.URL + "/api/events?page=p2&ttw=1")
	if err != nil {
		t.Fatal(err)
	}
	time.Sleep(100 * time.Millisecond)
	if n := count(); n != 1 {
		t.Errorf("own pages: %d", n)
	}
	own.Body.Close()
	plain.Body.Close()
	for i := 0; i < 50 && count() != 0; i++ {
		time.Sleep(20 * time.Millisecond)
	}
	if n := count(); n != 0 {
		t.Errorf("own pages after closing: %d", n)
	}
}
