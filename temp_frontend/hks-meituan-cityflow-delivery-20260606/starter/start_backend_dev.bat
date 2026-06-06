@echo off
cd /d "%~dp0..\frontend"
python -m uvicorn dev_backend:app --host 127.0.0.1 --port 8000
