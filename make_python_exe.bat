@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt
".venv\Scripts\python.exe" -m PyInstaller --clean --onedir --console --uac-admin --name FishAutoPython autofish.py

echo.
echo Done.
echo Output: %CD%\dist\FishAutoPython\FishAutoPython.exe
pause
