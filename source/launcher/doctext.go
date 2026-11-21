package main

// The text of DOCX and ODT files for the document view (1.3; the author's wish of 18.11.2026 «возможно ещё DOCX / ODT»,
// «да» of 21.11.2026). Only the standard library: such a file is a zip of XML parts.
//   - The text goes by paragraphs. A table — a paragraph per row, the cells divided by « | »; a list item — its number
//     («1.», «a)», as the file numbers it) or «•»; a text box — its paragraphs after the paragraph it stands in.
//   - Footnotes and endnotes: «[n]» where they stand, their text («[n] …») at the end.
//   - Formulas (Word: OMML, LibreOffice: MathML) become LaTeX between $ — between $$ when a formula is a paragraph of
//     its own: the window keeps them out of the translation, as everywhere in the program.
//   - Pages follow the pages of the file when it knows them: Word writes where its last layout broke the pages,
//     LibreOffice — «soft page breaks»; a paragraph that a page break cuts stays whole on the earlier page.
//   - Not shown in the file — not taken: deleted text of tracked changes, hidden text, field codes, comments.
//     Headers and footers, pictures and generated tables of contents are left out too.

import (
	"archive/zip"
	"bytes"
	"encoding/xml"
	"errors"
	"fmt"
	"io"
	"net/http"
	"path"
	"strconv"
	"strings"
)

const (
	maxDocFile = 64 << 20 // the file itself, pictures inside included
	maxDocPart = 48 << 20 // one XML part when unpacked: against «zip bombs»
)

// errNotText: an ODF file, but not a text document (a spreadsheet, a presentation).
var errNotText = errors.New("not a text document")

// docTextResult: the answer of POST /api/doctext.
type docTextResult struct {
	Kind     string   `json:"kind"`     // "docx" or "odt"
	Pages    []string `json:"pages"`    // the text of the pages: paragraphs divided by a blank line
	Paged    bool     `json:"paged"`    // the pages are the pages of the file (else: all the text on one page)
	Notes    int      `json:"notes"`    // footnotes and endnotes
	Formulas int      `json:"formulas"` // formulas turned into LaTeX
}

func (a *App) docTextRoutes(mux *http.ServeMux) {
	// The body — the file itself; ?name= — its name (for the extension).
	mux.HandleFunc("/api/doctext", a.post(func(w http.ResponseWriter, r *http.Request) {
		data, err := io.ReadAll(io.LimitReader(r.Body, maxDocFile+1))
		if err != nil {
			jsonError(w, 400, tr("не удалось прочитать файл"))
			return
		}
		if len(data) > maxDocFile {
			jsonError(w, 413, tr("файл больше 64 МБ"))
			return
		}
		res, err := docText(r.URL.Query().Get("name"), data)
		if err != nil {
			jsonError(w, 400, err.Error())
			return
		}
		writeJSON(w, 200, res)
	}))
}

// docText reads a DOCX or an ODT file.
func docText(name string, data []byte) (*docTextResult, error) {
	if strings.EqualFold(path.Ext(name), ".doc") || bytes.HasPrefix(data, []byte{0xD0, 0xCF, 0x11, 0xE0}) {
		return nil, errors.New(tr("старый формат Word (.doc) не читается — сохраните файл в Word или LibreOffice как .docx или .odt"))
	}
	zr, err := zip.NewReader(bytes.NewReader(data), int64(len(data)))
	if err != nil {
		return nil, errors.New(tr("это не файл DOCX или ODT"))
	}
	files := map[string]*zip.File{}
	for _, f := range zr.File {
		files[f.Name] = f
	}
	var res *docTextResult
	switch {
	case files["content.xml"] != nil && files["word/document.xml"] == nil:
		res, err = readODT(files)
	default:
		main := docxMainPart(files)
		if main == "" {
			return nil, errors.New(tr("это не файл DOCX или ODT"))
		}
		res, err = readDOCX(files, main)
	}
	if errors.Is(err, errNotText) {
		return nil, errors.New(tr("это не файл DOCX или ODT"))
	}
	if err != nil {
		return nil, fmt.Errorf("%s: %v", tr("не удалось прочитать файл"), err)
	}
	if len(res.Pages) == 0 {
		return nil, errors.New(tr("в файле нет текста"))
	}
	return res, nil
}

// ------------------------------------------------------------------ XML as a tree

// xnode: an element with its children in their order; a text node has no name.
type xnode struct {
	space, name string
	attr        []xml.Attr
	kids        []*xnode
	text        string
}

func (n *xnode) isText() bool { return n.name == "" }

// get: an attribute by its local name.
func (n *xnode) get(local string) string {
	for _, a := range n.attr {
		if a.Name.Local == local {
			return a.Value
		}
	}
	return ""
}

func (n *xnode) child(local string) *xnode {
	for _, k := range n.kids {
		if k.name == local {
			return k
		}
	}
	return nil
}

// val: w:val, m:val… of a child element ("" if there is none).
func (n *xnode) val(local string) string {
	if c := n.child(local); c != nil {
		return c.get("val")
	}
	return ""
}

// texts: all the text inside, as it is.
func (n *xnode) texts() string {
	if n.isText() {
		return n.text
	}
	var b strings.Builder
	for _, k := range n.kids {
		b.WriteString(k.texts())
	}
	return b.String()
}

func parseXML(r io.Reader) (*xnode, error) {
	d := xml.NewDecoder(r)
	root := &xnode{name: "#root"}
	stack := []*xnode{root}
	for {
		tok, err := d.Token()
		if err == io.EOF {
			break
		}
		if err != nil {
			return nil, err
		}
		top := stack[len(stack)-1]
		switch t := tok.(type) {
		case xml.StartElement:
			n := &xnode{space: t.Name.Space, name: t.Name.Local, attr: t.Attr}
			top.kids = append(top.kids, n)
			stack = append(stack, n)
		case xml.EndElement:
			if len(stack) > 1 {
				stack = stack[:len(stack)-1]
			}
		case xml.CharData:
			top.kids = append(top.kids, &xnode{text: string(t)})
		}
	}
	return root, nil
}

// readPart: one XML part of the archive (nil, nil if there is none).
func readPart(files map[string]*zip.File, name string) (*xnode, error) {
	f := files[name]
	if f == nil {
		return nil, nil
	}
	if f.UncompressedSize64 > maxDocPart {
		return nil, fmt.Errorf("%s: too large", name)
	}
	rc, err := f.Open()
	if err != nil {
		return nil, err
	}
	defer rc.Close()
	return parseXML(io.LimitReader(rc, maxDocPart))
}

// ------------------------------------------------------------------ paragraphs and pages

// docOut gathers paragraphs into pages; while a table cell or a text box is read, into a «sink» instead.
type docOut struct {
	pages    [][]string
	cur      []string
	sinks    []*[]string
	notes    []string
	formulas int
	paged    bool
}

func (o *docOut) emit(s string) {
	s = strings.TrimSpace(s)
	if s == "" {
		return
	}
	if len(o.sinks) > 0 {
		*o.sinks[len(o.sinks)-1] = append(*o.sinks[len(o.sinks)-1], s)
		return
	}
	o.cur = append(o.cur, s)
}

func (o *docOut) pageBreak() {
	if len(o.sinks) > 0 || len(o.cur) == 0 {
		return
	}
	o.pages = append(o.pages, o.cur)
	o.cur = nil
	o.paged = true
}

// collect: what fn emits, as a list of paragraphs.
func (o *docOut) collect(fn func()) []string {
	var got []string
	o.sinks = append(o.sinks, &got)
	fn()
	o.sinks = o.sinks[:len(o.sinks)-1]
	return got
}

func (o *docOut) result(kind string) *docTextResult {
	if len(o.cur) > 0 {
		o.pages = append(o.pages, o.cur)
		o.cur = nil
	}
	if len(o.notes) > 0 && len(o.pages) > 0 {
		last := len(o.pages) - 1
		o.pages[last] = append(o.pages[last], o.notes...)
	}
	res := &docTextResult{Kind: kind, Paged: o.paged && len(o.pages) > 1, Notes: len(o.notes), Formulas: o.formulas}
	for _, p := range o.pages {
		res.Pages = append(res.Pages, strings.Join(p, "\n\n"))
	}
	return res
}

// para: what is known of the paragraph being read.
type para struct {
	b                     strings.Builder
	breakBefore, breakEnd bool     // a page break at its start, inside or at its end
	after                 []string // paragraphs of text boxes in it
	formulas, display     int
}

func (p *para) pageBreak() {
	if strings.TrimSpace(p.b.String()) == "" {
		p.breakBefore = true
	} else {
		p.breakEnd = true
	}
}

// text: the paragraph; a single formula alone in it is a displayed one ($$…$$).
func (p *para) text() string {
	s := strings.TrimSpace(p.b.String())
	if p.formulas == 1 && p.display == 0 && strings.HasPrefix(s, "$") && strings.HasSuffix(s, "$") && strings.Count(s, "$") == 2 {
		s = "$" + s + "$"
	}
	return s
}

func (o *docOut) put(prefix string, p *para) {
	if p.breakBefore {
		o.pageBreak()
	}
	if t := p.text(); t != "" {
		o.emit(prefix + t)
	}
	for _, a := range p.after {
		o.emit(a)
	}
	if p.breakEnd {
		o.pageBreak()
	}
}

// ------------------------------------------------------------------ numbering

type numLevel struct {
	format, text string // DOCX: numFmt and lvlText («%1.»); ODT: num-format and prefix/suffix in text («%1)»)
	start        int
	levels       int // ODT: text:display-levels
}

func formatNum(n int, format string) string {
	switch format {
	case "bullet":
		return "•"
	case "none", "":
		return ""
	case "decimalZero":
		return fmt.Sprintf("%02d", n)
	case "lowerLetter", "a":
		return letters(n, 'a')
	case "upperLetter", "A":
		return letters(n, 'A')
	case "lowerRoman", "i":
		return strings.ToLower(roman(n))
	case "upperRoman", "I":
		return roman(n)
	}
	return strconv.Itoa(n)
}

func letters(n int, base rune) string {
	if n < 1 {
		return ""
	}
	// a … z, aa … zz (as Word and LibreOffice count)
	return strings.Repeat(string(base+rune((n-1)%26)), (n-1)/26+1)
}

func roman(n int) string {
	if n < 1 || n > 3999 {
		return strconv.Itoa(n)
	}
	vals := []int{1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1}
	syms := []string{"M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"}
	var b strings.Builder
	for i, v := range vals {
		for n >= v {
			b.WriteString(syms[i])
			n -= v
		}
	}
	return b.String()
}

// counters: the numbers of a list, level by level (0 — not yet counted).
type counters [10]int

func (c *counters) next(lvl int, levels map[int]numLevel) {
	if lvl < 0 || lvl >= len(c) {
		return
	}
	if c[lvl] == 0 {
		c[lvl] = max(levels[lvl].start, 1)
	} else {
		c[lvl]++
	}
	for i := lvl + 1; i < len(c); i++ {
		c[i] = 0
	}
}

func (c *counters) value(lvl int, levels map[int]numLevel) int {
	if c[lvl] == 0 {
		return max(levels[lvl].start, 1)
	}
	return c[lvl]
}

// ------------------------------------------------------------------ DOCX

func isMathNS(space string) bool { return strings.HasSuffix(space, "/math") }

// docxMainPart: the main part of a Word document (word/document.xml, else as _rels/.rels says).
func docxMainPart(files map[string]*zip.File) string {
	if files["word/document.xml"] != nil {
		return "word/document.xml"
	}
	rels, _ := readPart(files, "_rels/.rels")
	if rels == nil {
		return ""
	}
	var found string
	var walk func(n *xnode)
	walk = func(n *xnode) {
		for _, k := range n.kids {
			if k.name == "Relationship" && strings.HasSuffix(k.get("Type"), "/officeDocument") {
				found = strings.TrimPrefix(k.get("Target"), "/")
			}
			walk(k)
		}
	}
	walk(rels)
	if files[found] == nil {
		return ""
	}
	return found
}

type docxReader struct {
	out      docOut
	nums     map[string]string           // numId → abstractNumId
	abstract map[string]map[int]numLevel // abstractNumId → level → numbering
	restart  map[string]map[int]int      // numId → level → startOverride
	count    map[string]*counters        // abstractNumId → numbers
	started  map[string]bool             // numIds already used (their startOverride is applied once)
	notes    map[string]map[string]*xnode
	noteNo   map[string]int
	inTable  int
}

func readDOCX(files map[string]*zip.File, main string) (*docTextResult, error) {
	doc, err := readPart(files, main)
	if err != nil {
		return nil, err
	}
	dir := path.Dir(main)
	d := &docxReader{nums: map[string]string{}, abstract: map[string]map[int]numLevel{}, restart: map[string]map[int]int{},
		count: map[string]*counters{}, started: map[string]bool{}, notes: map[string]map[string]*xnode{}, noteNo: map[string]int{}}
	if n, _ := readPart(files, path.Join(dir, "numbering.xml")); n != nil {
		d.numbering(n)
	}
	for _, kind := range []string{"footnote", "endnote"} {
		d.notes[kind] = map[string]*xnode{}
		if n, _ := readPart(files, path.Join(dir, kind+"s.xml")); n != nil {
			var walk func(x *xnode)
			walk = func(x *xnode) {
				for _, k := range x.kids {
					if k.name == kind {
						if t := k.get("type"); t == "" || t == "normal" {
							d.notes[kind][k.get("id")] = k
						}
						continue
					}
					walk(k)
				}
			}
			walk(n)
		}
	}
	d.blocks(doc)
	return d.out.result("docx"), nil
}

func (d *docxReader) numbering(root *xnode) {
	var walk func(n *xnode)
	walk = func(n *xnode) {
		for _, k := range n.kids {
			switch k.name {
			case "abstractNum":
				levels := map[int]numLevel{}
				for _, l := range k.kids {
					if l.name != "lvl" {
						continue
					}
					i, _ := strconv.Atoi(l.get("ilvl"))
					start, err := strconv.Atoi(l.val("start"))
					if err != nil {
						start = 1
					}
					levels[i] = numLevel{format: l.val("numFmt"), text: l.val("lvlText"), start: start}
				}
				d.abstract[k.get("abstractNumId")] = levels
			case "num":
				id := k.get("numId")
				d.nums[id] = k.val("abstractNumId")
				for _, o := range k.kids {
					if o.name == "lvlOverride" {
						if s, err := strconv.Atoi(o.val("startOverride")); err == nil {
							i, _ := strconv.Atoi(o.get("ilvl"))
							if d.restart[id] == nil {
								d.restart[id] = map[int]int{}
							}
							d.restart[id][i] = s
						}
					}
				}
			default:
				walk(k)
			}
		}
	}
	walk(root)
}

// number: the number of a list paragraph («1. », «a) », «• »).
func (d *docxReader) number(numPr *xnode) string {
	id := numPr.val("numId")
	if id == "" || id == "0" {
		return ""
	}
	lvl, _ := strconv.Atoi(numPr.val("ilvl"))
	abs := d.nums[id]
	levels := d.abstract[abs]
	if levels == nil {
		return "• "
	}
	c := d.count[abs]
	if c == nil {
		c = &counters{}
		d.count[abs] = c
	}
	if !d.started[id] {
		d.started[id] = true
		for i, s := range d.restart[id] {
			if i >= 0 && i < len(c) {
				c[i] = s - 1 // the next item gets s (0: the start of the level)
			}
		}
	}
	c.next(lvl, levels)
	l := levels[lvl]
	if l.format == "bullet" {
		return "• "
	}
	if l.format == "none" {
		return ""
	}
	text := l.text
	if text == "" {
		text = "%" + strconv.Itoa(lvl+1) + "."
	}
	for i := 8; i >= 0; i-- {
		key := "%" + strconv.Itoa(i+1)
		if strings.Contains(text, key) {
			text = strings.ReplaceAll(text, key, formatNum(c.value(i, levels), levels[i].format))
		}
	}
	return strings.TrimSpace(text) + " "
}

// on: a w:b, w:vanish… switched on (no w:val, or a val other than "0", "false", "off").
func on(n *xnode) bool {
	if n == nil {
		return false
	}
	switch n.get("val") {
	case "0", "false", "off", "none":
		return false
	}
	return true
}

func (d *docxReader) blocks(n *xnode) {
	for _, k := range n.kids {
		if k.isText() {
			continue
		}
		switch k.name {
		case "p":
			if isMathNS(k.space) {
				continue
			}
			prefix, p := d.paragraph(k)
			d.out.put(prefix, p)
		case "tbl":
			d.table(k)
		case "sdt":
			if c := k.child("sdtContent"); c != nil {
				d.blocks(c)
			}
		case "AlternateContent":
			if c := k.child("Choice"); c != nil {
				d.blocks(c)
			}
		case "del", "moveFrom", "sectPr", "tblPr", "tblGrid", "trPr", "tcPr", "pPr", "rPr":
			// not shown, or no text
		default:
			d.blocks(k)
		}
	}
}

func (d *docxReader) paragraph(p *xnode) (string, *para) {
	pp := &para{}
	prefix := ""
	if pPr := p.child("pPr"); pPr != nil {
		if on(pPr.child("pageBreakBefore")) {
			pp.breakBefore = true
		}
		if np := pPr.child("numPr"); np != nil {
			prefix = d.number(np)
		}
	}
	d.inline(p, pp)
	if d.inTable > 0 || len(d.out.sinks) > 0 {
		pp.breakBefore, pp.breakEnd = false, false
	}
	return prefix, pp
}

func (d *docxReader) inline(n *xnode, p *para) {
	for _, k := range n.kids {
		if k.isText() {
			continue
		}
		if isMathNS(k.space) {
			switch k.name {
			case "oMathPara":
				for _, m := range k.kids {
					if m.name == "oMath" {
						p.b.WriteString("\n$$" + omml(m) + "$$\n")
						p.formulas++
						p.display++
						d.out.formulas++
					}
				}
			case "oMath":
				p.b.WriteString("$" + omml(k) + "$")
				p.formulas++
				d.out.formulas++
			}
			continue
		}
		switch k.name {
		case "r":
			d.run(k, p)
		case "sdt":
			if c := k.child("sdtContent"); c != nil {
				d.inline(c, p)
			}
		case "AlternateContent":
			if c := k.child("Choice"); c != nil {
				d.inline(c, p)
			}
		case "del", "moveFrom", "pPr", "rPr", "commentRangeStart", "commentRangeEnd", "bookmarkStart", "bookmarkEnd", "proofErr":
		default: // w:hyperlink, w:ins, w:moveTo, w:fldSimple, w:smartTag, w:customXml, w:dir, w:bdo…
			d.inline(k, p)
		}
	}
}

func (d *docxReader) run(r *xnode, p *para) {
	symbol := false
	if rPr := r.child("rPr"); rPr != nil {
		if on(rPr.child("vanish")) || on(rPr.child("webHidden")) {
			return
		}
		if f := rPr.child("rFonts"); f != nil && (strings.EqualFold(f.get("ascii"), "Symbol") || strings.EqualFold(f.get("hAnsi"), "Symbol")) {
			symbol = true
		}
	}
	for _, k := range r.kids {
		switch k.name {
		case "t":
			s := k.texts()
			if symbol {
				s = fromSymbolFont(s)
			}
			p.b.WriteString(s)
		case "tab", "ptab":
			p.b.WriteByte('\t')
		case "br", "cr":
			switch k.get("type") {
			case "page":
				p.pageBreak()
			case "column":
				p.b.WriteByte(' ')
			default:
				p.b.WriteByte('\n')
			}
		case "lastRenderedPageBreak":
			p.pageBreak()
		case "noBreakHyphen":
			p.b.WriteByte('-')
		case "sym":
			if strings.EqualFold(k.get("font"), "Symbol") {
				if c, err := strconv.ParseUint(k.get("char"), 16, 32); err == nil {
					p.b.WriteString(fromSymbolFont(string(rune(c))))
				}
			}
		case "footnoteReference", "endnoteReference":
			p.b.WriteString(d.noteRef(strings.TrimSuffix(k.name, "Reference"), k.get("id")))
		case "drawing", "pict", "object", "AlternateContent":
			d.boxes(k, p)
		}
	}
}

// boxes: text boxes in a drawing — their paragraphs go after the paragraph (the fallback copy is skipped).
func (d *docxReader) boxes(n *xnode, p *para) {
	for _, k := range n.kids {
		if k.isText() || k.name == "Fallback" {
			continue
		}
		if k.name == "txbxContent" {
			p.after = append(p.after, d.out.collect(func() { d.blocks(k) })...)
			continue
		}
		d.boxes(k, p)
	}
}

func (d *docxReader) table(t *xnode) {
	d.inTable++
	defer func() { d.inTable-- }()
	var rows func(n *xnode)
	rows = func(n *xnode) {
		for _, tr := range n.kids {
			switch tr.name {
			case "tr":
				var cells []string
				empty := true
				for _, tc := range tr.kids {
					if tc.name == "sdt" || tc.name == "customXml" { // a cell inside a content control
						if c := tc.child("sdtContent"); c != nil {
							tc = c
						}
						if tc.child("tc") != nil {
							tc = tc.child("tc")
						}
					}
					if tc.name != "tc" {
						continue
					}
					s := strings.Join(d.out.collect(func() { d.blocks(tc) }), " ")
					if s != "" {
						empty = false
					}
					cells = append(cells, s)
				}
				if !empty {
					d.out.emit(strings.Join(cells, " | "))
				}
			case "sdt":
				if c := tr.child("sdtContent"); c != nil {
					rows(c)
				}
			case "customXml":
				rows(tr)
			}
		}
	}
	rows(t)
}

// noteRef: «[n]» for a footnote or an endnote; its text goes to the end.
func (d *docxReader) noteRef(kind, id string) string {
	key := kind + ":" + id
	if n, ok := d.noteNo[key]; ok {
		return "[" + strconv.Itoa(n) + "]"
	}
	note := d.notes[kind][id]
	if note == nil {
		return ""
	}
	n := len(d.noteNo) + 1
	d.noteNo[key] = n
	text := strings.Join(d.out.collect(func() { d.blocks(note) }), " ")
	d.out.notes = append(d.out.notes, "["+strconv.Itoa(n)+"] "+text)
	return "[" + strconv.Itoa(n) + "]"
}

// fromSymbolFont: letters and signs of the old Symbol font (Greek letters typed as Latin ones) as Unicode.
func fromSymbolFont(s string) string {
	var b strings.Builder
	for _, r := range s {
		if r >= 0xF020 && r <= 0xF0FF {
			r -= 0xF000
		}
		if m, ok := symbolFont[r]; ok {
			b.WriteRune(m)
		} else {
			b.WriteRune(r)
		}
	}
	return b.String()
}

var symbolFont = func() map[rune]rune {
	m := map[rune]rune{}
	lower := "αβχδεφγηιϕκλμνοπθρστυϖωξψζ"
	upper := "ΑΒΧΔΕΦΓΗΙϑΚΛΜΝΟΠΘΡΣΤΥςΩΞΨΖ"
	for i, r := range []rune(lower) {
		m['a'+rune(i)] = r
	}
	for i, r := range []rune(upper) {
		m['A'+rune(i)] = r
	}
	for k, v := range map[rune]rune{0xA2: '′', 0xA3: '≤', 0xA5: '∞', 0xAB: '↔', 0xAC: '←', 0xAD: '↑', 0xAE: '→', 0xAF: '↓',
		0xB0: '°', 0xB1: '±', 0xB2: '″', 0xB3: '≥', 0xB4: '×', 0xB5: '∝', 0xB6: '∂', 0xB7: '•', 0xB8: '÷', 0xB9: '≠',
		0xBA: '≡', 0xBB: '≈', 0xBC: '…', 0xC0: 'ℵ', 0xC4: '⊗', 0xC5: '⊕', 0xC6: '∅', 0xC7: '∩', 0xC8: '∪', 0xC9: '⊃',
		0xCA: '⊇', 0xCB: '⊄', 0xCC: '⊂', 0xCD: '⊆', 0xCE: '∈', 0xCF: '∉', 0xD0: '∠', 0xD1: '∇', 0xD5: '∏', 0xD6: '√',
		0xD7: '⋅', 0xD8: '¬', 0xD9: '∧', 0xDA: '∨', 0xDB: '⇔', 0xDC: '⇐', 0xDD: '⇑', 0xDE: '⇒', 0xDF: '⇓', 0xE0: '◊',
		0xE1: '⟨', 0xE5: '∑', 0xF1: '⟩', 0xF2: '∫', 0x22: '∀', 0x24: '∃', 0x27: '∋', 0x2A: '∗', 0x2D: '−', 0x40: '≅',
		0x5E: '⊥', 0x7E: '∼'} {
		m[k] = v
	}
	return m
}()

// ------------------------------------------------------------------ formulas: OMML (Word) → LaTeX

// texFuncs: names of functions written with a backslash.
var texFuncs = map[string]bool{"sin": true, "cos": true, "tan": true, "cot": true, "sec": true, "csc": true, "arcsin": true,
	"arccos": true, "arctan": true, "sinh": true, "cosh": true, "tanh": true, "coth": true, "exp": true, "log": true,
	"ln": true, "lg": true, "lim": true, "max": true, "min": true, "sup": true, "inf": true, "det": true, "dim": true,
	"ker": true, "deg": true, "gcd": true, "arg": true, "Pr": true, "liminf": true, "limsup": true}

// texEsc: characters with a meaning in LaTeX (and $, which would end the formula).
func texEsc(s string) string {
	r := strings.NewReplacer(`\`, `\backslash `, "{", `\{`, "}", `\}`, "$", `\$`, "%", `\%`, "#", `\#`, "&", `\&`)
	return r.Replace(s)
}

func texWord(s string) string {
	t := strings.TrimSpace(s)
	if texFuncs[t] {
		return `\` + t + " "
	}
	return texEsc(s)
}

var texBig = map[string]string{"∑": `\sum`, "∏": `\prod`, "∐": `\coprod`, "∫": `\int`, "∬": `\iint`, "∭": `\iiint`,
	"∮": `\oint`, "⋃": `\bigcup`, "⋂": `\bigcap`, "⋁": `\bigvee`, "⋀": `\bigwedge`, "⨁": `\bigoplus`, "⨂": `\bigotimes`}

var texAccent = map[string]string{"̀": `\grave`, "́": `\acute`, "̂": `\hat`, "̃": `\tilde`,
	"̄": `\bar`, "̅": `\bar`, "̆": `\breve`, "̇": `\dot`, "̈": `\ddot`, "̌": `\check`,
	"⃗": `\vec`, "⃖": `\vec`, "→": `\vec`, "^": `\hat`, "~": `\tilde`, "¯": `\bar`, "˙": `\dot`, "¨": `\ddot`}

var texDelim = map[string]string{"{": `\{`, "}": `\}`, "⟨": `\langle`, "⟩": `\rangle`, "〈": `\langle`, "〉": `\rangle`,
	"‖": `\|`, "⌊": `\lfloor`, "⌋": `\rfloor`, "⌈": `\lceil`, "⌉": `\rceil`}

func delim(s string) string {
	if d, ok := texDelim[s]; ok {
		return d
	}
	return s
}

// omml: the LaTeX of an OMML element (its children, in order).
func omml(n *xnode) string {
	var b strings.Builder
	for _, k := range n.kids {
		if !k.isText() {
			b.WriteString(ommlEl(k))
		}
	}
	return strings.TrimSpace(b.String())
}

// part: the LaTeX of a child (m:e, m:sub…) — "" if there is none.
func part(n *xnode, local string) string {
	if c := n.child(local); c != nil {
		return omml(c)
	}
	return ""
}

func prop(n *xnode, propName, local string) (string, bool) {
	pr := n.child(propName)
	if pr == nil {
		return "", false
	}
	c := pr.child(local)
	if c == nil {
		return "", false
	}
	return c.get("val"), true
}

func ommlEl(n *xnode) string {
	switch n.name {
	case "r":
		var b strings.Builder
		for _, k := range n.kids {
			if k.name == "t" {
				b.WriteString(k.texts())
			}
		}
		return texWord(b.String())
	case "f":
		if t, _ := prop(n, "fPr", "type"); t == "lin" {
			return part(n, "num") + "/" + part(n, "den")
		}
		return `\frac{` + part(n, "num") + "}{" + part(n, "den") + "}"
	case "sSup":
		return "{" + part(n, "e") + "}^{" + part(n, "sup") + "}"
	case "sSub":
		return "{" + part(n, "e") + "}_{" + part(n, "sub") + "}"
	case "sSubSup":
		return "{" + part(n, "e") + "}_{" + part(n, "sub") + "}^{" + part(n, "sup") + "}"
	case "sPre":
		return "{}_{" + part(n, "sub") + "}^{" + part(n, "sup") + "}{" + part(n, "e") + "}"
	case "rad":
		deg := part(n, "deg")
		if v, ok := prop(n, "radPr", "degHide"); ok && v != "0" && v != "off" && v != "false" {
			deg = ""
		}
		if deg != "" {
			return `\sqrt[` + deg + "]{" + part(n, "e") + "}"
		}
		return `\sqrt{` + part(n, "e") + "}"
	case "nary":
		chr, ok := prop(n, "naryPr", "chr")
		if !ok || chr == "" {
			chr = "∫"
		}
		op, known := texBig[chr]
		if !known {
			op = texEsc(chr)
		}
		s := op
		if v, ok := prop(n, "naryPr", "subHide"); !ok || v == "0" || v == "off" || v == "false" {
			if sub := part(n, "sub"); sub != "" {
				s += "_{" + sub + "}"
			}
		}
		if v, ok := prop(n, "naryPr", "supHide"); !ok || v == "0" || v == "off" || v == "false" {
			if sup := part(n, "sup"); sup != "" {
				s += "^{" + sup + "}"
			}
		}
		return s + "{" + part(n, "e") + "}"
	case "d":
		beg, ok := prop(n, "dPr", "begChr")
		if !ok {
			beg = "("
		}
		end, ok := prop(n, "dPr", "endChr")
		if !ok {
			end = ")"
		}
		sep, ok := prop(n, "dPr", "sepChr")
		if !ok {
			sep = "|"
		}
		var items []string
		for _, k := range n.kids {
			if k.name == "e" {
				items = append(items, omml(k))
			}
		}
		return delim(beg) + strings.Join(items, delim(sep)) + delim(end)
	case "func":
		return part(n, "fName") + "{" + part(n, "e") + "}"
	case "limLow":
		return "{" + part(n, "e") + "}_{" + part(n, "lim") + "}"
	case "limUpp":
		return "{" + part(n, "e") + "}^{" + part(n, "lim") + "}"
	case "acc":
		chr, ok := prop(n, "accPr", "chr")
		if !ok {
			chr = "̂"
		}
		a, known := texAccent[chr]
		if !known {
			a = `\hat`
		}
		return a + "{" + part(n, "e") + "}"
	case "bar":
		if pos, _ := prop(n, "barPr", "pos"); pos == "top" {
			return `\overline{` + part(n, "e") + "}"
		}
		return `\underline{` + part(n, "e") + "}"
	case "groupChr":
		chr, _ := prop(n, "groupChrPr", "chr")
		pos, _ := prop(n, "groupChrPr", "pos")
		if chr == "⏞" || pos == "top" {
			return `\overbrace{` + part(n, "e") + "}"
		}
		return `\underbrace{` + part(n, "e") + "}"
	case "m":
		var rows []string
		for _, mr := range n.kids {
			if mr.name != "mr" {
				continue
			}
			var cells []string
			for _, e := range mr.kids {
				if e.name == "e" {
					cells = append(cells, omml(e))
				}
			}
			rows = append(rows, strings.Join(cells, " & "))
		}
		return `\begin{matrix}` + strings.Join(rows, ` \\ `) + `\end{matrix}`
	case "eqArr":
		var rows []string
		for _, e := range n.kids {
			if e.name == "e" {
				rows = append(rows, omml(e))
			}
		}
		return `\begin{aligned}` + strings.Join(rows, ` \\ `) + `\end{aligned}`
	case "phant":
		if v, ok := prop(n, "phantPr", "show"); ok && (v == "0" || v == "off" || v == "false") {
			return ""
		}
		return part(n, "e")
	case "rPr", "ctrlPr", "fPr", "sSupPr", "sSubPr", "sSubSupPr", "sPrePr", "radPr", "naryPr", "dPr", "funcPr",
		"limLowPr", "limUppPr", "accPr", "barPr", "groupChrPr", "mPr", "eqArrPr", "boxPr", "borderBoxPr", "phantPr", "oMathParaPr":
		return ""
	}
	return omml(n) // m:e, m:num, m:box, m:borderBox, m:oMath…: what is inside
}

// ------------------------------------------------------------------ ODT

type odtReader struct {
	out     docOut
	files   map[string]*zip.File
	styles  map[string]map[int]numLevel // list style → level (1…) → numbering
	count   map[string]*counters        // list style → numbers
	noteNo  int
	inTable int
}

func readODT(files map[string]*zip.File) (*docTextResult, error) {
	content, err := readPart(files, "content.xml")
	if err != nil {
		return nil, err
	}
	if content == nil {
		return nil, errors.New("no content.xml")
	}
	o := &odtReader{files: files, styles: map[string]map[int]numLevel{}, count: map[string]*counters{}}
	if st, _ := readPart(files, "styles.xml"); st != nil {
		o.listStyles(st)
	}
	o.listStyles(content)
	var body *xnode
	var find func(n *xnode)
	find = func(n *xnode) {
		for _, k := range n.kids {
			if body != nil {
				return
			}
			if k.name == "text" && strings.Contains(k.space, "office") {
				body = k
				return
			}
			find(k)
		}
	}
	find(content)
	if body == nil {
		return nil, errNotText
	}
	o.blocks(body, "", 0)
	return o.out.result("odt"), nil
}

func (o *odtReader) listStyles(root *xnode) {
	var walk func(n *xnode)
	walk = func(n *xnode) {
		for _, k := range n.kids {
			if k.name == "list-style" {
				levels := map[int]numLevel{}
				for _, l := range k.kids {
					lvl, _ := strconv.Atoi(l.get("level"))
					switch l.name {
					case "list-level-style-number":
						start, err := strconv.Atoi(l.get("start-value"))
						if err != nil {
							start = 1
						}
						shown, _ := strconv.Atoi(l.get("display-levels"))
						levels[lvl] = numLevel{format: l.get("num-format"), text: l.get("num-prefix") + "%" + l.get("num-suffix"), start: start, levels: max(shown, 1)}
					case "list-level-style-bullet", "list-level-style-image":
						levels[lvl] = numLevel{format: "bullet"}
					}
				}
				o.styles[k.get("name")] = levels
				continue
			}
			walk(k)
		}
	}
	walk(root)
}

// blocks: paragraphs, headings, lists, tables, sections; style and level — of the list we are in.
func (o *odtReader) blocks(n *xnode, style string, level int) {
	for _, k := range n.kids {
		if k.isText() {
			continue
		}
		switch k.name {
		case "p", "h":
			p := &para{}
			o.inline(k, p)
			if o.inTable > 0 || len(o.out.sinks) > 0 {
				p.breakBefore, p.breakEnd = false, false
			}
			o.out.put("", p)
		case "list":
			st := k.get("style-name")
			if st == "" {
				st = style
			}
			if level == 0 && k.get("continue-numbering") != "true" && k.get("continue-list") == "" {
				o.count[st] = &counters{}
			}
			o.list(k, st, level+1)
		case "numbered-paragraph":
			o.blocks(k, k.get("style-name"), 1)
		case "table":
			o.table(k)
		case "soft-page-break":
			if o.inTable == 0 {
				o.out.pageBreak()
			}
		case "tracked-changes", "table-of-content", "alphabetical-index", "illustration-index", "table-index",
			"object-index", "user-index", "bibliography", "sequence-decls", "variable-decls", "user-field-decls",
			"dde-connection-decls", "forms", "index-title":
			// generated, or not shown
		default: // text:section, office:text, text:list-header…
			o.blocks(k, style, level)
		}
	}
}

func (o *odtReader) list(l *xnode, style string, level int) {
	levels := o.styles[style]
	c := o.count[style]
	if c == nil {
		c = &counters{}
		o.count[style] = c
	}
	for _, item := range l.kids {
		if item.name != "list-item" && item.name != "list-header" {
			continue
		}
		prefix := ""
		if item.name == "list-item" {
			if sv, err := strconv.Atoi(item.get("start-value")); err == nil && level-1 < len(c) {
				c[level-1] = sv - 1
			}
			c.next(level-1, shift(levels))
			prefix = o.number(levels, c, level)
		}
		first := true
		for _, k := range item.kids {
			if k.isText() {
				continue
			}
			switch k.name {
			case "p", "h":
				p := &para{}
				o.inline(k, p)
				if o.inTable > 0 || len(o.out.sinks) > 0 {
					p.breakBefore, p.breakEnd = false, false
				}
				if first {
					o.out.put(prefix, p)
					first = false
				} else {
					o.out.put("", p)
				}
			case "list":
				st := k.get("style-name")
				if st == "" {
					st = style
				}
				o.list(k, st, level+1)
			default:
				o.blocks(k, style, level)
			}
		}
	}
}

// shift: ODT levels count from 1, the counters — from 0.
func shift(levels map[int]numLevel) map[int]numLevel {
	m := map[int]numLevel{}
	for k, v := range levels {
		m[k-1] = v
	}
	return m
}

func (o *odtReader) number(levels map[int]numLevel, c *counters, level int) string {
	l, ok := levels[level]
	if !ok {
		return "• "
	}
	if l.format == "bullet" {
		return "• "
	}
	if l.format == "" {
		return ""
	}
	var parts []string
	for i := level - l.levels + 1; i <= level; i++ {
		if i < 1 {
			continue
		}
		parts = append(parts, formatNum(c.value(i-1, shift(levels)), levels[i].format))
	}
	return strings.TrimSpace(strings.Replace(l.text, "%", strings.Join(parts, "."), 1)) + " "
}

func (o *odtReader) table(t *xnode) {
	o.inTable++
	defer func() { o.inTable-- }()
	var rows func(n *xnode)
	rows = func(n *xnode) {
		for _, r := range n.kids {
			switch r.name {
			case "table-row":
				var cells []string
				empty := true
				for _, c := range r.kids {
					if c.name != "table-cell" {
						continue
					}
					s := strings.Join(o.out.collect(func() { o.blocks(c, "", 0) }), " ")
					if s != "" {
						empty = false
					}
					cells = append(cells, s)
				}
				if !empty {
					o.out.emit(strings.Join(cells, " | "))
				}
			case "table-header-rows", "table-rows", "table-row-group":
				rows(r)
			}
		}
	}
	rows(t)
}

// collapse: white space of ODT text — a run of spaces and line ends is one space (more spaces are text:s).
func collapse(s string) string {
	var b strings.Builder
	sp := false
	for _, r := range s {
		if r == ' ' || r == '\t' || r == '\n' || r == '\r' {
			if !sp {
				b.WriteByte(' ')
			}
			sp = true
			continue
		}
		sp = false
		b.WriteRune(r)
	}
	return b.String()
}

func (o *odtReader) inline(n *xnode, p *para) {
	for _, k := range n.kids {
		if k.isText() {
			p.b.WriteString(collapse(k.text))
			continue
		}
		switch k.name {
		case "s":
			c, err := strconv.Atoi(k.get("c"))
			if err != nil || c < 1 {
				c = 1
			}
			p.b.WriteString(strings.Repeat(" ", min(c, 100)))
		case "tab":
			p.b.WriteByte('\t')
		case "line-break":
			p.b.WriteByte('\n')
		case "soft-page-break":
			p.pageBreak()
		case "note":
			o.noteNo++
			num := strconv.Itoa(o.noteNo)
			if c := k.child("note-citation"); c != nil && strings.TrimSpace(c.texts()) != "" {
				num = strings.TrimSpace(c.texts())
			}
			if body := k.child("note-body"); body != nil {
				text := strings.Join(o.out.collect(func() { o.blocks(body, "", 0) }), " ")
				o.out.notes = append(o.out.notes, "["+num+"] "+text)
			}
			p.b.WriteString("[" + num + "]")
		case "frame":
			o.frame(k, p)
		case "ruby-text", "annotation", "annotation-end", "change", "change-start", "change-end", "bookmark",
			"bookmark-start", "bookmark-end", "reference-mark", "reference-mark-start", "reference-mark-end", "toc-mark",
			"toc-mark-start", "toc-mark-end", "alphabetical-index-mark", "alphabetical-index-mark-start",
			"alphabetical-index-mark-end", "user-index-mark", "hidden-text", "hidden-paragraph", "note-citation":
			// not shown, or no text
		default: // text:span, text:a, fields…: what is inside
			o.inline(k, p)
		}
	}
}

// frame: a text box (its paragraphs after the paragraph) or a formula object (MathML → LaTeX).
func (o *odtReader) frame(f *xnode, p *para) {
	for _, k := range f.kids {
		switch k.name {
		case "text-box":
			p.after = append(p.after, o.out.collect(func() { o.blocks(k, "", 0) })...)
		case "object":
			href := strings.TrimPrefix(strings.TrimPrefix(k.get("href"), "./"), "/")
			if href == "" {
				continue
			}
			obj, err := readPart(o.files, path.Join(href, "content.xml"))
			if err != nil || obj == nil {
				continue
			}
			var math *xnode
			var find func(n *xnode)
			find = func(n *xnode) {
				for _, c := range n.kids {
					if math != nil {
						return
					}
					if c.name == "math" {
						math = c
						return
					}
					find(c)
				}
			}
			find(obj)
			if math == nil {
				continue
			}
			if tex := mathml(math); tex != "" {
				p.b.WriteString("$" + tex + "$")
				p.formulas++
				o.out.formulas++
			}
		}
	}
}

// ------------------------------------------------------------------ formulas: MathML (LibreOffice) → LaTeX

func mathmlKids(n *xnode) []*xnode {
	var out []*xnode
	for _, k := range n.kids {
		if !k.isText() {
			out = append(out, k)
		}
	}
	return out
}

func mathml(n *xnode) string {
	var b strings.Builder
	for _, k := range mathmlKids(n) {
		b.WriteString(mathmlEl(k))
	}
	return strings.TrimSpace(b.String())
}

func mathmlEl(n *xnode) string {
	k := mathmlKids(n)
	arg := func(i int) string {
		if i < len(k) {
			return mathmlEl(k[i])
		}
		return ""
	}
	switch n.name {
	case "mi", "mn", "ms":
		return texWord(strings.TrimSpace(n.texts()))
	case "mo":
		s := strings.TrimSpace(n.texts())
		if op, ok := texBig[s]; ok {
			return op + " "
		}
		return texEsc(s)
	case "mtext":
		return `\text{` + texEsc(n.texts()) + "}"
	case "mspace":
		return " "
	case "mfrac":
		return `\frac{` + arg(0) + "}{" + arg(1) + "}"
	case "msqrt":
		return `\sqrt{` + mathml(n) + "}"
	case "mroot":
		return `\sqrt[` + arg(1) + "]{" + arg(0) + "}"
	case "msup":
		return "{" + arg(0) + "}^{" + arg(1) + "}"
	case "msub":
		return "{" + arg(0) + "}_{" + arg(1) + "}"
	case "msubsup":
		return "{" + arg(0) + "}_{" + arg(1) + "}^{" + arg(2) + "}"
	case "munder":
		return "{" + arg(0) + "}_{" + arg(1) + "}"
	case "mover":
		if len(k) == 2 && k[1].name == "mo" {
			if a, ok := texAccent[strings.TrimSpace(k[1].texts())]; ok && n.get("accent") != "false" {
				return a + "{" + arg(0) + "}"
			}
		}
		return "{" + arg(0) + "}^{" + arg(1) + "}"
	case "munderover":
		return "{" + arg(0) + "}_{" + arg(1) + "}^{" + arg(2) + "}"
	case "mfenced":
		open, close, sep := "(", ")", ","
		if v := n.get("open"); hasAttr(n, "open") {
			open = v
		}
		if v := n.get("close"); hasAttr(n, "close") {
			close = v
		}
		if v := n.get("separators"); hasAttr(n, "separators") {
			sep = strings.TrimSpace(v)
		}
		var items []string
		for _, c := range k {
			items = append(items, mathmlEl(c))
		}
		return delim(open) + strings.Join(items, delim(sep)) + delim(close)
	case "mtable":
		var rows []string
		for _, r := range k {
			var cells []string
			for _, c := range mathmlKids(r) {
				cells = append(cells, mathml(c))
			}
			rows = append(rows, strings.Join(cells, " & "))
		}
		return `\begin{matrix}` + strings.Join(rows, ` \\ `) + `\end{matrix}`
	case "semantics", "maction":
		return arg(0)
	case "annotation", "annotation-xml", "mphantom", "none", "mprescripts":
		return ""
	}
	return mathml(n) // mrow, mstyle, mpadded, menclose, merror…
}

func hasAttr(n *xnode, local string) bool {
	for _, a := range n.attr {
		if a.Name.Local == local {
			return true
		}
	}
	return false
}
