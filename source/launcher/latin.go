package main

// Latin read aloud by an Italian voice (author's choice, 24.10.2026). There are no Latin Piper voices, so the
// Italian voice Paola reads Latin written in Italian spelling — that is, with the church (Italian) pronunciation
// of Latin: caelum → celum [ˈtʃɛlum], gratia → grazia, excelsis → ekscelsis [ekˈʃɛlsis], habet → abet.
//
// espeak-ng (inside sherpa-onnx) turns the text into sounds with its Italian rules. They stress the last but one
// syllable, which is right for fortūna or errāre but wrong for Dominus, hominibus or veritas, and they stress the
// last syllable of words that end in a consonant (amór, mutantúr) — which Latin never does. So the stress of
// Latin is marked with a grave accent (à è ì ò ù: espeak-ng's Italian reads them as stressed, è and ò open) where
// the rules of Latin tell it reliably:
//   - two syllables: the first one (marked only if the word ends in a consonant: Italian gets the others right);
//   - more syllables: the last but one if it is long — a diphthong (ae, oe, au), a vowel before two consonants
//     (x and z count as two; p, b, t, d, c, g, f before l or r as one) or a vowel with a macron (ā); short — a
//     vowel before a vowel (glória, sapiéntia, lúceat) or with a breve (ă) — moves the stress one syllable back;
//   - endings with a short vowel: -ibus, -icus, -imus, -ulus (in all their forms), -itas, -ietas
//     (homínibus, pública, plúrimae, pópulus, véritas, píetas);
//   - a short list of frequent words: Dominus, spiritus, tempora, facere… (and Maria, diei, illius… the other way);
//   - otherwise: the last but one syllable is marked if the word ends in a consonant (sanctificétur), else nothing.
// A word that already has a stress mark (liturgical texts: Dóminus) keeps it. Macrons and breves are only read
// for the stress and then dropped.

import (
	"strings"
	"unicode"
)

type latLetter struct {
	c     rune // lowercase letter without marks, a…z
	upper bool
	long  bool // macron: ā
	short bool // breve: ă
	acc   bool // the stress: an accent in the text, or marked here
	sep   bool // diaeresis: ë is a vowel of its own (poëta, aër), not part of a diphthong
}

// vowels with marks → the letter and the mark: L macron, S breve, A accent (acute, grave, circumflex), D diaeresis
var latinMarked = map[rune][2]rune{
	'ā': {'a', 'L'}, 'ē': {'e', 'L'}, 'ī': {'i', 'L'}, 'ō': {'o', 'L'}, 'ū': {'u', 'L'}, 'ȳ': {'y', 'L'},
	'ă': {'a', 'S'}, 'ĕ': {'e', 'S'}, 'ĭ': {'i', 'S'}, 'ŏ': {'o', 'S'}, 'ŭ': {'u', 'S'},
	'á': {'a', 'A'}, 'é': {'e', 'A'}, 'í': {'i', 'A'}, 'ó': {'o', 'A'}, 'ú': {'u', 'A'}, 'ý': {'y', 'A'},
	'à': {'a', 'A'}, 'è': {'e', 'A'}, 'ì': {'i', 'A'}, 'ò': {'o', 'A'}, 'ù': {'u', 'A'},
	'â': {'a', 'A'}, 'ê': {'e', 'A'}, 'î': {'i', 'A'}, 'ô': {'o', 'A'}, 'û': {'u', 'A'},
	'ä': {'a', 'D'}, 'ë': {'e', 'D'}, 'ï': {'i', 'D'}, 'ö': {'o', 'D'}, 'ü': {'u', 'D'}, 'ÿ': {'y', 'D'},
}

var latinGrave = map[rune]rune{'a': 'à', 'e': 'è', 'i': 'ì', 'o': 'ò', 'u': 'ù'}

// frequent words whose stress the rules would put on the wrong syllable
var latinStressBack = map[string]bool{ // a short last but one syllable: the stress is one syllable further back
	"dominus": true, "domine": true, "domini": true, "dominum": true, "domino": true, "dominos": true, "dominis": true,
	"spiritus": true, "spiritu": true, "spiritui": true, "spiritum": true,
	"angelus": true, "angeli": true, "angelos": true, "angelis": true, "angelum": true,
	"femina": true, "feminam": true, "feminae": true, "homines": true, "hominem": true, "hominum": true,
	"virginis": true, "virginem": true, "virgine": true, "nomine": true, "nomina": true, "nominis": true,
	"tempora": true, "corpora": true, "corpore": true, "corporis": true, "opera": true, "opere": true, "operis": true,
	"genera": true, "genere": true, "generis": true, "libera": true, "liberi": true, "liberos": true, "miseri": true,
	"omnipotens": true, "unigenitus": true, "unigenitum": true, "unigenite": true, "genitum": true,
	"facere": true, "dicere": true, "legere": true, "vivere": true, "credere": true, "scribere": true, "mittere": true,
	"ponere": true, "quaerere": true, "agere": true, "regere": true, "accipere": true, "cogere": true,
	"nihilo": true, "nihilum": true, "aliquis": true, "aliquid": true, "aliqua": true, "aliquem": true,
}
var latinStressPenult = map[string]bool{ // a long vowel before a vowel: the last but one syllable after all
	"maria": true, "mariae": true, "mariam": true, "diei": true,
	"illius": true, "unius": true, "totius": true, "ipsius": true, "alterius": true, "nullius": true, "solius": true, "utrius": true,
}
var latinShortEndings = []string{"ibus",
	"icus", "icum", "ica", "ici", "icae", "icis", "icam", "icos", "icas", "ico",
	"imus", "imum", "ima", "imi", "imae", "imis", "imam", "imos", "imas", "imo", "ime",
	"ulus", "ulum", "ula", "uli", "ulae", "ulis", "ulam", "ulos", "ulas", "ulo",
	"itas", "ietas"}
var latinDiphthongWords = map[string]bool{"heu": true, "eheu": true, "seu": true, "neu": true, "ceu": true, "cui": true, "huic": true}

func latinVowel(c rune) bool {
	return c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u' || c == 'y'
}

// two vowels, not a diphthong: poeta, poema, aer, and the Hebrew names
func latinHiatusWord(w string) bool {
	switch w {
	case "israel", "michael", "raphael", "ismael", "gabrielis":
		return true
	}
	return strings.HasPrefix(w, "poet") || strings.HasPrefix(w, "poem") || strings.HasPrefix(w, "aer")
}

type latNucleus struct {
	start, end int
	diph       bool
}

// latinNuclei finds the vowels of the syllables (a diphthong is one); i before a vowel at the start of a word or
// between vowels is a consonant (iam, eius), and so is u in qu and ngu before a vowel (quae, lingua).
func latinNuclei(L []latLetter, w string) []latNucleus {
	var out []latNucleus
	n := len(L)
	for i := 0; i < n; i++ {
		c := L[i].c
		if !latinVowel(c) {
			continue
		}
		nextVowel := i+1 < n && latinVowel(L[i+1].c)
		if c == 'i' && !L[i].sep && nextVowel && (i == 0 || latinVowel(L[i-1].c)) {
			continue
		}
		if c == 'u' && nextVowel && i > 0 && (L[i-1].c == 'q' || (i > 1 && L[i-2].c == 'n' && L[i-1].c == 'g')) {
			continue
		}
		if i+1 < n && !L[i+1].sep && !latinHiatusWord(w) {
			d := L[i+1].c
			if (c == 'a' && (d == 'e' || d == 'u')) || (c == 'o' && d == 'e') || (latinDiphthongWords[w] && latinVowel(d)) {
				out = append(out, latNucleus{i, i + 2, true})
				i++
				continue
			}
		}
		out = append(out, latNucleus{i, i + 1, false})
	}
	return out
}

// latinConsonants counts the consonants between two vowels for the length of a syllable: h does not count, x and
// z count as two, qu and gu as one, a stop or f before l or r just before the vowel (patrem, tenebrae) as one.
func latinConsonants(L []latLetter, a, b int) int {
	var cs []rune
	for k := a; k < b; k++ {
		c := L[k].c
		if c == 'h' || (c == 'u' && k > a && (L[k-1].c == 'q' || L[k-1].c == 'g')) {
			continue
		}
		cs = append(cs, c)
	}
	n := 0
	for k := 0; k < len(cs); k++ {
		c := cs[k]
		switch {
		case c == 'x' || c == 'z':
			n += 2
		case k+2 == len(cs) && strings.ContainsRune("pbtdcgf", c) && (cs[k+1] == 'l' || cs[k+1] == 'r'):
			n++
			k++
		default:
			n++
		}
	}
	return n
}

// latinStress returns the syllable (index into the nuclei) that carries the stress, or -1 to leave it to the
// Italian rules.
func latinStress(L []latLetter, nu []latNucleus, w string) int {
	n := len(nu)
	last := L[len(L)-1].c
	endsInConsonant := !latinVowel(last)
	switch {
	case n < 2:
		return -1
	case n == 2:
		if endsInConsonant {
			return 0
		}
		return -1
	}
	p, q := n-2, n-3
	pen := nu[p]
	switch {
	case latinStressBack[w]:
		return q
	case latinStressPenult[w]:
		return p
	case L[pen.start].long:
		return p
	case L[pen.start].short:
		return q
	case pen.diph:
		return p
	}
	a, b := pen.end, nu[p+1].start
	gap := true // only h between the two vowels: a vowel before a vowel
	for k := a; k < b; k++ {
		if L[k].c != 'h' {
			gap = false
		}
	}
	if gap {
		return q
	}
	if latinConsonants(L, a, b) >= 2 {
		return p
	}
	for _, e := range latinShortEndings {
		if strings.HasSuffix(w, e) {
			return q
		}
	}
	if endsInConsonant {
		return p
	}
	return -1
}

// latinParse splits a word into letters; ok is false if it has letters that are not Latin.
func latinParse(word []rune) ([]latLetter, bool) {
	var L []latLetter
	for _, r := range word {
		lo := unicode.ToLower(r)
		up := lo != r
		switch {
		case lo >= 'a' && lo <= 'z':
			L = append(L, latLetter{c: lo, upper: up})
		case lo == 'æ' || lo == 'œ':
			first := 'a'
			if lo == 'œ' {
				first = 'o'
			}
			L = append(L, latLetter{c: first, upper: up}, latLetter{c: 'e'})
		default:
			m, ok := latinMarked[lo]
			if !ok {
				return nil, false
			}
			l := latLetter{c: m[0], upper: up}
			switch m[1] {
			case 'L':
				l.long = true
			case 'S':
				l.short = true
			case 'A':
				l.acc = true
			case 'D':
				l.sep = true
			}
			L = append(L, l)
		}
	}
	return L, len(L) > 0
}

func latinWord(word []rune) []rune {
	L, ok := latinParse(word)
	if !ok {
		return word
	}
	var b strings.Builder
	for _, l := range L {
		b.WriteRune(l.c)
	}
	w := b.String()
	// mihi, nihil: the church pronunciation says michi, nichil
	if w == "mihi" || strings.HasPrefix(w, "nihil") {
		L = append(L[:2], append([]latLetter{{c: 'c', upper: L[2].upper && L[1].upper}}, L[2:]...)...)
	}
	marked := false
	for _, l := range L {
		marked = marked || l.acc
	}
	if !marked {
		nu := latinNuclei(L, w)
		if k := latinStress(L, nu, w); k >= 0 {
			L[nu[k].start].acc = true
		}
	}
	hiatus := latinHiatusWord(w)
	front := func(k int) bool { // e, i, y — or ae, oe — at k
		if k >= len(L) {
			return false
		}
		c := L[k].c
		return c == 'e' || c == 'i' || c == 'y' || ((c == 'a' || c == 'o') && k+1 < len(L) && L[k+1].c == 'e' && !L[k+1].sep)
	}
	var out []latLetter
	for i := 0; i < len(L); i++ {
		l := L[i]
		var next latLetter
		if i+1 < len(L) {
			next = L[i+1]
		}
		switch {
		case (l.c == 'a' || l.c == 'o') && next.c == 'e' && !next.sep && !hiatus: // ae, oe → e
			out = append(out, latLetter{c: 'e', upper: l.upper, acc: l.acc || next.acc})
			i++
		case (l.c == 'p' || l.c == 't' || l.c == 'r') && next.c == 'h': // ph → f, th → t, rh → r
			c := l.c
			if c == 'p' {
				c = 'f'
			}
			out = append(out, latLetter{c: c, upper: l.upper})
			i++
		case l.c == 'h' && (i == 0 || L[i-1].c != 'c'): // h is silent (ch stays: [k])
			if l.upper && i+1 < len(L) {
				L[i+1].upper = true
			}
		case l.c == 'y' || l.c == 'j':
			l.c = 'i'
			out = append(out, l)
		case l.c == 't' && next.c == 'i' && !next.acc && i > 0 && !strings.ContainsRune("stx", L[i-1].c) && i+2 < len(L) && latinVowel(L[i+2].c):
			l.c = 'z' // gratia → grazia, but not in hostia, mixtio, Attius
			out = append(out, l)
		case l.c == 'x' && next.c == 'c' && front(i+2): // excelsis → ekscelsis
			out = append(out, latLetter{c: 'k', upper: l.upper}, latLetter{c: 's', upper: l.upper && next.upper})
		default:
			out = append(out, latLetter{c: l.c, upper: l.upper, acc: l.acc})
		}
	}
	res := make([]rune, 0, len(out))
	for _, l := range out {
		r := l.c
		if l.acc {
			if g, ok := latinGrave[r]; ok {
				r = g
			}
		}
		if l.upper {
			r = unicode.ToUpper(r)
		}
		res = append(res, r)
	}
	return res
}

// respellLatinChurch writes a Latin text in Italian spelling with the stress marked (see above); other words
// (not in Latin letters) and everything between words stay as they are.
func respellLatinChurch(s string) string {
	rs := []rune(s)
	var b strings.Builder
	for i := 0; i < len(rs); {
		if !unicode.IsLetter(rs[i]) {
			b.WriteRune(rs[i])
			i++
			continue
		}
		j := i
		for j < len(rs) && unicode.IsLetter(rs[j]) {
			j++
		}
		b.WriteString(string(latinWord(rs[i:j])))
		i = j
	}
	return b.String()
}
