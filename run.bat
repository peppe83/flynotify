@echo off
REM Avvio del server web flynotify (sviluppo)
cd /d D:\webserver\apache24\flynotify
if exist .venv\Scripts\activate.bat call .venv\Scripts\activate.bat
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
