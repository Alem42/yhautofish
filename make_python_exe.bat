@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    py -3.12 -m venv .venv
    if errorlevel 1 exit /b %errorlevel%
)

".venv\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 exit /b %errorlevel%

".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 exit /b %errorlevel%

if not exist "models\easyocr\craft_mlt_25k.pth" (
    if exist "%USERPROFILE%\.EasyOCR\model\craft_mlt_25k.pth" (
        mkdir "models\easyocr" 2>nul
        copy /Y "%USERPROFILE%\.EasyOCR\model\craft_mlt_25k.pth" "models\easyocr\craft_mlt_25k.pth" >nul
    )
)

if not exist "models\easyocr\zh_sim_g2.pth" (
    if exist "%USERPROFILE%\.EasyOCR\model\zh_sim_g2.pth" (
        mkdir "models\easyocr" 2>nul
        copy /Y "%USERPROFILE%\.EasyOCR\model\zh_sim_g2.pth" "models\easyocr\zh_sim_g2.pth" >nul
    )
)

if not exist "models\easyocr\craft_mlt_25k.pth" (
    echo Missing models\easyocr\craft_mlt_25k.pth
    echo Put EasyOCR models in models\easyocr before packaging.
    exit /b 1
)

if not exist "models\easyocr\zh_sim_g2.pth" (
    echo Missing models\easyocr\zh_sim_g2.pth
    echo Put EasyOCR models in models\easyocr before packaging.
    exit /b 1
)

".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean FishAutoPython.spec
if errorlevel 1 exit /b %errorlevel%

echo.
echo Done.
echo Output: %CD%\dist\FishAutoPython\FishAutoPython.exe
if /I not "%~1"=="--no-pause" pause
