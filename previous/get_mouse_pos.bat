@echo off
set "PS=%SystemRoot%\System32\WindowsPowerShell\v1.0\powershell.exe"

if not exist "%PS%" (
    set "PS=%SystemRoot%\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
)

"%PS%" -NoProfile -ExecutionPolicy Bypass -Command "Add-Type -AssemblyName System.Windows.Forms; while ($true) { $p=[System.Windows.Forms.Cursor]::Position; Write-Host -NoNewline (\"`rX={0}  Y={1}      \" -f $p.X,$p.Y); Start-Sleep -Milliseconds 80 }"