package main

import (
	"testing"
	"time"
)

// 1.4: the reports of the speech and conversation tests keep the time of their start: the page rewrites the same report
// as the test goes on (speech-test-<start>.md, talk-test-<start>.md); a stamp that is not a date and time (or tries to
// leave the folder) is replaced; another kind is the full test.
func TestReportName(t *testing.T) {
	now := time.Date(2026, 11, 24, 15, 4, 5, 0, time.Local)
	for _, c := range []struct{ kind, stamp, want string }{
		{"quick", "", "quick-test-2026-11-24_15-04-05"},
		{"full", "", "test-2026-11-24_15-04-05"},
		{"", "2026-01-01_00-00-00", "test-2026-11-24_15-04-05"},
		{"speech", "2026-11-24_14-00-00", "speech-test-2026-11-24_14-00-00"},
		{"speech", "", "speech-test-2026-11-24_15-04-05"},
		{"speech", "../../config", "speech-test-2026-11-24_15-04-05"},
		{"speech", "2026-11-24_14-00-00/../x", "speech-test-2026-11-24_15-04-05"},
		{"talk", "2026-11-25_09-30-00", "talk-test-2026-11-25_09-30-00"},
		{"talk", "..\\..\\config", "talk-test-2026-11-24_15-04-05"},
		{"other", "2026-11-25_09-30-00", "test-2026-11-24_15-04-05"},
	} {
		if got := reportName(c.kind, c.stamp, now); got != c.want {
			t.Errorf("reportName(%q, %q) = %q, want %q", c.kind, c.stamp, got, c.want)
		}
	}
}
