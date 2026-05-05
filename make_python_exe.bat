@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
    if errorlevel 1 exit /b %errorlevel%
)

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b %errorlevel%

".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onedir --console --uac-admin --name FishAutoPython autofish.py
if errorlevel 1 exit /b %errorlevel%

echo.
echo Done.
echo Output: %CD%\dist\FishAutoPython\FishAutoPython.exe
pause
