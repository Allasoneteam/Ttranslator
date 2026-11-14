package main

// Android (1.2): the launcher is the same program as on Linux (GOOS=android builds sys_linux.go), started by the app
// (android/app/…/Launcher.java) with --no-window. What differs is here:
//   - the access key: other apps of the phone can reach 127.0.0.1 too, so the app gives the launcher a random key
//     (TDOC_ACCESS_KEY) and every request must carry it — the app's window in the cookie tdoc_key, the app itself in
//     the header X-Tdoc-Key. On computers the variable is not set and nothing changes;
//   - the port file (TDOC_PORT_FILE): the launcher writes there the port it listens on, so the app opens exactly this
//     launcher, not whatever else may listen on 127.0.0.1:8765;
//   - the model catalog by the memory of the phone (phoneCatalog), the device name for the test reports (TDOC_OS,
//     TDOC_CPU), and a clear answer instead of opening a folder (Android has no file manager to open one in).

import (
	"crypto/subtle"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strconv"
)

var isAndroid = runtime.GOOS == "android"

// accessCookie is the cookie the Android app sets in its window for 127.0.0.1 (the header is X-Tdoc-Key).
const accessCookie = "tdoc_key"

// takeAccessKey reads the access key from the environment and removes it there: the engine and the reading-aloud
// program, started later with this environment, have no use for it.
func takeAccessKey() string {
	k := os.Getenv("TDOC_ACCESS_KEY")
	os.Unsetenv("TDOC_ACCESS_KEY")
	return k
}

// accessOK: the request carries the access key (only asked when there is one, i.e. on Android).
func (a *App) accessOK(r *http.Request) bool {
	k := r.Header.Get("X-Tdoc-Key")
	if k == "" {
		if c, err := r.Cookie(accessCookie); err == nil {
			k = c.Value
		}
	}
	return k != "" && subtle.ConstantTimeCompare([]byte(k), []byte(a.accessKey)) == 1
}

// writePortFile tells the app the port of this launcher (written whole: a temporary file, then renamed).
func writePortFile(p string, port int) {
	if p == "" {
		return
	}
	tmp := p + ".tmp"
	if err := os.WriteFile(tmp, []byte(strconv.Itoa(port)+"\n"), 0o600); err == nil {
		if err := os.Rename(tmp, p); err != nil {
			logger.Printf("port file %s: %v", filepath.Base(p), err)
		}
	} else {
		logger.Printf("port file %s: %v", filepath.Base(p), err)
	}
}

// phoneRAMForE4B: E4B · Q4_0 (≈3.5 GB for the engine) is offered from 12 GB of memory. /proc/meminfo counts less
// than the phone's box says: a "12 GB" phone shows about 11 GiB, an "8 GB" one about 7.5.
const phoneRAMForE4B = 10.0

// phoneCatalog: the models a phone is offered (the author's decision of 14.11.2026): E2B · Q4_0 (≈2.6 GB) always,
// E4B · Q4_0 only from 12 GB, Q8_0 never. A file of a hidden model already in models/ shows up as an own file.
// Unknown ids (the test catalogs) stay.
func phoneCatalog(specs []ModelSpec, ramGB float64) []ModelSpec {
	var out []ModelSpec
	for _, m := range specs {
		switch m.ID {
		case "g4-e2b-q8", "g4-e4b-q8":
			continue
		case "g4-e4b":
			if ramGB < phoneRAMForE4B {
				continue
			}
		}
		out = append(out, m)
	}
	if len(out) == 0 {
		return specs
	}
	return out
}

// deviceInfo: the app knows the phone better than /proc (Android version, model, chip) — for the test reports.
func deviceInfo(m Machine) Machine {
	if v := os.Getenv("TDOC_OS"); v != "" {
		m.OS = v
	}
	if v := os.Getenv("TDOC_CPU"); v != "" {
		m.CPU = v
	}
	return m
}
