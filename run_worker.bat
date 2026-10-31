@echo off
REM Worker flynotify (da lanciare con Windows Task Scheduler ogni ~30 min)
cd /d D:\webserver\apache24\flynotify
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
if not exist logs mkdir logs
python -m app.worker >> logs\worker.log 2>&1
