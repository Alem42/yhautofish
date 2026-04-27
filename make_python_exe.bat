@echo off
setlocal
cd /d "%~dp0"

py -3.9 -m PyInstaller --clean --onefile --console --uac-admin --name FishAutoPython autofish.py

echo.
echo Done.
echo Output: %CD%\dist\YhFishAuto.exe
pause
