@echo off
rem Fallback start without Ttranslator.exe: llama-server serves the interface itself.
rem The engine and the model must already be downloaded (run Ttranslator.exe once).
setlocal
chcp 65001 >nul
set "ROOT=%~dp0"
set "SERVER="
for /r "%ROOT%engine\windows-amd64" %%f in (llama-server.exe) do if exist "%%f" set "SERVER=%%f"
if not defined SERVER (
  echo Engine not found. Run Ttranslator.exe once to download it.
  pause
  exit /b 1
)
set "MODEL="
for %%m in (gemma-4-E2B_q4_0-it.gguf gemma-4-E2B-it-Q8_0.gguf gemma-4-E4B_q4_0-it.gguf gemma-4-E4B-it-Q8_0.gguf Hy-MT2-1.8B-Q4_K_M.gguf Hy-MT2-1.8B-Q8_0.gguf) do if not defined MODEL if exist "%ROOT%models\%%m" set "MODEL=%ROOT%models\%%m"
if not defined MODEL (
  echo Model not found in the models folder. Run Ttranslator.exe once to download it.
  pause
  exit /b 1
)
echo Ttranslator engine is starting. Keep this window open; close it to stop the translator.
start "" powershell -NoProfile -WindowStyle Hidden -Command "for($i=0;$i -lt 240;$i++){try{Invoke-WebRequest -UseBasicParsing http://127.0.0.1:8766/health -TimeoutSec 1 | Out-Null; Start-Process 'http://127.0.0.1:8766/'; break}catch{Start-Sleep -Milliseconds 500}}"
"%SERVER%" -m "%MODEL%" --host 127.0.0.1 --port 8766 -c 4096 -np 1 --jinja -cram 256 -rea off --path "%ROOT%ui"
