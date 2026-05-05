@echo off
setlocal
cd /d "%~dp0"

echo Press F12 in the tool window to append one capture point to a CSV file.
echo The file will be created under the captures folder in this project.
echo.

py -3.9 get_scaled_mouse_pos.py

pause
