package main

// The own window of the program (launch_mode "window", a trial since 0.9.1). The small program ttranslator-window
// (source/window: C++ on the webview library, MIT) shows the interface in a native window with the web engine of
// the system: WebView2 on Windows, WebKitGTK on Linux. The launcher keeps to the Go standard library: it only
// starts that program and waits for its "ready". If the program is missing or cannot start (no WebView2 Runtime
// on an old Windows 10, no WebKitGTK 4.1 on Linux), an Edge/Chrome window opens instead and the reason is shown
// in the settings.

import (
	"bufio"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"sync"
	"time"
)

const (
	windowReadyTimeout = 30 * time.Second // the first start of WebView2 on a slow computer takes a while
	windowSize         = "1180x780"
)

// windowHelper is the path of the own-window program, or "" if it is not in the program folder.
func (a *App) windowHelper() string {
	p := filepath.Join(a.root, windowHelperName)
	if st, err := os.Stat(p); err == nil && !st.IsDir() {
		return p
	}
	return ""
}

// openUI opens a window of the program at u in the mode chosen in the settings. second: u belongs to another
// running copy of the program (this copy exits soon), so the own window is not tied to this process.
func (a *App) openUI(u string, second bool) {
	a.mu.Lock()
	mode := a.cfg.LaunchMode
	a.mu.Unlock()
	if mode == "window" {
		err := a.startOwnWindow(u, second)
		if err == nil {
			return
		}
		logger.Printf("own window: %v; opening an Edge/Chrome window instead", err)
		a.mu.Lock()
		a.windowErr = err.Error()
		a.mu.Unlock()
	}
	if err := openWindow(u, mode == "tab"); err != nil {
		logger.Printf("open window: %v", err)
	}
}

// tailBuffer keeps the last bytes written to it (what the window program printed on stderr).
type tailBuffer struct {
	mu sync.Mutex
	b  []byte
}

func (t *tailBuffer) Write(p []byte) (int, error) {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.b = append(t.b, p...)
	if len(t.b) > 4096 {
		t.b = t.b[len(t.b)-4096:]
	}
	return len(p), nil
}

func (t *tailBuffer) String() string {
	t.mu.Lock()
	defer t.mu.Unlock()
	return string(t.b)
}

// lastLine is the last non-empty line of s, shortened.
func lastLine(s string) string {
	lines := strings.Split(strings.TrimSpace(s), "\n")
	return clip(strings.TrimSpace(lines[len(lines)-1]), 200)
}

// windowStartError explains why the window program ended before its window appeared.
func windowStartError(err error, stderr string) error {
	var ee *exec.ExitError
	code := -1
	if errors.As(err, &ee) {
		code = ee.ExitCode()
	}
	switch {
	case code == 3:
		return errors.New(tr("нет веб-движка системы: в Windows нужен Microsoft Edge WebView2 Runtime, в Linux — WebKitGTK 4.1"))
	case code == 127:
		return fmt.Errorf("%s: %s", tr("не хватает системных библиотек (нужен WebKitGTK 4.1)"), lastLine(stderr))
	case code >= 0 && strings.TrimSpace(stderr) != "":
		return fmt.Errorf("%s: %s", fmt.Sprintf(tr("программа окна завершилась с кодом %d"), code), lastLine(stderr))
	case code >= 0:
		return fmt.Errorf(tr("программа окна завершилась с кодом %d"), code)
	}
	return err
}

// startOwnWindow starts the window program and waits until it says "ready" (or ends, or windowReadyTimeout passes).
func (a *App) startOwnWindow(u string, second bool) error {
	exe := a.windowHelper()
	if exe == "" {
		return fmt.Errorf(tr("нет программы окна %s в папке программы"), windowHelperName)
	}
	data := filepath.Join(a.dataDir, "webview")
	if err := os.MkdirAll(data, 0o755); err != nil {
		return err
	}
	args := append([]string{u, "--title", "Ttranslator", "--size", windowSize, "--data", data}, windowArgs(data)...)
	cmd := exec.Command(exe, args...)
	cmd.Dir = a.root
	windowChildAttrs(cmd)
	// own pipes (not buffers): the web engine's helper processes may keep stderr open after the window is gone,
	// and cmd.Wait must not wait for them
	outR, outW, err := os.Pipe()
	if err != nil {
		return err
	}
	errR, errW, err := os.Pipe()
	if err != nil {
		outR.Close()
		outW.Close()
		return err
	}
	cmd.Stdout, cmd.Stderr = outW, errW
	err = cmd.Start()
	outW.Close()
	errW.Close()
	if err != nil {
		outR.Close()
		errR.Close()
		return err
	}
	if !second {
		attachChild(cmd) // Windows: the window closes together with the launcher
	}
	ready := make(chan struct{})
	go func() {
		sc := bufio.NewScanner(outR)
		said := false
		for sc.Scan() {
			if !said && strings.TrimSpace(sc.Text()) == "ready" {
				said = true
				close(ready)
			}
		}
		outR.Close()
	}()
	stderr := &tailBuffer{}
	stderrDone := make(chan struct{})
	go func() {
		_, _ = io.Copy(stderr, errR)
		errR.Close()
		close(stderrDone)
	}()
	exited := make(chan error, 1)
	go func() { exited <- cmd.Wait() }()

	select {
	case <-ready:
	case err := <-exited:
		select {
		case <-stderrDone:
		case <-time.After(time.Second):
		}
		return windowStartError(err, stderr.String())
	case <-time.After(windowReadyTimeout):
		logger.Printf("own window: no answer in %v, keeping it", windowReadyTimeout)
	}
	logger.Printf("own window opened (%s)", filepath.Base(exe))
	done := make(chan struct{})
	if !second {
		a.mu.Lock()
		a.windowCmd, a.windowDone, a.windowErr = cmd, done, ""
		a.mu.Unlock()
	}
	go func() {
		err := <-exited
		close(done)
		if err != nil {
			logger.Printf("own window ended: %v %s", err, lastLine(stderr.String()))
		} else {
			logger.Printf("own window closed")
		}
		if second {
			return
		}
		a.mu.Lock()
		if a.windowCmd == cmd {
			a.windowCmd = nil
		}
		a.windowGone = time.Now() // the window is gone for sure: exit after byeGrace, not goneGrace
		a.mu.Unlock()
	}()
	return nil
}

// closeOwnWindow closes the own window when the program exits. After «Выход» the page closes the window itself
// (ttwClose), so it gets a moment for that before the window program is stopped.
func (a *App) closeOwnWindow() {
	a.mu.Lock()
	cmd, done := a.windowCmd, a.windowDone
	a.windowCmd = nil
	a.mu.Unlock()
	if cmd == nil {
		return
	}
	select {
	case <-done:
	case <-time.After(2 * time.Second):
		terminate(cmd)
	}
}

func (a *App) windowStateJSON() map[string]any { // call under a.mu
	return map[string]any{"available": a.windowHelper() != "", "error": a.windowErr, "pages": a.ownPages}
}
