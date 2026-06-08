@echo off
REM FRA Sesh Launcher (built on Odysseus)
cd /d "C:\Users\info\OneDrive\Desktop\Claude-workspace\odysseus"
start "FRA Sesh" /min "C:\Users\info\OneDrive\Desktop\Claude-workspace\odysseus\venv\Scripts\python.exe" -m uvicorn app:app --host 127.0.0.1 --port 7000
echo Starting FRA Sesh...
:loop
timeout /t 2 /nobreak >nul
curl -s http://127.0.0.1:7000 >nul 2>&1
if errorlevel 1 goto loop
start http://127.0.0.1:7000
exit
