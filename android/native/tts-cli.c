// Ttranslator for Android: the reading-aloud program.
//
// The launcher (source/launcher/tts.go) reads a phrase aloud by running sherpa-onnx-offline-tts with the arguments
// of ttsArgs. The official sherpa-onnx release for Android (sherpa-onnx-<version>-android.tar.bz2) has no such
// program, only libraries; this small program takes the same arguments and calls the C API of the official
// libsherpa-onnx-c-api.so (with libonnxruntime.so next to it). It is packed into the APK as
// libsherpa-onnx-offline-tts.so: Android starts programs of an app only from the app's library folder.
//
//   libsherpa-onnx-offline-tts.so --vits-model=DIR/MODEL --vits-tokens=DIR/tokens.txt
//       (--vits-data-dir=DIR/espeak-ng-data | --vits-lexicon=DIR/lexicon.txt [--tts-rule-fsts=A,B,C])
//       --num-threads=N --sid=N --speed=F --output-filename=OUT.wav -- TEXT
//
// Exit codes: 0 — the WAV file is written; 1 — the voice or the text could not be read; 2 — wrong arguments.

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "c-api.h"

static const char *opt(const char *arg, const char *name) {
  size_t n = strlen(name);
  if (strncmp(arg, "--", 2) == 0 && strncmp(arg + 2, name, n) == 0 && arg[2 + n] == '=') return arg + 3 + n;
  return NULL;
}

int main(int argc, char **argv) {
  const char *model = NULL, *tokens = NULL, *data_dir = NULL, *lexicon = NULL, *rules = NULL, *out = NULL;
  const char *text = NULL;
  int threads = 2, sid = 0;
  float speed = 1.0f;
  for (int i = 1; i < argc; i++) {
    const char *a = argv[i], *v;
    if (strcmp(a, "--") == 0) {
      if (i + 1 < argc) text = argv[i + 1];
      break;
    }
    if ((v = opt(a, "vits-model"))) model = v;
    else if ((v = opt(a, "vits-tokens"))) tokens = v;
    else if ((v = opt(a, "vits-data-dir"))) data_dir = v;
    else if ((v = opt(a, "vits-lexicon"))) lexicon = v;
    else if ((v = opt(a, "tts-rule-fsts"))) rules = v;
    else if ((v = opt(a, "num-threads"))) threads = atoi(v);
    else if ((v = opt(a, "sid"))) sid = atoi(v);
    else if ((v = opt(a, "speed"))) speed = (float)atof(v);
    else if ((v = opt(a, "output-filename"))) out = v;
    else if (a[0] == '-' && a[1] == '-') {
      fprintf(stderr, "unknown option: %s\n", a);
      return 2;
    } else if (!text) text = a; // like sherpa-onnx-offline-tts: the text may also come without "--"
  }
  if (!model || !tokens || !out || !text || !*text) {
    fprintf(stderr, "usage: %s --vits-model=M --vits-tokens=T (--vits-data-dir=D | --vits-lexicon=L) "
                    "[--tts-rule-fsts=F] [--num-threads=N] [--sid=N] [--speed=F] --output-filename=O.wav -- TEXT\n",
            argv[0]);
    return 2;
  }
  if (threads < 1) threads = 1;
  if (speed <= 0) speed = 1.0f;

  // zero fields get the defaults of the library (the same as those of sherpa-onnx-offline-tts)
  SherpaOnnxOfflineTtsConfig config;
  memset(&config, 0, sizeof(config));
  config.model.vits.model = model;
  config.model.vits.tokens = tokens;
  config.model.vits.data_dir = data_dir ? data_dir : "";
  config.model.vits.lexicon = lexicon ? lexicon : "";
  config.model.num_threads = threads;
  config.model.provider = "cpu";
  config.rule_fsts = rules ? rules : "";
  config.max_num_sentences = 1;

  const SherpaOnnxOfflineTts *tts = SherpaOnnxCreateOfflineTts(&config);
  if (!tts) {
    fprintf(stderr, "the voice could not be loaded: %s\n", model);
    return 1;
  }
  SherpaOnnxGenerationConfig gen;
  memset(&gen, 0, sizeof(gen));
  gen.sid = sid;
  gen.speed = speed;
  const SherpaOnnxGeneratedAudio *audio = SherpaOnnxOfflineTtsGenerateWithConfig(tts, text, &gen, NULL, NULL);
  if (!audio || audio->n <= 0) {
    fprintf(stderr, "no speech was generated\n");
    if (audio) SherpaOnnxDestroyOfflineTtsGeneratedAudio(audio);
    SherpaOnnxDestroyOfflineTts(tts);
    return 1;
  }
  int ok = SherpaOnnxWriteWave(audio->samples, audio->n, audio->sample_rate, out);
  printf("%d samples, %d Hz, %.2f s\n", audio->n, audio->sample_rate, (double)audio->n / audio->sample_rate);
  SherpaOnnxDestroyOfflineTtsGeneratedAudio(audio);
  SherpaOnnxDestroyOfflineTts(tts);
  if (!ok) {
    fprintf(stderr, "the file could not be written: %s\n", out);
    return 1;
  }
  return 0;
}
