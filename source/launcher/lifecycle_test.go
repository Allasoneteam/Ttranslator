package main

import (
	"context"
	"io"
	"log"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

// An open event stream counts as a window until its page says it is closing (pagehide), even if the stream
// lingers; a new page (a reload) keeps the program running; a stream dropped without a goodbye waits longer.
func TestWindowsAndClosing(t *testing.T) {
	logger = log.New(io.Discard, "", 0)
	a := &App{quit: make(chan struct{})}
	open := func() int { a.mu.Lock(); defer a.mu.Unlock(); return a.openWindows() }
	streams := func(id string) int { a.mu.Lock(); defer a.mu.Unlock(); return a.pages[id] }
	last := func() bool { a.mu.Lock(); defer a.mu.Unlock(); return a.lastGoneBye }
	stream := func(id string) func() {
		ctx, cancel := context.WithCancel(context.Background())
		req := httptest.NewRequest(http.MethodGet, "/api/events?page="+id, nil).WithContext(ctx)
		done := make(chan struct{})
		go func() { a.handleEvents(httptest.NewRecorder(), req); close(done) }()
		for i := 0; i < 500 && streams(id) == 0; i++ {
			time.Sleep(2 * time.Millisecond)
		}
		return func() { cancel(); <-done }
	}
	closing := func(id string) {
		rec := httptest.NewRecorder()
		a.handleClosing(rec, httptest.NewRequest(http.MethodPost, "/api/closing?page="+id, nil))
		if rec.Code != http.StatusNoContent {
			t.Fatalf("closing %s: %d", id, rec.Code)
		}
	}

	stop1 := stream("p1")
	if open() != 1 {
		t.Fatalf("one window: %d", open())
	}
	// the window is closed: it says so first, its stream ends a moment later
	closing("p1")
	if open() != 0 || !last() {
		t.Errorf("after goodbye: open %d, bye %v", open(), last())
	}
	stop1()
	if open() != 0 || !last() || streams("p1") != 0 {
		t.Errorf("after the stream ended: open %d, bye %v", open(), last())
	}
	// a reload: the new page opens its own stream
	stop2 := stream("p2")
	if open() != 1 {
		t.Errorf("reloaded window: %d", open())
	}
	// a stream that lingers after its page said goodbye does not keep the program running
	stream("p3")
	closing("p3")
	if open() != 1 || streams("p3") != 1 {
		t.Errorf("lingering stream: open %d, streams %d", open(), streams("p3"))
	}
	// a stream that drops without a goodbye (a crash): the longer grace applies
	stop2()
	if open() != 0 || last() {
		t.Errorf("dropped stream: open %d, bye %v", open(), last())
	}
	if byeGrace >= goneGrace || byeGrace > 10*time.Second {
		t.Errorf("grace times: %v, %v", byeGrace, goneGrace)
	}
}

// The welcome window applies its start choice once per run: /api/start-done or any load or unload ends the start.
func TestStartDone(t *testing.T) {
	for _, path := range []string{"/api/start-done", "/api/unload", "/api/load", "/api/unload?at_start"} {
		a := testApp(t)
		a.cfg = defaultConfig()
		a.cfg.LoadModelAtStart = false
		a.unloaded, a.noModelAtStart = true, true
		if st := a.stateJSON(); st["start_done"] != false || st["no_model_at_start"] != true {
			t.Fatalf("at start: %v %v", st["start_done"], st["no_model_at_start"])
		}
		rec := httptest.NewRecorder()
		body := ""
		if path == "/api/unload?at_start" { // the welcome window unloads at start: still «not loaded at start»
			path, body = "/api/unload", `{"at_start":true}`
		}
		req := httptest.NewRequest(http.MethodPost, path, strings.NewReader(body))
		req.Host = "127.0.0.1:8765"
		a.routes().ServeHTTP(rec, req)
		if rec.Code != 200 {
			t.Fatalf("%s: %d %s", path, rec.Code, rec.Body.String())
		}
		if st := a.stateJSON(); st["start_done"] != true || st["unloaded"] != (path != "/api/load") {
			t.Errorf("%s %s: start_done = %v, unloaded = %v", path, body, st["start_done"], st["unloaded"])
		}
		if want := path == "/api/start-done" || body != ""; a.noModelAtStart != want {
			t.Errorf("%s: no_model_at_start = %v", path, a.noModelAtStart)
		}
	}
}
