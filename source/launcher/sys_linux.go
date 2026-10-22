//go:build linux

package main

import (
	"bufio"
	"bytes"
	_ "embed"
	"fmt"
	"math"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"syscall"
)

func platformInit() {}

func setChildAttrs(cmd *exec.Cmd) {
	cmd.SysProcAttr = &syscall.SysProcAttr{Setpgid: true}
}

func attachChild(cmd *exec.Cmd) {}

func terminate(cmd *exec.Cmd) {
	if cmd.Process != nil {
		_ = cmd.Process.Signal(syscall.SIGTERM)
	}
}

func engineEnv(dir string) []string {
	lp := dir + string(os.PathListSeparator) + filepath.Join(dir, "..", "lib")
	if old := os.Getenv("LD_LIBRARY_PATH"); old != "" {
		lp += string(os.PathListSeparator) + old
	}
	env := []string{}
	for _, e := range os.Environ() {
		if !strings.HasPrefix(e, "LD_LIBRARY_PATH=") {
			env = append(env, e)
		}
	}
	return append(env, "LD_LIBRARY_PATH="+lp)
}

func exitMessage(code int, err error) string {
	if code == 127 {
		return tr("Движок не нашёл нужные системные библиотеки. Подробности — в журнале ниже. Можно собрать llama.cpp самостоятельно и указать путь к llama-server в config.json (engine_path).")
	}
	return fmt.Sprintf(tr("Движок неожиданно завершился (код %d). Подробности — в журнале ниже. Если в журнале упоминается GLIBC, соберите llama.cpp самостоятельно и укажите путь к llama-server в config.json (engine_path)."), code)
}

// openWindow opens the program's window: a Chrome-like window without tabs and address bar (maximized, if asked) or,
// with tab (launch_mode "tab") or when no such browser is installed, the default browser (xdg-open).
func openWindow(u string, tab, maximized bool) error {
	for _, b := range []string{"google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "microsoft-edge", "microsoft-edge-stable", "brave-browser"} {
		if tab {
			break
		}
		if p, err := exec.LookPath(b); err == nil {
			cmd := exec.Command(p, appWindowArgs(u, maximized)...)
			cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
			if err := cmd.Start(); err == nil {
				_ = cmd.Process.Release()
				return nil
			}
		}
	}
	cmd := exec.Command("xdg-open", u)
	cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true}
	return cmd.Start()
}

func openFolder(p string) error { return exec.Command("xdg-open", p).Start() }

// The own window (window.go): the program ttranslator-window-linux next to ttranslator-linux.
const windowHelperName = "ttranslator-window-linux"

//go:embed Ttranslator.png
var windowIconPNG []byte

// windowArgs: the icon of the window, written into the window's data folder.
func windowArgs(data string) []string {
	p := filepath.Join(data, "ttranslator.png")
	if b, err := os.ReadFile(p); err != nil || !bytes.Equal(b, windowIconPNG) {
		if err := os.WriteFile(p, windowIconPNG, 0o644); err != nil {
			return nil
		}
	}
	return []string{"--icon", p}
}

// windowChildAttrs: the window has its own session, like a browser window (not stopped by the terminal's Ctrl+C).
func windowChildAttrs(cmd *exec.Cmd) { cmd.SysProcAttr = &syscall.SysProcAttr{Setsid: true} }

// allowForeground: nothing to do on Linux (the window program presents its window itself).
func allowForeground(pid int) {}

func fatal(msg string) {
	if logger != nil {
		logger.Print(msg)
	}
	fmt.Fprintln(os.Stderr, msg)
	os.Exit(1)
}

func machineInfo() Machine {
	m := Machine{Threads: runtime.NumCPU()}
	if f, err := os.Open("/proc/cpuinfo"); err == nil {
		sc := bufio.NewScanner(f)
		for sc.Scan() {
			if k, v, ok := strings.Cut(sc.Text(), ":"); ok && strings.TrimSpace(k) == "model name" {
				m.CPU = strings.TrimSpace(v)
				break
			}
		}
		f.Close()
	}
	if f, err := os.Open("/proc/meminfo"); err == nil {
		sc := bufio.NewScanner(f)
		for sc.Scan() {
			fs := strings.Fields(sc.Text())
			if len(fs) >= 2 && fs[0] == "MemTotal:" {
				kb, _ := strconv.ParseFloat(fs[1], 64)
				m.RamGB = math.Round(kb/(1<<20)*10) / 10
				break
			}
		}
		f.Close()
	}
	m.OS = "Linux"
	if b, err := os.ReadFile("/etc/os-release"); err == nil {
		for _, line := range strings.Split(string(b), "\n") {
			if v, ok := strings.CutPrefix(line, "PRETTY_NAME="); ok {
				m.OS = strings.Trim(v, `"`)
			}
		}
	}
	return m
}
