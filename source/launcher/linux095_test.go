//go:build linux

package main

import (
	"bytes"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

// unsetEnv removes a variable for one test and puts it back afterwards (t.Setenv cannot remove one).
func unsetEnv(t *testing.T, k string) {
	t.Helper()
	old, had := os.LookupEnv(k)
	_ = os.Unsetenv(k)
	t.Cleanup(func() {
		if had {
			_ = os.Setenv(k, old)
		} else {
			_ = os.Unsetenv(k)
		}
	})
}

// With the NVIDIA driver the window program gets WEBKIT_DISABLE_DMABUF_RENDERER=1 (an empty window otherwise);
// without it, or when the user has set the variable himself, the environment is the launcher's.
func TestWindowEnvNVIDIA(t *testing.T) {
	a := testApp(t)
	a.root = t.TempDir()
	a.cfg = defaultConfig()
	unsetEnv(t, "WEBKIT_DISABLE_DMABUF_RENDERER")
	old := nvidiaDriver
	t.Cleanup(func() { nvidiaDriver = old })
	nvidiaDriver = filepath.Join(a.root, "no-such-driver")
	if env := windowEnv(); env != nil {
		t.Errorf("no NVIDIA driver: %d variables", len(env))
	}
	nvidiaDriver = filepath.Join(a.root, "version")
	_ = os.WriteFile(nvidiaDriver, []byte("NVRM version: NVIDIA UNIX Open Kernel Module for x86_64  580.105.08\n"), 0o644)
	env := windowEnv()
	if len(env) == 0 || env[len(env)-1] != "WEBKIT_DISABLE_DMABUF_RENDERER=1" || len(env) != len(os.Environ())+1 {
		t.Errorf("NVIDIA driver: %v", env[max(0, len(env)-2):])
	}
	// the window program really gets it
	out := filepath.Join(a.root, "env.txt")
	fakeWindow(t, a, "echo \"dmabuf=$WEBKIT_DISABLE_DMABUF_RENDERER\" > '"+out+"'; echo ready; exec sleep 1")
	if err := a.startOwnWindow("http://127.0.0.1:8765/", true, false); err != nil {
		t.Fatal(err)
	}
	if b, _ := os.ReadFile(out); string(b) != "dmabuf=1\n" {
		t.Errorf("the window program's environment: %q", b)
	}
	// the user's own choice stays
	t.Setenv("WEBKIT_DISABLE_DMABUF_RENDERER", "0")
	if env := windowEnv(); env != nil {
		t.Errorf("set by the user: %d variables", len(env))
	}
	fakeWindow(t, a, "echo \"dmabuf=$WEBKIT_DISABLE_DMABUF_RENDERER\" > '"+out+"'; echo ready; exec sleep 1")
	if err := a.startOwnWindow("http://127.0.0.1:8765/", true, false); err != nil {
		t.Fatal(err)
	}
	if b, _ := os.ReadFile(out); string(b) != "dmabuf=0\n" {
		t.Errorf("the user's value: %q", b)
	}
}

// Programs copied without their execute permission (some cloud folders, network shares) get it back: the engine
// (engine.json), sherpa-onnx (tts.json) and the window program.
func TestExecutablePermission(t *testing.T) {
	a := testApp(t)
	a.root = t.TempDir()
	a.engineDir = filepath.Join(a.root, "engine", "linux-amd64")
	a.cfg = defaultConfig()
	a.pkg, _ = currentEnginePackage()
	server := filepath.Join(a.engineDir, "b1", "bin", a.pkg.Server)
	tts := filepath.Join(a.engineDir, "sherpa", "bin", ttsExeName())
	win := filepath.Join(a.root, windowHelperName)
	for _, p := range []string{server, tts, win} {
		_ = os.MkdirAll(filepath.Dir(p), 0o755)
		_ = os.WriteFile(p, []byte("#!/bin/sh\necho ready\n"), 0o644)
	}
	_ = os.WriteFile(filepath.Join(a.engineDir, "engine.json"), []byte(`{"version": "b1", "server": "b1/bin/`+a.pkg.Server+`"}`), 0o644)
	_ = os.WriteFile(filepath.Join(a.engineDir, "tts.json"), []byte(`{"version": "v1", "exe": "sherpa/bin/`+ttsExeName()+`"}`), 0o644)
	a.mu.Lock()
	gotServer, gotTTS := a.serverPath(), a.ttsExe()
	a.mu.Unlock()
	gotWin := a.windowHelper()
	for _, c := range []struct{ got, want string }{{gotServer, server}, {gotTTS, tts}, {gotWin, win}} {
		st, err := os.Stat(c.want)
		if c.got != c.want || err != nil || st.Mode().Perm() != 0o755 {
			t.Errorf("%s: found %q, mode %v", c.want, c.got, st.Mode())
		}
	}
}

// ./ttranslator-linux --shortcut: a desktop entry in the menu of applications and its icon; a folder name with
// spaces and $ is quoted as the Desktop Entry Specification says.
func TestShortcut(t *testing.T) {
	testApp(t)
	share := t.TempDir()
	t.Setenv("XDG_DATA_HOME", share)
	root := filepath.Join(t.TempDir(), "Мои программы", "T $1")
	exe := filepath.Join(root, "ttranslator-linux")
	p, err := makeShortcut(exe, root)
	if err != nil || p != filepath.Join(share, "applications", "ttranslator.desktop") {
		t.Fatalf("makeShortcut: %q, %v", p, err)
	}
	b, _ := os.ReadFile(p)
	s := string(b)
	icon := filepath.Join(share, "icons", "hicolor", "256x256", "apps", "ttranslator.png")
	for _, line := range []string{
		"[Desktop Entry]", "Type=Application", "Name=Ttranslator", "Terminal=false", "StartupWMClass=ttranslator",
		`Exec="` + strings.ReplaceAll(exe, "$", `\\$`) + `"`, "Path=" + root, "Icon=" + icon,
		"Comment[ru]=Локальный переводчик, работает без интернета",
	} {
		if !strings.Contains(s, "\n"+line+"\n") && !strings.HasPrefix(s, line+"\n") {
			t.Errorf("no line %q in\n%s", line, s)
		}
	}
	if png, err := os.ReadFile(icon); err != nil || !bytes.Equal(png, windowIconPNG) {
		t.Errorf("icon: %v", err)
	}
	if v, err := exec.LookPath("desktop-file-validate"); err == nil {
		if out, err := exec.Command(v, p).CombinedOutput(); err != nil || len(bytes.TrimSpace(out)) > 0 {
			t.Errorf("desktop-file-validate: %v\n%s", err, out)
		}
	}
	// again (the folder was moved): the entry is replaced
	time.Sleep(10 * time.Millisecond)
	if _, err := makeShortcut("/opt/Ttranslator/ttranslator-linux", "/opt/Ttranslator"); err != nil {
		t.Fatal(err)
	}
	if b, _ := os.ReadFile(p); !strings.Contains(string(b), "\nExec=\"/opt/Ttranslator/ttranslator-linux\"\n") || strings.Contains(string(b), "T $1") {
		t.Errorf("replaced entry:\n%s", b)
	}
	if desktopExec(`/a "b"/c\d%e`) != `"/a \\"b\\"/c\\\\d%%e"` {
		t.Errorf("desktopExec: %s", desktopExec(`/a "b"/c\d%e`))
	}
}
