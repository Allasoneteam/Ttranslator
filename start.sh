#!/bin/sh
# Fallback start without the launcher: llama-server serves the interface itself.
# The engine and the model must already be downloaded (run ./ttranslator-linux once).
cd "$(dirname "$0")" || exit 1
SERVER=$(find engine/linux-amd64 -name llama-server -type f 2>/dev/null | head -n 1)
if [ -z "$SERVER" ]; then
  echo "Engine not found. Run ./ttranslator-linux once to download it."
  exit 1
fi
MODEL=""
for f in models/gemma-4-E2B_q4_0-it.gguf models/gemma-4-E2B-it-Q8_0.gguf models/gemma-4-E4B_q4_0-it.gguf models/gemma-4-E4B-it-Q8_0.gguf \
         models/Hy-MT2-1.8B-Q4_K_M.gguf models/Hy-MT2-1.8B-Q8_0.gguf; do
  if [ -f "$f" ]; then MODEL="$f"; break; fi
done
if [ -z "$MODEL" ]; then
  echo "Model not found in the models folder. Run ./ttranslator-linux once to download it."
  exit 1
fi
(
  i=0
  while [ $i -lt 240 ]; do
    if curl -sf -o /dev/null http://127.0.0.1:8766/health; then
      xdg-open http://127.0.0.1:8766/ >/dev/null 2>&1
      break
    fi
    sleep 0.5
    i=$((i + 1))
  done
) &
echo "Ttranslator engine is starting. Press Ctrl+C to stop."
LD_LIBRARY_PATH="$(dirname "$SERVER")" exec "$SERVER" -m "$MODEL" --host 127.0.0.1 --port 8766 -c 4096 -np 1 --jinja -cram 256 -rea off --path ui
