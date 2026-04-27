@echo off
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"

if not exist "%PS%" (
    set "PS=%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
)

if not exist "%PS%" (
    echo Cannot find Windows PowerShell.
    pause
    exit /b
)

start "" /high "%PS%" -NoProfile -ExecutionPolicy Bypass -File "%~dp0fish_auto.ps1"

exit