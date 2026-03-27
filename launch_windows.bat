@echo off
cd /d "%~dp0"
call venv\Scripts\activate.bat
python emit_gui.py
pause
