//go:build ignore

// make_icon draws the program's icon from the outline LOGO in ui/index.html (the author's drawing t4: a purple
// T with arrows, here with a thin white outline so that it shows on dark backgrounds) and writes
//
//	rsrc_windows_amd64.syso  the Windows icon resource; "go build" links it into Ttranslator.exe by itself
//	Ttranslator.ico          the same icon as a file (also the icon of ttranslator-window.exe, source/window)
//	Ttranslator.png          256×256, the icon of the own window on Linux (embedded into the launcher)
//
// Only the Go standard library is used. Run it after the drawing changes:
//
//	cd source/launcher && go run make_icon.go
package main

import (
	"bytes"
	"encoding/binary"
	"fmt"
	"image"
	"image/color"
	"image/png"
	"math"
	"os"
	"regexp"
	"strconv"
)

var (
	purple = color.NRGBA{117, 5, 117, 255}
	white  = color.NRGBA{255, 255, 255, 255}
	sizes  = []int{16, 20, 24, 32, 40, 48, 64, 256}
)

const margin = 19.0 // drawing units around the T, room for the outline

type pt struct{ x, y float64 }

func main() {
	html, err := os.ReadFile("../../ui/index.html")
	check(err)
	m := regexp.MustCompile(`const LOGO = \{ view: '[^']*', path: '([^']+)' \}`).FindSubmatch(html)
	if m == nil {
		check(fmt.Errorf("LOGO not found in ui/index.html"))
	}
	poly := parsePath(string(m[1]))
	var imgs []*image.NRGBA
	for _, s := range sizes {
		imgs = append(imgs, render(poly, s))
	}
	var entries [][]byte // icon images: DIB for the small sizes, PNG for 256
	for _, im := range imgs {
		if im.Bounds().Dx() >= 256 {
			var b bytes.Buffer
			check(png.Encode(&b, im))
			entries = append(entries, b.Bytes())
		} else {
			entries = append(entries, dib(im))
		}
	}
	check(os.WriteFile("Ttranslator.ico", ico(imgs, entries), 0o644))
	check(os.WriteFile("rsrc_windows_amd64.syso", coff(resources(imgs, entries)), 0o644))
	check(os.WriteFile("Ttranslator.png", entries[len(entries)-1], 0o644)) // 256×256: the own window on Linux
	fmt.Println("wrote Ttranslator.ico, rsrc_windows_amd64.syso and Ttranslator.png:", sizes)
}

func check(err error) {
	if err != nil {
		fmt.Fprintln(os.Stderr, "make_icon:", err)
		os.Exit(1)
	}
}

// parsePath reads an SVG path of straight segments (M, L, H, V, Z, absolute or relative) as one polygon.
func parsePath(d string) []pt {
	toks := regexp.MustCompile(`[MmLlHhVvZz]|-?(?:\d+\.?\d*|\.\d+)`).FindAllString(d, -1)
	var poly []pt
	var cur pt
	cmd := ""
	num := func(i *int) float64 {
		v, err := strconv.ParseFloat(toks[*i], 64)
		check(err)
		*i++
		return v
	}
	for i := 0; i < len(toks); {
		if t := toks[i]; len(t) == 1 && (t[0] >= 'A' && t[0] <= 'Z' || t[0] >= 'a' && t[0] <= 'z') {
			cmd = t
			i++
			if cmd == "z" || cmd == "Z" {
				continue
			}
		}
		switch cmd {
		case "M", "L":
			cur = pt{num(&i), num(&i)}
			if cmd == "M" {
				cmd = "L" // further pairs after M are lines
			}
		case "m", "l":
			cur = pt{cur.x + num(&i), cur.y + num(&i)}
			if cmd == "m" {
				cmd = "l"
			}
		case "H":
			cur.x = num(&i)
		case "h":
			cur.x += num(&i)
		case "V":
			cur.y = num(&i)
		case "v":
			cur.y += num(&i)
		default:
			check(fmt.Errorf("unsupported path command %q", cmd))
		}
		poly = append(poly, cur)
	}
	return poly
}

func inside(p []pt, x, y float64) bool {
	in := false
	for i, j := 0, len(p)-1; i < len(p); j, i = i, i+1 {
		if (p[i].y > y) != (p[j].y > y) && x < (p[j].x-p[i].x)*(y-p[i].y)/(p[j].y-p[i].y)+p[i].x {
			in = !in
		}
	}
	return in
}

func distance(p []pt, x, y float64) float64 {
	best := math.Inf(1)
	for i, j := 0, len(p)-1; i < len(p); j, i = i, i+1 {
		ax, ay, bx, by := p[j].x, p[j].y, p[i].x, p[i].y
		dx, dy := bx-ax, by-ay
		t := ((x-ax)*dx + (y-ay)*dy) / (dx*dx + dy*dy)
		t = math.Max(0, math.Min(1, t))
		best = math.Min(best, math.Hypot(x-(ax+t*dx), y-(ay+t*dy)))
	}
	return best
}

// render draws the T centred in a size×size square with a white outline (about 1 pixel at 16 px), 8×8 samples
// per pixel.
func render(poly []pt, size int) *image.NRGBA {
	minX, minY, maxX, maxY := math.Inf(1), math.Inf(1), math.Inf(-1), math.Inf(-1)
	for _, q := range poly {
		minX, minY, maxX, maxY = math.Min(minX, q.x), math.Min(minY, q.y), math.Max(maxX, q.x), math.Max(maxY, q.y)
	}
	span := math.Max(maxX-minX, maxY-minY) + 2*margin
	ox, oy := (minX+maxX)/2-span/2, (minY+maxY)/2-span/2
	unit := span / float64(size)                    // drawing units per pixel
	outline := math.Max(1, float64(size)/22) * unit // outline width in drawing units
	const n = 8
	im := image.NewNRGBA(image.Rect(0, 0, size, size))
	for py := 0; py < size; py++ {
		for px := 0; px < size; px++ {
			var np, nw int
			for sy := 0; sy < n; sy++ {
				for sx := 0; sx < n; sx++ {
					x := ox + (float64(px)+(float64(sx)+0.5)/n)*unit
					y := oy + (float64(py)+(float64(sy)+0.5)/n)*unit
					if inside(poly, x, y) {
						np++
					} else if distance(poly, x, y) <= outline {
						nw++
					}
				}
			}
			if np+nw == 0 {
				continue
			}
			mix := func(a, b uint8) uint8 { return uint8((np*int(a) + nw*int(b) + (np+nw)/2) / (np + nw)) }
			im.SetNRGBA(px, py, color.NRGBA{mix(purple.R, white.R), mix(purple.G, white.G), mix(purple.B, white.B),
				uint8((255*(np+nw) + n*n/2) / (n * n))})
		}
	}
	return im
}

// dib is an icon image in the classic format: BITMAPINFOHEADER, 32-bit BGRA rows bottom-up, then the 1-bit
// AND mask (1 = transparent).
func dib(im *image.NRGBA) []byte {
	w, h := im.Bounds().Dx(), im.Bounds().Dy()
	maskRow := (w + 31) / 32 * 4
	var b bytes.Buffer
	for _, v := range []any{uint32(40), int32(w), int32(2 * h), uint16(1), uint16(32), uint32(0),
		uint32(w*h*4 + maskRow*h), int32(0), int32(0), uint32(0), uint32(0)} {
		binary.Write(&b, binary.LittleEndian, v)
	}
	for y := h - 1; y >= 0; y-- {
		for x := 0; x < w; x++ {
			c := im.NRGBAAt(x, y)
			b.Write([]byte{c.B, c.G, c.R, c.A})
		}
	}
	for y := h - 1; y >= 0; y-- {
		row := make([]byte, maskRow)
		for x := 0; x < w; x++ {
			if im.NRGBAAt(x, y).A == 0 {
				row[x/8] |= 0x80 >> (x % 8)
			}
		}
		b.Write(row)
	}
	return b.Bytes()
}

func dim(im *image.NRGBA) byte { // 256 is written as 0
	return byte(im.Bounds().Dx() % 256)
}

func ico(imgs []*image.NRGBA, entries [][]byte) []byte {
	var b bytes.Buffer
	le := func(v any) { binary.Write(&b, binary.LittleEndian, v) }
	le(uint16(0))
	le(uint16(1))
	le(uint16(len(imgs)))
	off := 6 + 16*len(imgs)
	for i, im := range imgs {
		b.Write([]byte{dim(im), dim(im), 0, 0})
		le(uint16(1))
		le(uint16(32))
		le(uint32(len(entries[i])))
		le(uint32(off))
		off += len(entries[i])
	}
	for _, e := range entries {
		b.Write(e)
	}
	return b.Bytes()
}

type resource struct {
	typ, id uint32
	data    []byte
}

// resources: RT_ICON 1…n (the images) and RT_GROUP_ICON 1 (their list).
func resources(imgs []*image.NRGBA, entries [][]byte) []resource {
	var g bytes.Buffer
	le := func(v any) { binary.Write(&g, binary.LittleEndian, v) }
	le(uint16(0))
	le(uint16(1))
	le(uint16(len(imgs)))
	var res []resource
	for i, im := range imgs {
		g.Write([]byte{dim(im), dim(im), 0, 0})
		le(uint16(1))
		le(uint16(32))
		le(uint32(len(entries[i])))
		le(uint16(i + 1))
		res = append(res, resource{3, uint32(i + 1), entries[i]})
	}
	return append(res, resource{14, 1, g.Bytes()})
}

// coff builds an AMD64 COFF object with one .rsrc section: the resource directory (type → id → language),
// the data entries and the data. The data addresses in the entries are relocated (IMAGE_REL_AMD64_ADDR32NB)
// against the section, which is how Go's linker places resources from .syso files into the executable.
func coff(res []resource) []byte {
	const lang = 0x0409
	types := []uint32{}
	byType := map[uint32][]resource{}
	for _, r := range res {
		if len(byType[r.typ]) == 0 {
			types = append(types, r.typ)
		}
		byType[r.typ] = append(byType[r.typ], r)
	}
	for i := range types { // ids in ascending order, as Windows expects
		for j := i + 1; j < len(types); j++ {
			if types[j] < types[i] {
				types[i], types[j] = types[j], types[i]
			}
		}
	}
	// sizes of the directory parts
	dirSize := func(entries int) int { return 16 + 8*entries }
	rootLen := dirSize(len(types))
	typeLen := 0
	for _, t := range types {
		typeLen += dirSize(len(byType[t]))
	}
	langLen := dirSize(1) * len(res)
	dataEntries := rootLen + typeLen + langLen
	dataStart := dataEntries + 16*len(res)
	var sec bytes.Buffer
	le := func(v any) { binary.Write(&sec, binary.LittleEndian, v) }
	dir := func(n int) {
		le(uint32(0))
		le(uint32(0))
		le(uint16(0))
		le(uint16(0))
		le(uint16(0))
		le(uint16(n))
	}
	// root: one entry per type, pointing to the type directories
	dir(len(types))
	off := rootLen
	for _, t := range types {
		le(t)
		le(uint32(0x80000000 | off))
		off += dirSize(len(byType[t]))
	}
	// type directories: one entry per id, pointing to its language directory
	langOff := rootLen + typeLen
	k := 0
	order := []resource{}
	for _, t := range types {
		dir(len(byType[t]))
		for _, r := range byType[t] {
			le(r.id)
			le(uint32(0x80000000 | (langOff + k*dirSize(1))))
			order = append(order, r)
			k++
		}
	}
	// language directories: one entry (lang), pointing to the data entry
	for i := range order {
		dir(1)
		le(uint32(lang))
		le(uint32(dataEntries + 16*i))
	}
	// data entries (the address is relocated) and the data itself, 8-byte aligned
	var relocs []uint32
	pos := dataStart
	for _, r := range order {
		relocs = append(relocs, uint32(sec.Len()))
		le(uint32(pos))
		le(uint32(len(r.data)))
		le(uint32(0))
		le(uint32(0))
		pos += (len(r.data) + 7) &^ 7
	}
	for _, r := range order {
		sec.Write(r.data)
		sec.Write(make([]byte, ((len(r.data)+7)&^7)-len(r.data)))
	}
	data := sec.Bytes()

	var b bytes.Buffer
	w := func(v any) { binary.Write(&b, binary.LittleEndian, v) }
	const fileHeader, sectionHeader = 20, 40
	rawPtr := fileHeader + sectionHeader
	relPtr := rawPtr + len(data)
	symPtr := relPtr + 10*len(relocs)
	// IMAGE_FILE_HEADER
	w(uint16(0x8664))
	w(uint16(1))
	w(uint32(0))
	w(uint32(symPtr))
	w(uint32(1))
	w(uint16(0))
	w(uint16(0))
	// IMAGE_SECTION_HEADER
	b.WriteString(".rsrc\x00\x00\x00")
	w(uint32(0))
	w(uint32(0))
	w(uint32(len(data)))
	w(uint32(rawPtr))
	w(uint32(relPtr))
	w(uint32(0))
	w(uint16(len(relocs)))
	w(uint16(0))
	w(uint32(0x40000040)) // initialized data, readable
	b.Write(data)
	for _, r := range relocs { // IMAGE_RELOCATION: address, symbol 0 (the section), IMAGE_REL_AMD64_ADDR32NB
		w(r)
		w(uint32(0))
		w(uint16(3))
	}
	// symbol table: the section symbol .rsrc (static), then an empty string table
	b.WriteString(".rsrc\x00\x00\x00")
	w(uint32(0))
	w(int16(1))
	w(uint16(0))
	w(uint8(3))
	w(uint8(0))
	w(uint32(4))
	return b.Bytes()
}
