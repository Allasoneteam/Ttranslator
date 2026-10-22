package main

import (
	"testing"
	"unicode/utf16"
)

func TestGlossaryName(t *testing.T) {
	ok := map[string]string{
		"Мой словарь":     "Мой словарь.tsv",
		"physics.tsv":     "physics.tsv",
		"Laser terms.CSV": "Laser terms.CSV",
		" spaces.txt ":    "spaces.txt",
		"v1.2 (draft)":    "v1.2 (draft).tsv",
	}
	for in, want := range ok {
		got, err := glossaryName(in)
		if err != nil || got != want {
			t.Errorf("glossaryName(%q) = %q, %v; want %q", in, got, err, want)
		}
	}
	for _, in := range []string{"", "../x", "a/b", `a\b`, "..", ".hidden", "c:x", "con", "NUL.tsv", "x\x01", "name."} {
		if got, err := glossaryName(in); err == nil {
			t.Errorf("glossaryName(%q) = %q, want an error", in, got)
		}
	}
}

func TestDecodeText(t *testing.T) {
	want := "Английский\tРусский\r\nperturbation theory\tтеория возмущений"
	// UTF-8 with BOM
	if got := decodeText(append([]byte{0xEF, 0xBB, 0xBF}, want...)); got != want {
		t.Errorf("utf-8 bom: %q", got)
	}
	// UTF-16LE with BOM (Excel "Unicode text")
	u := utf16.Encode([]rune(want))
	b := []byte{0xFF, 0xFE}
	for _, c := range u {
		b = append(b, byte(c), byte(c>>8))
	}
	if got := decodeText(b); got != want {
		t.Errorf("utf-16le: %q", got)
	}
	// Windows-1251: "теория" = f2 e5 ee f0 e8 ff
	if got := decodeText([]byte{0xF2, 0xE5, 0xEE, 0xF0, 0xE8, 0xFF, '\t', 'x'}); got != "теория\tx" {
		t.Errorf("cp1251: %q", got)
	}
	// Windows-1252: "Störungstheorie" with ö = f6 among mostly ASCII letters
	if got := decodeText([]byte("St\xf6rungstheorie\tgeschlossene Form")); got != "Störungstheorie\tgeschlossene Form" {
		t.Errorf("cp1252: %q", got)
	}
}
