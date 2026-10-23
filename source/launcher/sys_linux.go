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

// nvidiaDriver: this file is there while the NVIDIA driver (not nouveau) is loaded. A variable for the tests.
var nvidiaDriver = "/proc/driver/nvidia/version"

// windowEnv is the environment of the window program; nil: the launcher's own. With the NVIDIA driver, WebKitGTK's
// DMA-BUF renderer often shows an empty (white) window or ends on resize (WebKit bug 303811, 2025, and earlier ones);
// its older renderer works there. Not when the user has set WEBKIT_DISABLE_DMABUF_RENDERER himself (also to 0).
func windowEnv() []string {
	if _, set := os.LookupEnv("WEBKIT_DISABLE_DMABUF_RENDERER"); set {
		return nil
	}
	if _, err := os.Stat(nvidiaDriver); err != nil {
		return nil
	}
	logger.Printf("own window: NVIDIA driver, WEBKIT_DISABLE_DMABUF_RENDERER=1 (an empty window with WebKitGTK's DMA-BUF renderer)")
	return append(os.Environ(), "WEBKIT_DISABLE_DMABUF_RENDERER=1")
}

// makeShortcut (./ttranslator-linux --shortcut, 0.9.5) puts Ttranslator into the menu of applications: the desktop
// entry ~/.local/share/applications/ttranslator.desktop and its icon (the window program calls itself "ttranslator",
// so the window gets this icon in the taskbar too). GNOME Files does not start a program file by double click.
// Moving the program folder needs the shortcut again; deleting the two files removes it. Returns the entry's path.
func makeShortcut(exe, root string) (string, error) {
	share := os.Getenv("XDG_DATA_HOME")
	if share == "" {
		home, err := os.UserHomeDir()
		if err != nil {
			return "", err
		}
		share = filepath.Join(home, ".local", "share")
	}
	iconDir := filepath.Join(share, "icons", "hicolor", "256x256", "apps")
	appsDir := filepath.Join(share, "applications")
	for _, d := range []string{iconDir, appsDir} {
		if err := os.MkdirAll(d, 0o755); err != nil {
			return "", err
		}
	}
	icon := filepath.Join(iconDir, "ttranslator.png")
	if err := os.WriteFile(icon, windowIconPNG, 0o644); err != nil {
		return "", err
	}
	entry := strings.Join([]string{
		"[Desktop Entry]",
		"Type=Application",
		"Name=Ttranslator",
		"GenericName=Translator",
		"GenericName[ru]=Переводчик",
		"GenericName[de]=Übersetzer",
		"Comment=Local translator, works without the internet",
		"Comment[ru]=Локальный переводчик, работает без интернета",
		"Comment[de]=Lokaler Übersetzer, arbeitet ohne Internet",
		"Exec=" + desktopExec(exe),
		"Path=" + desktopString(root),
		"Icon=" + desktopString(icon),
		"Terminal=false",
		"Categories=Office;",
		"Keywords=translate;translator;dictionary;",
		"Keywords[ru]=перевод;переводчик;словарь;",
		"Keywords[de]=übersetzen;Übersetzer;Wörterbuch;",
		"StartupWMClass=ttranslator",
	}, "\n") + "\n"
	p := filepath.Join(appsDir, "ttranslator.desktop")
	if err := os.WriteFile(p, []byte(entry), 0o644); err != nil {
		return "", err
	}
	logger.Printf("menu shortcut: %s (program %s)", p, exe)
	return p, nil
}

// desktopString escapes a string value of a desktop entry; desktopExec quotes the program for Exec= (the quoting
// rule of the Desktop Entry Specification comes on top of the string escapes: "\\$" for a literal $).
func desktopString(s string) string {
	return strings.NewReplacer(`\`, `\\`, "\n", `\n`, "\t", `\t`, "\r", `\r`).Replace(s)
}

func desktopExec(p string) string {
	var b strings.Builder
	for _, r := range p {
		switch r {
		case '"', '`', '$', '\\':
			b.WriteByte('\\')
		}
		b.WriteRune(r)
	}
	return desktopString(`"` + strings.ReplaceAll(b.String(), "%", "%%") + `"`)
}

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
