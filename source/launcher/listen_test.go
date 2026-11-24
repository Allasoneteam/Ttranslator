package main

import (
	"testing"
	"time"
)

// 1.4: the report of the speech test keeps the time of its start: the page rewrites the same report after each
// language (speech-test-<start>.md); a stamp that is not a date and time (or tries to leave the folder) is replaced.
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
	} {
		if got := reportName(c.kind, c.stamp, now); got != c.want {
			t.Errorf("reportName(%q, %q) = %q, want %q", c.kind, c.stamp, got, c.want)
		}
	}
}
