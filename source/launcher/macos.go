package main

// macOS (1.1), the parts that do not need macOS itself — so that the tests check them on any system.

import (
	"path/filepath"
	"strings"
)

// The mark macOS puts on downloaded files (and Archive Utility on every file unpacked from them).
const quarantineAttr = "com.apple.quarantine"

// appBundle: the folder X.app when the program runs from X.app/Contents/MacOS, else "".
func appBundle(exeDir string) string {
	contents := filepath.Dir(exeDir)
	app := filepath.Dir(contents)
	if filepath.Base(exeDir) != "MacOS" || filepath.Base(contents) != "Contents" || !strings.HasSuffix(app, ".app") {
		return ""
	}
	return app
}

// macDirs: where the program on macOS keeps what. Inside Ttranslator.app — read only (an app without a developer
// signature is often run by macOS from a read-only copy of it) — the programs are in Contents/MacOS (bin: the
// launcher and the window program), the interface and the engine of the archive in Contents/Resources (res: ui/,
// engine/darwin-<arch>). The data — config.json, data/, models/ and engine/ for what is downloaded later (sherpa-onnx,
// or the engine when the app has none) — are in ~/Library/Application Support/Ttranslator (root; author's decision
// of 22.10.2026); tdocRoot (TDOC_ROOT): another data folder (tests). Outside an app (a program file in a folder) the
// interface and the window program are next to the launcher.
func macDirs(exeDir, configDir, tdocRoot string) (root, res, bin string) {
	res, bin = exeDir, exeDir
	if app := appBundle(exeDir); app != "" {
		res = filepath.Join(app, "Contents", "Resources")
	}
	switch {
	case tdocRoot != "":
		root = tdocRoot
	case configDir != "":
		root = filepath.Join(configDir, "Ttranslator")
	default:
		root = exeDir
	}
	return root, res, bin
}

// sysctlUint: a number from sysctl (hw.memsize: 8 bytes, little-endian; syscall.Sysctl drops a last zero byte).
func sysctlUint(s string) uint64 {
	var n uint64
	for i := len(s) - 1; i >= 0; i-- {
		n = n<<8 | uint64(s[i])
	}
	return n
}
