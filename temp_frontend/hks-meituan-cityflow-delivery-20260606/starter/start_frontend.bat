@echo off
cd /d "%~dp0..\frontend"
python -m http.server 5174 --bind 127.0.0.1
