//go:build darwin

package main

// macOS (1.1): Ttranslator.app. The launcher is Contents/MacOS/Ttranslator, the own window Contents/MacOS/
// ttranslator-window; the interface and the engine are in Contents/Resources; the data are in
// ~/Library/Application Support/Ttranslator (macos.go).

import (
	"fmt"
	"math"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
	"syscall"
)

// programDirs: the data folder, the folder of the interface and the engine of the app, the folder of the programs.
func programDirs(exeDir string) (root, res, bin string) {
	conf, _ := os.UserConfigDir() // ~/Library/Application Support
	return macDirs(exeDir, conf, os.Getenv("TDOC_ROOT"))
}

// platformInit: the files unpacked from the downloaded zip carry the quarantine mark (Archive Utility puts it on
// every file). macOS asks the user once, for Ttranslator.app; the engine and the window program are started by the
// launcher, and the mark is removed from them (from the whole app) so that macOS does not stop them one by one.
// Not possible when macOS runs the app from a read-only copy (App Translocation: the app was not moved out of the
// folder it was unpacked into) — README.txt asks to move Ttranslator.app into Applications first.
func platformInit() {
	exe, err := os.Executable()
	if err != nil {
		return
	}
	if p, err := filepath.EvalSymlinks(exe); err == nil {
		exe = p
	}
	app := appBundle(filepath.Dir(exe))
	if app == "" {
		return
	}
	if strings.Contains(app, "/AppTranslocation/") {
		logger.Printf("macOS runs the app from a read-only copy (App Translocation): %s", app)
	}
	if exec.Command("/usr/bin/xattr", "-p", quarantineAttr, exe).Run() != nil {
		return // no mark (or it was removed already)
	}
	out, err := exec.Command("/usr/bin/xattr", "-d", "-r", quarantineAttr, app).CombinedOutput()
	if err != nil {
		logger.Printf("quarantine mark not removed from %s: %v %s", app, err, lastLine(string(out)))
		return
	}
	logger.Printf("quarantine mark removed from the files of %s", app)
}

func setChildAttrs(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
}

func attachChild(cmd *exec.Cmd) {}

func terminate(cmd *exec.Cmd) {
	if cmd.Process != nil {
		_ = cmd.Process.Signal(syscall.SIGTERM)
	}
}

// engineEnv: the engine and sherpa-onnx find their libraries themselves (@rpath: next to the program, ../lib).
func engineEnv(dir string) []string { return os.Environ() }

func exitMessage(code int, err error) string {
	return fmt.Sprintf(tr("Движок неожиданно завершился (код %d). Подробности — в журнале ниже."), code)
}

// openWindow opens the program's window when the own window could not open: a Chrome or Edge window without tabs
// and address bar (maximized, if asked) or, with tab (launch_mode "tab") or when neither is installed, the default
// browser.
func openWindow(u string, tab, maximized bool) error {
	if !tab {
		home, _ := os.UserHomeDir()
		for _, app := range []string{"Google Chrome", "Microsoft Edge", "Chromium", "Brave Browser"} {
			for _, base := range []string{"/Applications", filepath.Join(home, "Applications")} {
				p := filepath.Join(base, app+".app", "Contents", "MacOS", app)
				if st, err := os.Stat(p); err != nil || st.IsDir() {
					continue
				}
				cmd := exec.Command(p, appWindowArgs(u, maximized)...)
				cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
				if err := cmd.Start(); err == nil {
					_ = cmd.Process.Release()
					return nil
				}
			}
		}
	}
	return exec.Command("/usr/bin/open", u).Start()
}

func openFolder(p string) error { return exec.Command("/usr/bin/open", p).Start() }

// The own window (window.go): Contents/MacOS/ttranslator-window. Its menu bar (Edit: copy, paste… — without it
// the keyboard shortcuts do not work in the window) is in the language of the interface; the app icon is the one of
// Ttranslator.app, the page data are kept by macOS for the app.
const windowHelperName = "ttranslator-window"

func windowArgs(data string) []string { return []string{"--lang", curLang()} }

// windowChildAttrs: the window has its own session, like a browser window (not stopped by the terminal's Ctrl+C).
func windowChildAttrs(cmd *exec.Cmd) { cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true} }

// windowEnv: the window program gets the launcher's environment.
func windowEnv() []string { return nil }

// allowForeground: nothing to do on macOS (the window program brings itself to the front).
func allowForeground(pid int) {}

// makeShortcut: a menu entry is a Linux thing (--shortcut).
func makeShortcut(exe, root string) (string, error) {
	return "", fmt.Errorf("%s", tr("На Mac ярлык не нужен: перенесите Ttranslator.app в папку «Программы», а оттуда, если хотите, — в Dock."))
}

// fatal: the message in a dialog (osascript; it closes by itself after 10 minutes) and in the log.
func fatal(msg string) {
	if logger != nil {
		logger.Print(msg)
	}
	fmt.Fprintln(os.Stderr, msg)
	_ = exec.Command("/usr/bin/osascript", "-e", "on run argv", "-e",
		`display dialog (item 1 of argv) with title "Ttranslator" buttons {"OK"} default button 1 with icon stop giving up after 600`,
		"-e", "end run", msg).Run()
	os.Exit(1)
}

func machineInfo() Machine {
	m := Machine{Threads: runtime.NumCPU(), OS: "macOS"}
	if s, err := syscall.Sysctl("machdep.cpu.brand_string"); err == nil {
		m.CPU = strings.TrimSpace(s)
	}
	if s, err := syscall.Sysctl("hw.memsize"); err == nil {
		m.RamGB = math.Round(float64(sysctlUint(s))/(1<<30)*10) / 10
	}
	if v, err := syscall.Sysctl("kern.osproductversion"); err == nil && strings.TrimSpace(v) != "" {
		m.OS = "macOS " + strings.TrimSpace(v)
	}
	return m
}
