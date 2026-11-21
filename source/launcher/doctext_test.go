package main

import (
	"archive/zip"
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// zipOf: an archive with these parts (in this order: the mimetype of ODT goes first).
func zipOf(t *testing.T, parts ...string) []byte {
	t.Helper()
	var buf bytes.Buffer
	z := zip.NewWriter(&buf)
	for i := 0; i+1 < len(parts); i += 2 {
		w, err := z.Create(parts[i])
		if err != nil {
			t.Fatal(err)
		}
		if _, err := w.Write([]byte(parts[i+1])); err != nil {
			t.Fatal(err)
		}
	}
	if err := z.Close(); err != nil {
		t.Fatal(err)
	}
	return buf.Bytes()
}

const wNS = `xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math" ` +
	`xmlns:mc="http://schemas.openxmlformats.org/markup-compatibility/2006" xmlns:wps="http://schemas.microsoft.com/office/word/2010/wordprocessingShape"`

func testDOCX(t *testing.T) []byte {
	doc := `<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document ` + wNS + `><w:body>` +
		`<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Заголовок</w:t></w:r></w:p>` +
		`<w:p><w:r><w:t xml:space="preserve">Первый </w:t></w:r><w:r><w:rPr><w:b/></w:rPr><w:t>абзац</w:t></w:r>` +
		`<w:r><w:t xml:space="preserve"> с формулой </w:t></w:r><m:oMath><m:sSup><m:e><m:r><m:t>E</m:t></m:r></m:e><m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSup></m:oMath>` +
		`<w:r><w:t>.</w:t></w:r><w:r><w:footnoteReference w:id="2"/></w:r></w:p>` +
		`<w:p><m:oMathPara><m:oMath><m:f><m:num><m:r><m:t>a</m:t></m:r></m:num><m:den><m:rad><m:radPr><m:degHide m:val="1"/></m:radPr><m:deg/>` +
		`<m:e><m:r><m:t>b</m:t></m:r></m:e></m:rad></m:den></m:f><m:r><m:t>=</m:t></m:r><m:nary><m:naryPr><m:chr m:val="∑"/></m:naryPr>` +
		`<m:sub><m:r><m:t>i=1</m:t></m:r></m:sub><m:sup><m:r><m:t>n</m:t></m:r></m:sup><m:e><m:r><m:t>i</m:t></m:r></m:e></m:nary>` +
		`<m:func><m:fName><m:r><m:t>sin</m:t></m:r></m:fName><m:e><m:r><m:t>x</m:t></m:r></m:e></m:func></m:oMath></m:oMathPara></w:p>` +
		`<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr><w:r><w:t>Пункт один</w:t></w:r></w:p>` +
		`<w:p><w:pPr><w:numPr><w:ilvl w:val="1"/><w:numId w:val="1"/></w:numPr></w:pPr><w:r><w:t>Подпункт</w:t></w:r></w:p>` +
		`<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr></w:pPr><w:r><w:t>Пункт два</w:t></w:r></w:p>` +
		`<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/><w:numId w:val="2"/></w:numPr></w:pPr><w:r><w:t>Точка</w:t></w:r></w:p>` +
		`<w:tbl><w:tr><w:tc><w:p><w:r><w:t>A1</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>B1</w:t></w:r></w:p></w:tc></w:tr>` +
		`<w:tr><w:tc><w:p/></w:tc><w:tc><w:p/></w:tc></w:tr>` +
		`<w:tr><w:tc><w:p><w:r><w:t>A3</w:t></w:r></w:p></w:tc><w:tc><w:p><w:r><w:t>B3</w:t></w:r></w:p><w:p><w:r><w:lastRenderedPageBreak/><w:t>ещё</w:t></w:r></w:p></w:tc></w:tr></w:tbl>` +
		`<w:p><w:r><w:t xml:space="preserve">Правка: </w:t></w:r><w:del><w:r><w:delText>старое</w:delText></w:r></w:del><w:ins><w:r><w:t>новое</w:t></w:r></w:ins>` +
		`<w:r><w:rPr><w:vanish/></w:rPr><w:t>скрытое</w:t></w:r><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText> PAGE </w:instrText></w:r>` +
		`<w:r><w:rPr><w:rFonts w:ascii="Symbol" w:hAnsi="Symbol"/></w:rPr><w:t xml:space="preserve"> a</w:t></w:r><w:r><w:sym w:font="Symbol" w:char="F062"/></w:r>` +
		`<w:hyperlink><w:r><w:t xml:space="preserve"> ссылка</w:t></w:r></w:hyperlink></w:p>` +
		`<w:p><w:r><w:t>Рядом рамка:</w:t></w:r><w:r><mc:AlternateContent><mc:Choice Requires="wps"><w:drawing><wps:wsp><wps:txbx><w:txbxContent>` +
		`<w:p><w:r><w:t>В рамке</w:t></w:r></w:p></w:txbxContent></wps:txbx></wps:wsp></w:drawing></mc:Choice>` +
		`<mc:Fallback><w:pict><w:txbxContent><w:p><w:r><w:t>В рамке</w:t></w:r></w:p></w:txbxContent></w:pict></mc:Fallback></mc:AlternateContent></w:r></w:p>` +
		`<w:p><w:r><w:t xml:space="preserve">Конец первой страницы, </w:t></w:r><w:r><w:lastRenderedPageBreak/><w:t>продолжение абзаца.</w:t></w:r></w:p>` +
		`<w:p><w:r><w:t>Вторая страница.</w:t></w:r></w:p>` +
		`<w:p><w:r><w:br w:type="page"/><w:t>Третья страница.</w:t></w:r><w:r><w:br/><w:t>Строка 2.</w:t></w:r></w:p>` +
		`<w:sectPr/></w:body></w:document>`
	numbering := `<w:numbering ` + wNS + `>` +
		`<w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/></w:lvl>` +
		`<w:lvl w:ilvl="1"><w:start w:val="1"/><w:numFmt w:val="lowerLetter"/><w:lvlText w:val="%2)"/></w:lvl></w:abstractNum>` +
		`<w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/><w:lvlText w:val=""/></w:lvl></w:abstractNum>` +
		`<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num><w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num></w:numbering>`
	notes := `<w:footnotes ` + wNS + `><w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:separator/></w:r></w:p></w:footnote>` +
		`<w:footnote w:id="2"><w:p><w:r><w:footnoteRef/></w:r><w:r><w:t xml:space="preserve"> Сноска к тексту.</w:t></w:r></w:p></w:footnote></w:footnotes>`
	return zipOf(t, "[Content_Types].xml", `<Types/>`, "word/document.xml", doc, "word/numbering.xml", numbering, "word/footnotes.xml", notes)
}

func TestDocxText(t *testing.T) {
	res, err := docText("статья.docx", testDOCX(t))
	if err != nil {
		t.Fatal(err)
	}
	want := []string{
		"Заголовок\n\n" +
			"Первый абзац с формулой ${E}^{2}$.[1]\n\n" +
			`$$\frac{a}{\sqrt{b}}=\sum_{i=1}^{n}{i}\sin{x}$$` + "\n\n" +
			"1. Пункт один\n\na) Подпункт\n\n2. Пункт два\n\n• Точка\n\n" +
			"A1 | B1\n\nA3 | B3 ещё\n\n" +
			"Правка: новое αβ ссылка\n\n" +
			"Рядом рамка:\n\nВ рамке\n\n" +
			"Конец первой страницы, продолжение абзаца.",
		"Вторая страница.",
		"Третья страница.\nСтрока 2.\n\n[1] Сноска к тексту.",
	}
	if res.Kind != "docx" || !res.Paged || res.Notes != 1 || res.Formulas != 2 || len(res.Pages) != len(want) {
		t.Fatalf("result: kind %s, paged %v, notes %d, formulas %d, %d pages: %q", res.Kind, res.Paged, res.Notes, res.Formulas, len(res.Pages), res.Pages)
	}
	for i := range want {
		if res.Pages[i] != want[i] {
			t.Errorf("page %d:\n got  %q\n want %q", i+1, res.Pages[i], want[i])
		}
	}
}

func testODT(t *testing.T) []byte {
	content := `<?xml version="1.0" encoding="UTF-8"?><office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0" ` +
		`xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0" xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" ` +
		`xmlns:draw="urn:oasis:names:tc:opendocument:xmlns:drawing:1.0" xmlns:xlink="http://www.w3.org/1999/xlink" ` +
		`xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0"><office:automatic-styles>` +
		`<text:list-style style:name="L1"><text:list-level-style-number text:level="1" style:num-suffix="." style:num-format="1"/>` +
		`<text:list-level-style-number text:level="2" style:num-suffix=")" style:num-format="a"/></text:list-style>` +
		`<text:list-style style:name="L2"><text:list-level-style-bullet text:level="1" text:bullet-char="•"/></text:list-style>` +
		`</office:automatic-styles><office:body><office:text>` +
		`<text:sequence-decls><text:sequence-decl text:name="Table"/></text:sequence-decls>` +
		`<text:tracked-changes><text:changed-region text:id="c1"><text:deletion><text:p>удалено</text:p></text:deletion></text:changed-region></text:tracked-changes>` +
		`<text:h text:outline-level="1">Заголовок</text:h>` +
		"<text:p>Первый   абзац\n<text:s text:c=\"2\"/>с <text:span>выделением</text:span> и формулой " +
		`<draw:frame><draw:object xlink:href="./Object 1"/></draw:frame>.<text:note text:note-class="footnote"><text:note-citation>1</text:note-citation>` +
		`<text:note-body><text:p>Сноска к тексту.</text:p></text:note-body></text:note></text:p>` +
		`<text:p><draw:frame><draw:object xlink:href="./Object 2"/></draw:frame></text:p>` +
		`<text:list text:style-name="L1"><text:list-item><text:p>Пункт один</text:p><text:list><text:list-item><text:p>Подпункт</text:p></text:list-item></text:list></text:list-item>` +
		`<text:list-item><text:p>Пункт два</text:p></text:list-item></text:list>` +
		`<text:list text:style-name="L2"><text:list-item><text:p>Точка</text:p></text:list-item></text:list>` +
		`<table:table><table:table-row><table:table-cell><text:p>A1</text:p></table:table-cell><table:table-cell><text:p>B1</text:p></table:table-cell></table:table-row></table:table>` +
		`<text:p>Конец страницы,<text:soft-page-break/> продолжение.</text:p><text:soft-page-break/>` +
		`<text:p>Вторая страница.<text:line-break/>Строка 2.</text:p>` +
		`</office:text></office:body></office:document-content>`
	obj1 := `<math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><msup><mi>E</mi><mn>2</mn></msup></mrow><annotation encoding="StarMath 5.0">E^2</annotation></semantics></math>`
	obj2 := `<math xmlns="http://www.w3.org/1998/Math/MathML"><semantics><mrow><mfrac><mi>a</mi><msqrt><mi>b</mi></msqrt></mfrac><mo>=</mo>` +
		`<munderover><mo>∑</mo><mrow><mi>i</mi><mo>=</mo><mn>1</mn></mrow><mi>n</mi></munderover><mi>i</mi></mrow></semantics></math>`
	return zipOf(t, "mimetype", "application/vnd.oasis.opendocument.text", "content.xml", content, "Object 1/content.xml", obj1, "Object 2/content.xml", obj2)
}

func TestOdtText(t *testing.T) {
	res, err := docText("статья.odt", testODT(t))
	if err != nil {
		t.Fatal(err)
	}
	want := []string{
		"Заголовок\n\n" +
			"Первый абзац   с выделением и формулой ${E}^{2}$.[1]\n\n" + // the line end is a space, then text:s — two more
			`$$\frac{a}{\sqrt{b}}={\sum }_{i=1}^{n}i$$` + "\n\n" +
			"1. Пункт один\n\na) Подпункт\n\n2. Пункт два\n\n• Точка\n\nA1 | B1\n\n" +
			"Конец страницы, продолжение.",
		"Вторая страница.\nСтрока 2.\n\n[1] Сноска к тексту.",
	}
	if res.Kind != "odt" || !res.Paged || res.Notes != 1 || res.Formulas != 2 || len(res.Pages) != len(want) {
		t.Fatalf("result: kind %s, paged %v, notes %d, formulas %d, %d pages: %q", res.Kind, res.Paged, res.Notes, res.Formulas, len(res.Pages), res.Pages)
	}
	for i := range want {
		if res.Pages[i] != want[i] {
			t.Errorf("page %d:\n got  %q\n want %q", i+1, res.Pages[i], want[i])
		}
	}
}

func TestDocTextErrors(t *testing.T) {
	cases := []struct {
		name string
		data []byte
		want string
	}{
		{"old.doc", append([]byte{0xD0, 0xCF, 0x11, 0xE0}, make([]byte, 100)...), ".doc"},
		{"x.docx", []byte("not a zip"), "DOCX"},
		{"x.docx", zipOf(t, "a.txt", "x"), "DOCX"},
		{"table.ods", zipOf(t, "mimetype", "application/vnd.oasis.opendocument.spreadsheet", "content.xml",
			`<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"><office:body><office:spreadsheet/></office:body></office:document-content>`), "DOCX"},
		{"empty.docx", zipOf(t, "word/document.xml", `<w:document `+wNS+`><w:body><w:p/></w:body></w:document>`), "нет текста"},
		{"bad.docx", zipOf(t, "word/document.xml", `<w:document `+wNS+`><w:body><w:p>`), "не удалось прочитать"},
	}
	for _, c := range cases {
		_, err := docText(c.name, c.data)
		if err == nil || !strings.Contains(err.Error(), c.want) {
			t.Errorf("%s: %v (want …%s…)", c.name, err, c.want)
		}
	}
	// a document in another place of the archive (as _rels/.rels says); without pages of its own — one page
	data := zipOf(t, "_rels/.rels", `<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">`+
		`<Relationship Id="r1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="/doc/main.xml"/></Relationships>`,
		"doc/main.xml", `<w:document `+wNS+`><w:body><w:p><w:r><w:t>Один</w:t></w:r></w:p><w:p><w:r><w:t>Два</w:t></w:r></w:p></w:body></w:document>`)
	res, err := docText("x.docx", data)
	if err != nil || len(res.Pages) != 1 || res.Paged || res.Pages[0] != "Один\n\nДва" {
		t.Errorf("main part from _rels: %v %+v", err, res)
	}
}

func TestDocTextRoute(t *testing.T) {
	a := testApp(t)
	a.cfg = defaultConfig()
	mux := http.NewServeMux()
	a.docTextRoutes(mux)
	rec := httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("POST", "/api/doctext?name=a.odt", bytes.NewReader(testODT(t))))
	var j docTextResult
	if err := json.Unmarshal(rec.Body.Bytes(), &j); rec.Code != 200 || err != nil || j.Kind != "odt" || len(j.Pages) != 2 {
		t.Errorf("POST: %d %s", rec.Code, rec.Body.String())
	}
	rec = httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("GET", "/api/doctext", nil))
	if rec.Code != 405 {
		t.Errorf("GET: %d", rec.Code)
	}
	rec = httptest.NewRecorder()
	mux.ServeHTTP(rec, httptest.NewRequest("POST", "/api/doctext?name=a.doc", strings.NewReader("\xD0\xCF\x11\xE0 old")))
	if rec.Code != 400 || !strings.Contains(rec.Body.String(), ".doc") {
		t.Errorf("old .doc: %d %s", rec.Code, rec.Body.String())
	}
}

func TestFormulaPieces(t *testing.T) {
	for in, want := range map[string]string{
		`<m:oMath ` + wNS + `><m:d><m:dPr><m:begChr m:val="{"/><m:endChr m:val="}"/></m:dPr><m:e><m:r><m:t>x</m:t></m:r></m:e><m:e><m:r><m:t>y</m:t></m:r></m:e></m:d></m:oMath>`:                                      `\{x|y\}`,
		`<m:oMath ` + wNS + `><m:acc><m:accPr><m:chr m:val="⃗"/></m:accPr><m:e><m:r><m:t>v</m:t></m:r></m:e></m:acc></m:oMath>`:                                                                                        `\vec{v}`,
		`<m:oMath ` + wNS + `><m:m><m:mr><m:e><m:r><m:t>1</m:t></m:r></m:e><m:e><m:r><m:t>0</m:t></m:r></m:e></m:mr><m:mr><m:e><m:r><m:t>0</m:t></m:r></m:e><m:e><m:r><m:t>1</m:t></m:r></m:e></m:mr></m:m></m:oMath>`: `\begin{matrix}1 & 0 \\ 0 & 1\end{matrix}`,
		`<m:oMath ` + wNS + `><m:r><m:t>50% $</m:t></m:r></m:oMath>`: `50\% \$`,
	} {
		root, err := parseXML(strings.NewReader(in))
		if err != nil {
			t.Fatal(err)
		}
		if got := omml(root.kids[0]); got != want {
			t.Errorf("%s:\n got  %q\n want %q", in, got, want)
		}
	}
	if got := formatNum(14, "upperRoman") + " " + formatNum(28, "lowerLetter") + " " + formatNum(3, "decimalZero"); got != "XIV bb 03" {
		t.Errorf("numbers: %q", got)
	}
}
