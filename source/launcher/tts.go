package main

// Read aloud: Piper voices (small VITS speech models) spoken by sherpa-onnx's program sherpa-onnx-offline-tts.
// Both come from the official sherpa-onnx releases on GitHub; they are downloaded only when the user asks for a
// voice (version pinned, size and SHA-256 checked) and are not part of the program's archive. Every request
// starts the program once — loading the voice and speaking a phrase take about a second — and returns a WAV file;
// nothing stays in memory between phrases.

import (
	"bytes"
	"compress/bzip2"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"io/fs"
	"net/http"
	"os"
	"os/exec"
	"path"
	"path/filepath"
	"runtime"
	"strconv"
	"strings"
	"sync/atomic"
	"time"
	"unicode/utf8"
)

const (
	ttsVersion   = "v1.13.7"
	ttsRelease   = "https://github.com/k2-fsa/sherpa-onnx/releases/download/" + ttsVersion + "/"
	voiceRelease = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/"
	voiceSamples = "https://rhasspy.github.io/piper-samples/"
	ttsMaxChars  = 2000             // one request; the window sends sentences of a few hundred characters
	ttsTimeout   = 60 * time.Second // one phrase normally takes about a second
)

// ttsPackage is the sherpa-onnx release archive for this platform (shared build: the program, onnxruntime and
// the sherpa-onnx libraries).
type ttsPackage struct {
	Asset  string
	Size   int64
	SHA256 string
}

// Sizes and checksums of the official sherpa-onnx v1.13.7 release files.
func currentTTSPackage() (ttsPackage, bool) {
	switch runtime.GOOS + "/" + runtime.GOARCH {
	case "windows/amd64":
		return ttsPackage{"sherpa-onnx-" + ttsVersion + "-win-x64-shared-MD-Release.tar.bz2", 20117803,
			"e78b44e0aa68f2fe4540ffa06994c586056d889beb70176801c7c62a338f769c"}, true
	case "linux/amd64":
		return ttsPackage{"sherpa-onnx-" + ttsVersion + "-linux-x64-shared.tar.bz2", 27884774,
			"95b9f4358e2d5522a0bd987c3ee91128e31f8abf4340927cab32e438300f3c24"}, true
	case "darwin/amd64", "darwin/arm64":
		return ttsPackage{"sherpa-onnx-" + ttsVersion + "-osx-universal2-shared.tar.bz2", 43312926,
			"a486bb987f9ccff182768bf75c39e81c2d3e4ba7143368e9e00139becc441cb5"}, true
	}
	return ttsPackage{}, false
}

func ttsExeName() string {
	if runtime.GOOS == "windows" {
		return "sherpa-onnx-offline-tts.exe"
	}
	return "sherpa-onnx-offline-tts"
}

// VoiceSpec is a Piper voice packed by sherpa-onnx: the archive holds one folder (Dir) with the model, tokens.txt
// and espeak-ng-data — or, for Chinese, a pronunciation lexicon and text rules instead of espeak-ng-data. A voice
// that sherpa-onnx has not packed into an archive is made of separate files (Parts) put into that folder.
type VoiceSpec struct {
	ID      string      `json:"id"`
	Lang    string      `json:"lang"`    // language code of the interface lists (ru, en, de, …)
	Name    string      `json:"name"`    // name of the voice
	Gender  string      `json:"gender"`  // "female" or "male"
	License string      `json:"license"` // licence of the voice (of its training data)
	NC      bool        `json:"nc"`      // the licence allows only non-commercial use
	Dir     string      `json:"dir"`
	Model   string      `json:"model"`
	SID     int         `json:"sid"`  // speaker of a voice with several speakers
	URL     string      `json:"url"`  // the archive, or the first of the parts
	Page    string      `json:"page"` // samples to listen to
	Size    int64       `json:"size"` // of the archive, or of all the parts
	SHA256  string      `json:"sha256"`
	Lexicon string      `json:"lexicon,omitempty"` // a voice without espeak-ng (Chinese): its lexicon file…
	Rules   []string    `json:"rules,omitempty"`   // …and the rules that spell out numbers, dates and phone numbers
	Parts   []VoicePart `json:"parts,omitempty"`   // a voice made of separate files instead of one archive
}

// VoicePart is one file of a voice made of parts; an archive (.tar.bz2) is unpacked into the voice's folder.
type VoicePart struct {
	URL    string `json:"url"`
	File   string `json:"file"`
	Size   int64  `json:"size"`
	SHA256 string `json:"sha256"`
}

func piperVoice(id, lang, name, gender, license string, nc bool, voice string, size int64, sha string) VoiceSpec {
	dir := "vits-piper-" + voice
	return VoiceSpec{ID: id, Lang: lang, Name: name, Gender: gender, License: license, NC: nc, Dir: dir, Model: voice + ".onnx",
		URL: voiceRelease + dir + ".tar.bz2", Page: voiceSamples + "#" + voice, Size: size, SHA256: sha}
}

// lexiconVoice: a voice that reads with a lexicon and text rules (files in its archive) instead of espeak-ng.
func lexiconVoice(v VoiceSpec, lexicon string, rules ...string) VoiceSpec {
	v.Lexicon, v.Rules = lexicon, rules
	return v
}

// partsVoice: a voice made of separate files — the model and tokens.txt, and espeak-ng-data from its archive.
func partsVoice(id, lang, name, gender, license string, nc bool, voice string, parts ...VoicePart) VoiceSpec {
	v := VoiceSpec{ID: id, Lang: lang, Name: name, Gender: gender, License: license, NC: nc, Dir: "vits-piper-" + voice,
		Model: voice + ".onnx", URL: parts[0].URL, Page: voiceSamples + "#" + voice, SHA256: parts[0].SHA256, Parts: parts}
	for _, p := range parts {
		v.Size += p.Size
	}
	return v
}

// espeak-ng-data of sherpa-onnx: the same files as in every Piper archive of its release
var espeakPart = VoicePart{URL: voiceRelease + "espeak-ng-data.tar.bz2", File: "espeak-ng-data.tar.bz2", Size: 7252012,
	SHA256: "4135ccf82e1f40613491c0874d4945ae9e9c7840933d8e25a6f9e003d9ebf533"}

// es_ES-mls_9972-low is not among the archives of the sherpa-onnx release; its author keeps the converted model
// (with the metadata sherpa-onnx reads) on Hugging Face. Pinned to a commit; size and SHA-256 as for every download.
const hfMLS9972 = "https://huggingface.co/csukuangfj/vits-piper-es_ES-mls_9972-low/resolve/5440d32fb5870a035eea1e03b833f29724803378/"

// The voices chosen by the author (21.10.2026, Spanish and Chinese 22.10.2026) and, for Russian and English, a
// voice with a free licence. Licences are those of the voices' training data (MODEL_CARD of each voice).
var voiceSpecs = []VoiceSpec{
	piperVoice("ru-ruslan", "ru", "Ruslan", "male", "CC BY-NC-SA 4.0", true, "ru_RU-ruslan-medium", 67210684,
		"0690b1cad01f86e8db9ba988af24898bdc1af774e23cb2e46b9c730269b6fd83"),
	piperVoice("ru-dmitri", "ru", "Dmitri", "male", "CC0", false, "ru_RU-dmitri-medium", 67188551,
		"c86d0803737de13d441923ff3b3f309482fab8d7af3ec85949942809eb9a3660"),
	piperVoice("en-hfc-female", "en", "HFC female", "female", "CC BY-NC-SA 4.0", true, "en_US-hfc_female-medium", 67228166,
		"3fffdceb0c65bd9415a085d09c3cb88cc82f9d74a6ca453f8ce7fc5eaee81ff8"),
	piperVoice("en-ljspeech", "en", "LJSpeech", "female", "public domain", false, "en_US-ljspeech-medium", 67169893,
		"3dfb4b759d8be032a4903a9538d128b0fda2a06ab1de6cbc2d93a97e2dd83dba"),
	piperVoice("de-kerstin", "de", "Kerstin", "female", "CC0", false, "de_DE-kerstin-low", 67107768,
		"4bfe121d5f690a3b87acecd7ae1e70b48f4589ce6ae9f45a1809e6eb19fad97b"),
	piperVoice("sv-alma", "sv", "Alma", "female", "CC BY 4.0", false, "sv_SE-alma-medium", 67154700,
		"4ab8212595575e52595bc95c37d0b4f79450c0f00b63496346cdc5941d913edc"),
	partsVoice("es-mls-9972", "es", "MLS 9972", "female", "CC BY 4.0", false, "es_ES-mls_9972-low",
		VoicePart{URL: hfMLS9972 + "es_ES-mls_9972-low.onnx", File: "es_ES-mls_9972-low.onnx", Size: 63104654,
			SHA256: "29cd34f8c8c7f176efd2e438e563847e8e7f37c33de994e0746fe839de432cc8"},
		VoicePart{URL: hfMLS9972 + "tokens.txt", File: "tokens.txt", Size: 763,
			SHA256: "42d1a69ed2b91a51928a711aa228ed9f3dc021c6d359a3e9c4f37eb1d20f80bd"},
		espeakPart),
	lexiconVoice(piperVoice("zh-chaowen", "zh", "Chaowen", "male", "CC0", false, "zh_CN-chaowen-medium", 60443846,
		"1b69bdcf10bb6331c7f8a7591940febeb175c6bb86caa3802d96531f8e4ad211"), "lexicon.txt", "phone.fst", "date.fst", "number.fst"),
}

// Test hooks, used only when the environment variables are set: TDOC_TTS_URL replaces the sherpa-onnx archive
// URL (size and checksum are then not checked), TDOC_TEST_VOICES points to a JSON list of VoiceSpec.
var ttsURLOverride string

func applyTTSTestOverrides() {
	ttsURLOverride = os.Getenv("TDOC_TTS_URL")
	if p := os.Getenv("TDOC_TEST_VOICES"); p != "" {
		b, err := os.ReadFile(p)
		var vs []VoiceSpec
		if err == nil && json.Unmarshal(b, &vs) == nil && len(vs) > 0 {
			voiceSpecs = vs
			logger.Printf("test voices from %s", p)
		}
	}
}

func findVoice(id string) *VoiceSpec {
	for i := range voiceSpecs {
		if voiceSpecs[i].ID == id {
			v := voiceSpecs[i]
			return &v
		}
	}
	return nil
}

func (a *App) voicesDir() string            { return filepath.Join(a.modelsDir, "voices") }
func (a *App) voiceDir(v *VoiceSpec) string { return filepath.Join(a.voicesDir(), v.Dir) }

// voiceParts are the downloads of a voice: its archive, or its separate files.
func voiceParts(v *VoiceSpec) []VoicePart {
	if len(v.Parts) > 0 {
		return v.Parts
	}
	return []VoicePart{{URL: v.URL, File: path.Base(v.URL), Size: v.Size, SHA256: v.SHA256}}
}

// partPath is where a download of a voice is kept until it is unpacked or moved: an archive in the voices folder
// (as before 0.9.3), the separate files in a folder of their own (<Dir>.download), so that tokens.txt of two voices
// never meet.
func (a *App) partPath(v *VoiceSpec, p VoicePart) string {
	if len(v.Parts) == 0 {
		return filepath.Join(a.voicesDir(), p.File)
	}
	return filepath.Join(a.voicesDir(), v.Dir+".download", p.File)
}

// voicePartial is how much of a voice has been downloaded so far (finished parts and the unfinished one).
func (a *App) voicePartial(v *VoiceSpec) int64 {
	var n int64
	for _, p := range voiceParts(v) {
		dest := a.partPath(v, p)
		if st, err := os.Stat(dest); err == nil && len(v.Parts) > 0 && st.Size() == p.Size {
			n += p.Size
		} else if st, err := os.Stat(dest + ".part"); err == nil {
			n += st.Size()
		}
	}
	return n
}

// removeVoiceDownloads deletes unfinished downloads of a voice.
func (a *App) removeVoiceDownloads(v *VoiceSpec) {
	if len(v.Parts) > 0 {
		_ = os.RemoveAll(filepath.Join(a.voicesDir(), v.Dir+".download"))
		return
	}
	_ = os.Remove(a.partPath(v, voiceParts(v)[0]) + ".part")
}

func (a *App) voicePresent(v *VoiceSpec) bool {
	d := a.voiceDir(v)
	need := []string{v.Model, "tokens.txt"}
	if v.Lexicon != "" {
		need = append(append(need, v.Lexicon), v.Rules...)
	}
	for _, f := range need {
		st, err := os.Stat(filepath.Join(d, f))
		if err != nil || st.IsDir() || st.Size() == 0 {
			return false
		}
	}
	if v.Lexicon != "" {
		return true
	}
	st, err := os.Stat(filepath.Join(d, "espeak-ng-data"))
	return err == nil && st.IsDir()
}

// activeVoiceID is the voice that reads a language: the one chosen for it (config.json "voices"), or else the
// first downloaded voice of that language in the catalogue. Caller holds a.mu.
func (a *App) activeVoiceID(lang string) string {
	if id := a.cfg.Voices[lang]; id != "" {
		if v := findVoice(id); v != nil && v.Lang == lang && a.voicePresent(v) {
			return id
		}
	}
	for i := range voiceSpecs {
		if voiceSpecs[i].Lang == lang && a.voicePresent(&voiceSpecs[i]) {
			return voiceSpecs[i].ID
		}
	}
	return ""
}

type ttsMeta struct {
	Version string `json:"version"`
	Exe     string `json:"exe"`
}

// ttsExe returns the installed sherpa-onnx program (engine/<os>-<arch>/tts.json), or "".
func (a *App) ttsExe() string {
	b, err := os.ReadFile(filepath.Join(a.engineDir, "tts.json"))
	if err != nil {
		return ""
	}
	var m ttsMeta
	if json.Unmarshal(b, &m) != nil || m.Exe == "" {
		return ""
	}
	p := filepath.Join(a.engineDir, filepath.FromSlash(m.Exe))
	if st, err := os.Stat(p); err != nil || st.IsDir() {
		return ""
	}
	return p
}

func (a *App) ttsURL(pkg ttsPackage) string {
	if ttsURLOverride != "" {
		return ttsURLOverride
	}
	if pkg.Asset == "" {
		return ""
	}
	return ttsRelease + pkg.Asset
}

// ttsStateJSON describes read-aloud for /api/state. Caller holds a.mu.
func (a *App) ttsStateJSON() map[string]any {
	pkg, ok := currentTTSPackage()
	u := a.ttsURL(pkg)
	exe := a.ttsExe()
	voices := []map[string]any{}
	for i := range voiceSpecs {
		v := &voiceSpecs[i]
		present := a.voicePresent(v)
		var partial int64
		if !present {
			partial = a.voicePartial(v)
		}
		parts := []map[string]any{}
		for _, p := range voiceParts(v) {
			parts = append(parts, map[string]any{"url": p.URL, "file": p.File, "size": p.Size})
		}
		voices = append(voices, map[string]any{
			"id": v.ID, "lang": v.Lang, "name": v.Name, "gender": v.Gender, "license": v.License, "nc": v.NC,
			"url": v.URL, "page": v.Page, "file": path.Base(v.URL), "size": v.Size, "parts": parts,
			"present": present, "active": present && a.activeVoiceID(v.Lang) == v.ID, "partial": partial,
		})
	}
	return map[string]any{
		"engine": map[string]any{
			"present": exe != "", "supported": ok || ttsURLOverride != "", "version": ttsVersion,
			"url": u, "file": path.Base(u), "dir": a.engineDir, "size": pkg.Size,
		},
		"voices":     voices,
		"voices_dir": a.voicesDir(),
		"download":   a.vdl,
	}
}

// ---------------------------------------------------------------- downloads

func (a *App) setVDL(f func(d *DownloadState)) {
	a.mu.Lock()
	f(&a.vdl)
	a.mu.Unlock()
}

// startVoiceDownload downloads a voice (and, the first time, the sherpa-onnx program) in the background. The
// download has its own state: the model, the translation and the window keep working meanwhile.
func (a *App) startVoiceDownload(v *VoiceSpec) error {
	pkg, supported := currentTTSPackage()
	a.mu.Lock()
	if a.vdl.Active {
		a.mu.Unlock()
		return errors.New(tr("идёт скачивание голоса, дождитесь окончания"))
	}
	needTTS := a.ttsExe() == ""
	if needTTS && !supported && ttsURLOverride == "" {
		a.mu.Unlock()
		return fmt.Errorf(tr("платформа %s/%s пока не поддерживается"), runtime.GOOS, runtime.GOARCH)
	}
	ctx, cancel := context.WithCancel(context.Background())
	a.vdlCancel = cancel
	a.vdl = DownloadState{Active: true, Item: "voice", Name: v.ID}
	a.mu.Unlock()

	go func() {
		defer cancel()
		var err error
		if needTTS {
			err = a.downloadTTS(ctx, pkg, v.ID)
		}
		if err == nil && !a.voicePresent(v) {
			err = a.downloadVoice(ctx, v)
		}
		a.mu.Lock()
		a.vdl.Active, a.vdl.Phase = false, ""
		if err != nil {
			if errors.Is(err, context.Canceled) {
				a.vdl.Error = tr("скачивание отменено")
			} else {
				a.vdl.Error = err.Error()
			}
			logger.Printf("voice download failed: %v", err)
		} else {
			a.vdl.Error = ""
			// the voice just downloaded is the one the user wants to hear
			if a.cfg.Voices == nil {
				a.cfg.Voices = map[string]string{}
			}
			a.cfg.Voices[v.Lang] = v.ID
			a.saveConfig(a.cfg)
		}
		a.mu.Unlock()
	}()
	return nil
}

func (a *App) downloadTTS(ctx context.Context, pkg ttsPackage, voiceID string) error {
	u := a.ttsURL(pkg)
	size, sum := pkg.Size, pkg.SHA256
	if ttsURLOverride != "" {
		size, sum = 0, ""
	}
	asset := path.Base(u)
	a.setVDL(func(d *DownloadState) {
		*d = DownloadState{Active: true, Item: "tts", Name: voiceID, Phase: "download", Total: size}
	})
	archive := filepath.Join(a.engineDir, asset)
	if err := a.fetchTo(ctx, u, archive, size, sum, a.setVDL); err != nil {
		return fmt.Errorf(tr("программа озвучки: %w"), err)
	}
	a.setVDL(func(d *DownloadState) { d.Phase = "extract" })
	top := strings.TrimSuffix(asset, ".tar.bz2")
	_ = os.RemoveAll(filepath.Join(a.engineDir, top))
	if err := untarbz2(archive, a.engineDir); err != nil {
		return fmt.Errorf(tr("распаковка программы озвучки: %w"), err)
	}
	exe := ""
	_ = filepath.WalkDir(filepath.Join(a.engineDir, top), func(p string, d fs.DirEntry, err error) error {
		if err == nil && !d.IsDir() && d.Name() == ttsExeName() && exe == "" {
			exe = p
		}
		return nil
	})
	if exe == "" {
		return fmt.Errorf(tr("в архиве нет файла %s"), ttsExeName())
	}
	if runtime.GOOS != "windows" {
		_ = os.Chmod(exe, 0o755)
	}
	rel, _ := filepath.Rel(a.engineDir, exe)
	meta, _ := json.MarshalIndent(ttsMeta{Version: ttsVersion, Exe: filepath.ToSlash(rel)}, "", "  ")
	if err := os.WriteFile(filepath.Join(a.engineDir, "tts.json"), meta, 0o644); err != nil {
		return err
	}
	_ = os.Remove(archive)
	logger.Printf("sherpa-onnx installed: %s", exe)
	return nil
}

func (a *App) downloadVoice(ctx context.Context, v *VoiceSpec) error {
	dir := a.voicesDir()
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	a.setVDL(func(d *DownloadState) {
		*d = DownloadState{Active: true, Item: "voice", Name: v.ID, Phase: "download", Total: v.Size}
	})
	// the parts one after another; the progress counts all of them together
	var before int64
	for _, p := range voiceParts(v) {
		dest := a.partPath(v, p)
		if err := os.MkdirAll(filepath.Dir(dest), 0o755); err != nil {
			return err
		}
		// a part finished earlier (fetchTo keeps a file only after checking its size and SHA-256)
		if st, err := os.Stat(dest); err == nil && len(v.Parts) > 0 && st.Size() == p.Size {
			before += p.Size
			continue
		}
		var cur DownloadState
		base := before
		progress := func(f func(d *DownloadState)) {
			f(&cur)
			a.setVDL(func(d *DownloadState) {
				d.Phase, d.Speed, d.Done, d.Total = cur.Phase, cur.Speed, base+cur.Done, v.Size
			})
		}
		if err := a.fetchTo(ctx, p.URL, dest, p.Size, p.SHA256, progress); err != nil {
			if len(v.Parts) > 0 {
				return fmt.Errorf(tr("голос (%s): %w"), p.File, err)
			}
			return fmt.Errorf(tr("голос: %w"), err)
		}
		before += p.Size
	}
	a.setVDL(func(d *DownloadState) { d.Phase = "extract" })
	vd := a.voiceDir(v)
	_ = os.RemoveAll(vd)
	if len(v.Parts) == 0 {
		if err := untarbz2(a.partPath(v, voiceParts(v)[0]), dir); err != nil {
			return fmt.Errorf(tr("распаковка голоса: %w"), err)
		}
	} else {
		if err := os.MkdirAll(vd, 0o755); err != nil {
			return err
		}
		for _, p := range v.Parts {
			src := a.partPath(v, p)
			var err error
			if strings.HasSuffix(p.File, ".tar.bz2") {
				err = untarbz2(src, vd)
			} else {
				err = os.Rename(src, filepath.Join(vd, p.File))
			}
			if err != nil {
				return fmt.Errorf(tr("распаковка голоса: %w"), err)
			}
		}
	}
	if !a.voicePresent(v) {
		return fmt.Errorf(tr("в архиве нет файла %s"), v.Dir+"/"+v.Model)
	}
	a.removeVoiceDownloads(v)
	if len(v.Parts) == 0 {
		_ = os.Remove(a.partPath(v, voiceParts(v)[0]))
	}
	logger.Printf("voice installed: %s", v.Dir)
	return nil
}

// untarbz2 unpacks a .tar.bz2 archive into dest (no paths outside dest).
func untarbz2(archive, dest string) error {
	f, err := os.Open(archive)
	if err != nil {
		return err
	}
	defer f.Close()
	return untar(bzip2.NewReader(f), dest)
}

// ---------------------------------------------------------------- speaking

var ttsSeq atomic.Int64

// ttsThreads: up to 4 threads; a phrase is short, most of the time goes to loading the voice.
func ttsThreads() int {
	n := runtime.NumCPU()
	if n > 4 {
		n = 4
	}
	if n < 1 {
		n = 1
	}
	return n
}

// ttsArgs are the arguments of sherpa-onnx-offline-tts for one phrase. Paths are relative to the voices folder
// (the working directory of the program) and contain only ASCII letters: on Windows a program reads its
// command line in the system code page, and the folder of the program may have any letters in its name.
// "--" ends the options, so a text that starts with "--" is still text.
func ttsArgs(v *VoiceSpec, text string, speed float64, out string) []string {
	args := []string{
		"--vits-model=" + v.Dir + "/" + v.Model,
		"--vits-tokens=" + v.Dir + "/tokens.txt",
	}
	if v.Lexicon != "" {
		args = append(args, "--vits-lexicon="+v.Dir+"/"+v.Lexicon)
		if len(v.Rules) > 0 {
			rules := make([]string, len(v.Rules))
			for i, r := range v.Rules {
				rules[i] = v.Dir + "/" + r
			}
			args = append(args, "--tts-rule-fsts="+strings.Join(rules, ","))
		}
	} else {
		args = append(args, "--vits-data-dir="+v.Dir+"/espeak-ng-data")
	}
	return append(args,
		"--num-threads="+strconv.Itoa(ttsThreads()),
		"--sid="+strconv.Itoa(v.SID),
		"--speed="+strconv.FormatFloat(speed, 'f', 2, 64),
		"--output-filename="+out,
		"--", text,
	)
}

// synthesize speaks one phrase and returns the WAV file.
func (a *App) synthesize(ctx context.Context, exe string, v *VoiceSpec, text string, speed float64) ([]byte, error) {
	a.ttsMu.Lock() // one phrase at a time: the window asks for the next sentence while the current one sounds
	defer a.ttsMu.Unlock()
	if err := ctx.Err(); err != nil {
		return nil, err
	}
	dir := a.voicesDir()
	out := fmt.Sprintf("tts-%d-%d.wav", os.Getpid(), ttsSeq.Add(1))
	defer os.Remove(filepath.Join(dir, out))
	args := ttsArgs(v, text, speed, out)
	ctx, cancel := context.WithTimeout(ctx, ttsTimeout)
	defer cancel()
	run := func(prog string) (string, error) {
		cmd := exec.CommandContext(ctx, prog, args...)
		cmd.Dir = dir
		var buf bytes.Buffer
		cmd.Stdout, cmd.Stderr = &buf, &buf
		cmd.Env = engineEnv(filepath.Dir(prog))
		setChildAttrs(cmd)
		err := cmd.Run()
		return buf.String(), err
	}
	prog := exe
	a.mu.Lock()
	noUTF8 := a.ttsNoUTF8
	a.mu.Unlock()
	if runtime.GOOS == "windows" && !noUTF8 {
		if p, err := utf8Copy(exe); err == nil {
			prog = p
		} else {
			logger.Printf("tts: no UTF-8 copy of the program: %v", err)
		}
	}
	t0 := time.Now()
	output, err := run(prog)
	var exitErr *exec.ExitError
	if err != nil && prog != exe && ctx.Err() == nil && (!errors.As(err, &exitErr) || uint32(exitErr.ExitCode()) == sxsExitCode) {
		// the copy with the UTF-8 manifest did not start on this system: use the program as it is
		logger.Printf("tts: the UTF-8 copy did not start (%v), using the original program", err)
		a.mu.Lock()
		a.ttsNoUTF8 = true
		a.mu.Unlock()
		output, err = run(exe)
	}
	if err != nil {
		if errors.Is(ctx.Err(), context.DeadlineExceeded) {
			return nil, errors.New(tr("чтение вслух не ответило за минуту"))
		}
		if ctx.Err() != nil {
			return nil, ctx.Err()
		}
		logger.Printf("tts failed: %v\n%s", err, lastLines(output, 20))
		return nil, fmt.Errorf(tr("не удалось прочитать текст вслух: %s"), lastLines(output, 3))
	}
	wav, err := os.ReadFile(filepath.Join(dir, out))
	if err != nil || len(wav) < 44 || string(wav[:4]) != "RIFF" {
		return nil, fmt.Errorf(tr("не удалось прочитать текст вслух: %s"), lastLines(output, 3))
	}
	logger.Printf("tts %s: %d characters in %d ms", v.ID, utf8.RuneCountInString(text), time.Since(t0).Milliseconds())
	return wav, nil
}

func lastLines(s string, n int) string {
	lines := strings.Split(strings.TrimSpace(s), "\n")
	if len(lines) > n {
		lines = lines[len(lines)-n:]
	}
	return strings.TrimSpace(strings.Join(lines, "\n"))
}

// ---------------------------------------------------------------- Windows: the command line in UTF-8

// sherpa-onnx-offline-tts.exe reads its command line in the system code page, so on a German Windows a Russian
// text would arrive as question marks. Since Windows 10 1903 a program can ask for UTF-8 instead with
// activeCodePage in its manifest. utf8Copy writes a copy of the program whose embedded manifest says so; the
// manifest is replaced in place by one of the same length, so nothing else in the file moves.
const sxsExitCode uint32 = 0xC0150002 // the side-by-side configuration (the manifest) is not accepted

const utf8Manifest = `<?xml version='1.0' encoding='UTF-8' standalone='yes'?><assembly xmlns='urn:schemas-microsoft-com:asm.v1' manifestVersion='1.0'><application xmlns='urn:schemas-microsoft-com:asm.v3'><windowsSettings><activeCodePage xmlns='http://schemas.microsoft.com/SMI/2019/WindowsSettings'>UTF-8</activeCodePage></windowsSettings></application></assembly>`

// patchManifestUTF8 returns the program with its manifest replaced by utf8Manifest (padded with spaces to the
// same length), or false if the program has no single plain manifest with enough room.
func patchManifestUTF8(b []byte) ([]byte, bool) {
	start := bytes.Index(b, []byte("<?xml"))
	open := bytes.Index(b, []byte("<assembly"))
	if start < 0 || open < start || open-start > 200 || bytes.Count(b, []byte("<assembly")) != 1 {
		return nil, false
	}
	end := bytes.Index(b[open:], []byte("</assembly>"))
	if end < 0 {
		return nil, false
	}
	end += open + len("</assembly>")
	old := b[start:end]
	if bytes.Contains(old, []byte("activeCodePage")) || len(utf8Manifest) > len(old) || bytes.IndexByte(old, 0) >= 0 {
		return nil, false
	}
	out := append([]byte{}, b...)
	copy(out[start:end], utf8Manifest+strings.Repeat(" ", len(old)-len(utf8Manifest)))
	return out, true
}

// utf8Copy returns the path of the UTF-8 copy of the program next to it, writing it when needed.
func utf8Copy(exe string) (string, error) {
	dst := strings.TrimSuffix(exe, filepath.Ext(exe)) + "-utf8" + filepath.Ext(exe)
	src, err := os.Stat(exe)
	if err != nil {
		return "", err
	}
	if st, err := os.Stat(dst); err == nil && st.Size() == src.Size() && !st.ModTime().Before(src.ModTime()) {
		return dst, nil
	}
	b, err := os.ReadFile(exe)
	if err != nil {
		return "", err
	}
	nb, ok := patchManifestUTF8(b)
	if !ok {
		return "", errors.New("no manifest to patch")
	}
	tmp := dst + ".tmp"
	if err := os.WriteFile(tmp, nb, 0o755); err != nil {
		return "", err
	}
	if err := os.Rename(tmp, dst); err != nil {
		_ = os.Remove(tmp)
		return "", err
	}
	return dst, nil
}

// ---------------------------------------------------------------- HTTP

func (a *App) ttsRoutes(mux *http.ServeMux) {
	// download a voice (and, the first time, sherpa-onnx); a downloaded voice is chosen for its language
	mux.HandleFunc("/api/voice", a.post(func(w http.ResponseWriter, r *http.Request) {
		var req struct{ ID string }
		_ = json.NewDecoder(io.LimitReader(r.Body, 4096)).Decode(&req)
		v := findVoice(req.ID)
		if v == nil {
			jsonError(w, 400, tr("неизвестный голос"))
			return
		}
		a.mu.Lock()
		present := a.voicePresent(v) && a.ttsExe() != ""
		if present {
			if a.cfg.Voices == nil {
				a.cfg.Voices = map[string]string{}
			}
			a.cfg.Voices[v.Lang] = v.ID
			a.saveConfig(a.cfg)
		}
		a.mu.Unlock()
		if !present {
			if err := a.startVoiceDownload(v); err != nil {
				jsonError(w, 409, err.Error())
				return
			}
		}
		writeJSON(w, 200, map[string]any{"ok": true})
	}))
	mux.HandleFunc("/api/voice-cancel", a.post(func(w http.ResponseWriter, r *http.Request) {
		a.mu.Lock()
		if a.vdlCancel != nil && a.vdl.Active {
			a.vdlCancel()
		}
		a.mu.Unlock()
		writeJSON(w, 200, map[string]any{"ok": true})
	}))
	mux.HandleFunc("/api/voice/", func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodDelete {
			jsonError(w, 405, "method not allowed")
			return
		}
		v := findVoice(strings.TrimPrefix(r.URL.Path, "/api/voice/"))
		if v == nil {
			jsonError(w, 404, tr("неизвестный голос"))
			return
		}
		a.mu.Lock()
		busy := a.vdl.Active && a.vdl.Name == v.ID
		a.mu.Unlock()
		if busy {
			jsonError(w, 409, tr("этот голос сейчас скачивается"))
			return
		}
		a.ttsMu.Lock() // not while it speaks
		err := os.RemoveAll(a.voiceDir(v))
		a.ttsMu.Unlock()
		if err != nil {
			jsonError(w, 500, tr("не удалось удалить файл: ")+err.Error())
			return
		}
		a.removeVoiceDownloads(v)
		a.mu.Lock()
		if a.cfg.Voices[v.Lang] == v.ID {
			delete(a.cfg.Voices, v.Lang)
			a.saveConfig(a.cfg)
		}
		a.mu.Unlock()
		logger.Printf("voice deleted: %s", v.Dir)
		writeJSON(w, 200, map[string]any{"ok": true})
	})
	// speak a text in a language with the voice chosen for it; the answer is a WAV file
	mux.HandleFunc("/api/tts", a.post(func(w http.ResponseWriter, r *http.Request) {
		var req struct {
			Lang  string  `json:"lang"`
			Text  string  `json:"text"`
			Speed float64 `json:"speed"`
		}
		if err := json.NewDecoder(io.LimitReader(r.Body, 64*1024)).Decode(&req); err != nil {
			jsonError(w, 400, tr("неверный запрос"))
			return
		}
		text := strings.TrimSpace(req.Text)
		if text == "" {
			jsonError(w, 400, tr("нет текста для чтения"))
			return
		}
		if utf8.RuneCountInString(text) > ttsMaxChars {
			jsonError(w, 400, tr("слишком длинный текст для чтения вслух"))
			return
		}
		speed := req.Speed
		if speed < 0.5 || speed > 2 {
			speed = 1
		}
		a.mu.Lock()
		exe := a.ttsExe()
		v := findVoice(a.activeVoiceID(req.Lang))
		a.mu.Unlock()
		if exe == "" || v == nil {
			jsonError(w, 409, tr("для этого языка нет скачанного голоса"))
			return
		}
		wav, err := a.synthesize(r.Context(), exe, v, text, speed)
		if err != nil {
			if r.Context().Err() != nil {
				return // the window does not need it any more
			}
			jsonError(w, 500, err.Error())
			return
		}
		w.Header().Set("Content-Type", "audio/wav")
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("X-Voice", v.ID)
		_, _ = w.Write(wav)
	}))
}

// cleanTTSLeftovers removes WAV files of phrases a previous run did not finish.
func (a *App) cleanTTSLeftovers() {
	files, _ := filepath.Glob(filepath.Join(a.voicesDir(), "tts-*.wav"))
	for _, f := range files {
		_ = os.Remove(f)
	}
}
