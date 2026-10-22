package main

import (
	"encoding/json"
	"os"
	"strings"
	"testing"
)

// The engine archives of the release archives (source/release.sh): Windows and Linux, pinned size and checksum.
// TDOC_DUMP_RELEASE=<file>: also writes the version and those archives as JSON for source/release.sh.
func TestDumpReleaseInfo(t *testing.T) {
	engines := map[string]any{}
	for _, p := range []string{"windows/amd64", "linux/amd64"} {
		goos, goarch, _ := strings.Cut(p, "/")
		pkg, err := enginePackageFor(goos, goarch)
		if err != nil || !strings.Contains(pkg.Asset, engineVersion) || pkg.Size < 1<<20 || !hex64.MatchString(pkg.SHA256) || pkg.Server == "" {
			t.Fatalf("%s: %+v %v", p, pkg, err)
		}
		engines[goos+"-"+goarch] = map[string]any{"asset": pkg.Asset, "url": engineRelease + pkg.Asset, "size": pkg.Size,
			"sha256": pkg.SHA256, "server": pkg.Server}
	}
	if _, err := enginePackageFor("plan9", "386"); err == nil {
		t.Error("an unsupported platform has an engine")
	}
	out := os.Getenv("TDOC_DUMP_RELEASE")
	if out == "" {
		return
	}
	b, err := json.MarshalIndent(map[string]any{"version": appVersion, "engine_version": engineVersion, "engines": engines}, "", "  ")
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(out, b, 0o644); err != nil {
		t.Fatal(err)
	}
}
