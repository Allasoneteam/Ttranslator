package main

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

// macOS (1.1): where the program keeps what — inside Ttranslator.app (read only) and in Application Support.
func TestMacDirs(t *testing.T) {
	conf := "/Users/u/Library/Application Support"
	app := "/Applications/Ttranslator.app"
	root, res, bin := macDirs(app+"/Contents/MacOS", conf, "")
	if root != conf+"/Ttranslator" || res != app+"/Contents/Resources" || bin != app+"/Contents/MacOS" {
		t.Errorf("in the app: %q %q %q", root, res, bin)
	}
	// App Translocation: macOS runs the app from a read-only copy at a random path — the data stay where they were
	tr := "/private/var/folders/x/T/AppTranslocation/0A1B/d/Ttranslator.app"
	if root, res, _ := macDirs(tr+"/Contents/MacOS", conf, ""); root != conf+"/Ttranslator" || res != tr+"/Contents/Resources" {
		t.Errorf("translocated: %q %q", root, res)
	}
	// TDOC_ROOT (tests): another data folder; the program files stay in the app
	if root, res, _ := macDirs(app+"/Contents/MacOS", conf, "/tmp/t"); root != "/tmp/t" || res != app+"/Contents/Resources" {
		t.Errorf("TDOC_ROOT: %q %q", root, res)
	}
	// a program file outside an app: the interface and the window program next to it, the data in Application Support
	if root, res, bin := macDirs("/opt/tt", conf, ""); root != conf+"/Ttranslator" || res != "/opt/tt" || bin != "/opt/tt" {
		t.Errorf("outside an app: %q %q %q", root, res, bin)
	}
	if root, _, _ := macDirs("/opt/tt", "", ""); root != "/opt/tt" {
		t.Errorf("no home folder: %q", root)
	}
	for in, want := range map[string]string{
		"/Applications/Ttranslator.app/Contents/MacOS": "/Applications/Ttranslator.app",
		"/Applications/Ttranslator.app/Contents":       "",
		"/opt/Contents/MacOS":                          "",
		"/opt/x.app/MacOS":                             "",
	} {
		if got := appBundle(in); got != want {
			t.Errorf("appBundle(%q) = %q, want %q", in, got, want)
		}
	}
}

// The engines of macOS: the official llama.cpp archives for Intel (processor) and Apple Silicon (Metal).
func TestMacEngine(t *testing.T) {
	for arch, want := range map[string]string{"amd64": "llama-" + engineVersion + "-bin-macos-x64.tar.gz", "arm64": "llama-" + engineVersion + "-bin-macos-arm64.tar.gz"} {
		pkg, err := enginePackageFor("darwin", arch)
		if err != nil || pkg.Asset != want || pkg.Server != "llama-server" || pkg.Size < 1<<20 || !hex64.MatchString(pkg.SHA256) {
			t.Errorf("darwin/%s: %+v %v", arch, pkg, err)
		}
	}
	if pkg, _ := enginePackageFor("darwin", "arm64"); !strings.Contains(pkg.Label, "Metal") {
		t.Errorf("Apple Silicon computes with Metal: %q", pkg.Label)
	}
	// hw.memsize: 8 bytes, little-endian; syscall.Sysctl drops the last byte when it is zero
	if n := sysctlUint("\x00\x00\x00\x00\x02\x00\x00"); n != 8<<30 {
		t.Errorf("8 GB: %d", n)
	}
	if n := sysctlUint("\x00\x00\x00\x00\x10"); n != 64<<30 {
		t.Errorf("64 GB: %d", n)
	}
}

// The engine inside Ttranslator.app is used first; without it — the one downloaded into the data folder, as on
// Windows and Linux.
func TestAppEngine(t *testing.T) {
	a := testApp(t)
	a.engineDir = filepath.Join(t.TempDir(), "engine", "darwin-arm64")
	a.appEngineDir = filepath.Join(t.TempDir(), "Resources", "engine", "darwin-arm64")
	a.pkg = enginePackage{Server: "llama-server"}
	put := func(dir, version string) string {
		p := filepath.Join(dir, version, "llama-"+version, "llama-server")
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(p, []byte("#!/bin/sh\n"), 0o755); err != nil {
			t.Fatal(err)
		}
		meta, _ := json.Marshal(engineMeta{Version: version, Server: version + "/llama-" + version + "/llama-server"})
		if err := os.WriteFile(filepath.Join(dir, "engine.json"), meta, 0o644); err != nil {
			t.Fatal(err)
		}
		return p
	}
	if p := a.serverPath(); p != "" {
		t.Errorf("no engine yet: %q", p)
	}
	downloaded := put(a.engineDir, "b1")
	if p := a.serverPath(); p != downloaded {
		t.Errorf("downloaded engine: %q", p)
	}
	inApp := put(a.appEngineDir, engineVersion)
	if p := a.serverPath(); p != inApp {
		t.Errorf("the engine of the app first: %q", p)
	}
	// an engine.json without its program does not count
	_ = os.RemoveAll(filepath.Dir(inApp))
	if p := a.serverPath(); p != downloaded {
		t.Errorf("the app's engine is gone: %q", p)
	}
	// engine_path in config.json is still the first choice
	a.cfg.EnginePath = inApp
	if p := a.serverPath(); p != "" {
		t.Errorf("engine_path to a missing file: %q", p)
	}
}

// «Открыть папку данных»: /api/state tells the window the data folder and the system.
func TestStateDataRoot(t *testing.T) {
	a := testApp(t)
	a.root = t.TempDir()
	a.engineDir, a.modelsDir = filepath.Join(a.root, "engine"), filepath.Join(a.root, "models")
	a.cfg = defaultConfig()
	st := a.stateJSON()
	if st["data_root"] != a.root || st["platform"] == "" {
		t.Errorf("data_root %v, platform %v", st["data_root"], st["platform"])
	}
}
