package main

import (
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

// macOS (1.1), on a Mac (GitHub Actions: source/ci/macos.sh): the computer for the test reports, the folders,
// the arguments of the window program.
func TestMachineInfoMac(t *testing.T) {
	m := machineInfo()
	if m.CPU == "" || m.RamGB < 1 || m.Threads < 1 || !regexp.MustCompile(`^macOS \d+\.\d+`).MatchString(m.OS) {
		t.Errorf("%+v", m)
	}
}

func TestProgramDirsMac(t *testing.T) {
	t.Setenv("TDOC_ROOT", "")
	home, err := os.UserHomeDir()
	if err != nil {
		t.Skip(err)
	}
	root, res, bin := programDirs("/Applications/Ttranslator.app/Contents/MacOS")
	if root != filepath.Join(home, "Library", "Application Support", "Ttranslator") ||
		res != "/Applications/Ttranslator.app/Contents/Resources" || bin != "/Applications/Ttranslator.app/Contents/MacOS" {
		t.Errorf("%q %q %q", root, res, bin)
	}
	t.Setenv("TDOC_ROOT", "/tmp/tt")
	if root, _, _ := programDirs("/Applications/Ttranslator.app/Contents/MacOS"); root != "/tmp/tt" {
		t.Errorf("TDOC_ROOT: %q", root)
	}
}

func TestWindowArgsMac(t *testing.T) {
	defer setUILang("ru")
	setUILang("de")
	if got := strings.Join(windowArgs("/x/data/webview"), " "); got != "--lang de" {
		t.Errorf("window arguments: %q", got)
	}
	if windowHelperName != "ttranslator-window" || windowEnv() != nil {
		t.Errorf("window program %q", windowHelperName)
	}
	if _, err := makeShortcut("/Applications/Ttranslator.app/Contents/MacOS/Ttranslator", "/x"); err == nil || !strings.Contains(err.Error(), "Ttranslator.app") {
		t.Errorf("--shortcut on a Mac: %v", err)
	}
}
