@echo off
setlocal
cd /d "%~dp0"

py -3.9 get_scaled_mouse_pos.py

pause
