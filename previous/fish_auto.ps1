# =====================
# Ŀ�괰�ڱ���
# ��ͼ����Ϸ���ڱ����ǡ��컷��
# =====================
$TargetTitleKeyword = "�컷"

# =====================
# ��߽ű��������ȼ�
# =====================
try {
    (Get-Process -Id $PID).PriorityClass = "High"
} catch {
    Write-Host "Failed to set process priority. Continue normally."
}

Add-Type @"
using System;
using System.Text;
using System.Runtime.InteropServices;

public class WinAPI {
    public delegate bool EnumWindowsProc(IntPtr hWnd, IntPtr lParam);

    [DllImport("user32.dll")]
    public static extern bool EnumWindows(EnumWindowsProc lpEnumFunc, IntPtr lParam);

    [DllImport("user32.dll")]
    public static extern int GetWindowText(IntPtr hWnd, StringBuilder lpString, int nMaxCount);

    [DllImport("user32.dll")]
    public static extern bool IsWindowVisible(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool SetForegroundWindow(IntPtr hWnd);

    [DllImport("user32.dll")]
    public static extern bool ShowWindow(IntPtr hWnd, int nCmdShow);

    [DllImport("user32.dll")]
    public static extern short GetAsyncKeyState(int vKey);

    [DllImport("user32.dll")]
    public static extern bool SetCursorPos(int X, int Y);

    [DllImport("user32.dll")]
    public static extern void mouse_event(int dwFlags, int dx, int dy, int dwData, int dwExtraInfo);

    [DllImport("user32.dll")]
    public static extern void keybd_event(byte bVk, byte bScan, int dwFlags, int dwExtraInfo);

    public const int SW_RESTORE = 9;
    public const int KEYEVENTF_KEYUP = 0x0002;
    public const int MOUSEEVENTF_LEFTDOWN = 0x0002;
    public const int MOUSEEVENTF_LEFTUP = 0x0004;
}
"@

# =====================
# ��������
# =====================
$VK_F = 0x46
$VK_ESC = 0x1B
$VK_F10 = 0x79
$VK_F12 = 0x7B

# =====================
# ��������
# =====================
function DelayMs($ms) {
    Start-Sleep -Milliseconds $ms
}

function IsKeyPressed($vk) {
    return ([WinAPI]::GetAsyncKeyState($vk) -band 0x8000) -ne 0
}

function CheckStop {
    if (IsKeyPressed $VK_F12) {
        Write-Host "F12 detected. Script stopped."
        exit
    }
}

function SafeDelay($ms) {
    $step = 50
    $elapsed = 0

    while ($elapsed -lt $ms) {
        CheckStop
        DelayMs $step
        $elapsed += $step
    }
}

function KeyDown($vk) {
    [WinAPI]::keybd_event([byte]$vk, 0, 0, 0)
}

function KeyUp($vk) {
    [WinAPI]::keybd_event([byte]$vk, 0, [WinAPI]::KEYEVENTF_KEYUP, 0)
}

function PressKey($vk, $holdMs = 110) {
    KeyDown $vk
    DelayMs $holdMs
    KeyUp $vk
}

function MoveTo($x, $y) {
    [WinAPI]::SetCursorPos($x, $y) | Out-Null
}

function LeftClick() {
    [WinAPI]::mouse_event([WinAPI]::MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    DelayMs 50
    [WinAPI]::mouse_event([WinAPI]::MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
}

# =====================
# ���Ҵ���
# =====================
function Get-WindowByTitleKeyword($keyword) {
    $script:FoundHwnd = [IntPtr]::Zero

    $callback = {
        param($hWnd, $lParam)

        if (-not [WinAPI]::IsWindowVisible($hWnd)) {
            return $true
        }

        $sb = New-Object System.Text.StringBuilder 512
        [void][WinAPI]::GetWindowText($hWnd, $sb, $sb.Capacity)
        $title = $sb.ToString()

        if ($title -like "*$keyword*") {
            $script:FoundHwnd = $hWnd
            return $false
        }

        return $true
    }

    [void][WinAPI]::EnumWindows($callback, [IntPtr]::Zero)
    return $script:FoundHwnd
}

function ActivateGameWindow {
    $hwnd = Get-WindowByTitleKeyword $TargetTitleKeyword

    if ($hwnd -eq [IntPtr]::Zero) {
        Write-Host "Cannot find game window with title keyword: $TargetTitleKeyword"
        return $false
    }

    [WinAPI]::ShowWindow($hwnd, [WinAPI]::SW_RESTORE) | Out-Null
    SafeDelay 100
    [WinAPI]::SetForegroundWindow($hwnd) | Out-Null
    SafeDelay 300

    return $true
}

# =====================
# ���ֶ���
# =====================
function RunOnce {
    ActivateGameWindow | Out-Null

    SafeDelay 500

    PressKey $VK_F 110

    SafeDelay 110

    MoveTo 34 615

    SafeDelay 7000

    ActivateGameWindow | Out-Null
    PressKey $VK_F 110

    SafeDelay 400

    MoveTo 34 615
    LeftClick

    SafeDelay 8000

    MoveTo 1058 621
    LeftClick

    SafeDelay 300

    PressKey $VK_ESC 110
}

Clear-Host
Write-Host "Ready."
Write-Host "Target window keyword: $TargetTitleKeyword"
Write-Host "Press F10 to start."
Write-Host "Press F12 to stop."
Write-Host ""

# =====================
# �ȴ� F10
# =====================
while ($true) {
    if (IsKeyPressed $VK_F10) {
        Write-Host "F10 detected. Script started."
        SafeDelay 500
        break
    }

    if (IsKeyPressed $VK_F12) {
        Write-Host "F12 detected. Script exited."
        exit
    }

    DelayMs 50
}

# =====================
# ѭ��ִ��
# =====================
while ($true) {
    CheckStop
    RunOnce
}