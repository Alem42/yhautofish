# -*- coding: utf-8 -*-

import ctypes
import sys
import time
from ctypes import wintypes


# ===== Config =====
TARGET_TITLE_KEYWORD = "\u5f02\u73af"
LOG_ENABLED = True

# Coordinates from the original macro, measured on a 1920x1080 game client.
# They are scaled to the current game window client size at runtime.
REFERENCE_WIDTH = 1920
REFERENCE_HEIGHT = 1080
LEFT_CLICK_REF_X = 89
LEFT_CLICK_REF_Y = 1085
RIGHT_CLICK_REF_X = 1900
RIGHT_CLICK_REF_Y = 1085

# Click the game content once before the loop starts sending keys.
FOCUS_CENTER_BEFORE_ACTION = True

VK_F = 0x46
VK_ESC = 0x1B
VK_F10 = 0x79
VK_F12 = 0x7B

SW_RESTORE = 9
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004


# ===== WinAPI =====
user32 = ctypes.WinDLL("user32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)

EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
user32.EnumWindows.restype = wintypes.BOOL
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.restype = ctypes.c_int
user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
user32.GetWindowTextW.restype = ctypes.c_int
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
user32.ShowWindow.restype = wintypes.BOOL
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.GetForegroundWindow.argtypes = []
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetClientRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetClientRect.restype = wintypes.BOOL
user32.ClientToScreen.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.ClientToScreen.restype = wintypes.BOOL
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL
user32.mouse_event.argtypes = [ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_uint, ctypes.c_ulong]
user32.keybd_event.argtypes = [ctypes.c_ubyte, ctypes.c_ubyte, ctypes.c_uint, ctypes.c_ulong]


try:
    user32.SetProcessDPIAware()
except Exception:
    pass


def delay(ms):
    time.sleep(ms / 1000.0)


def log(message):
    if LOG_ENABLED:
        now = time.strftime("%H:%M:%S")
        print(f"[{now}] {message}", flush=True)


def is_admin():
    try:
        return bool(shell32.IsUserAnAdmin())
    except Exception:
        return False


def is_pressed(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def stop_requested():
    return is_pressed(VK_F12)


def wait(ms):
    """Delay in small steps, so F12 can stop quickly."""
    log(f"Wait {ms}ms")
    end = time.perf_counter() + ms / 1000.0
    while time.perf_counter() < end:
        if stop_requested():
            log("F12 detected")
            raise KeyboardInterrupt
        delay(50)


def key_down(vk):
    user32.keybd_event(vk, 0, 0, 0)


def key_up(vk):
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)


def press_key(vk, hold_ms=110):
    log(f"Key down: vk={vk}")
    key_down(vk)
    delay(hold_ms)
    log(f"Key up: vk={vk}")
    key_up(vk)


def move_to(x, y):
    log(f"MoveTo {x}, {y}")
    user32.SetCursorPos(x, y)


def left_click():
    log("LeftClick down")
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    delay(50)
    log("LeftClick up")
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)


def click_at(x, y):
    move_to(x, y)
    left_click()


def get_client_rect(hwnd):
    rect = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rect)):
        raise RuntimeError("GetClientRect failed")
    return rect


def client_to_screen(hwnd, x, y):
    point = wintypes.POINT(int(round(x)), int(round(y)))
    if not user32.ClientToScreen(hwnd, ctypes.byref(point)):
        raise RuntimeError("ClientToScreen failed")
    return point.x, point.y


def scaled_client_point(hwnd, ref_x, ref_y):
    rect = get_client_rect(hwnd)
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    client_x = ref_x * width / REFERENCE_WIDTH
    client_y = ref_y * height / REFERENCE_HEIGHT
    screen_x, screen_y = client_to_screen(hwnd, client_x, client_y)
    log(
        f"Scaled point ref=({ref_x},{ref_y}) "
        f"client=({client_x:.1f},{client_y:.1f}) "
        f"screen=({screen_x},{screen_y}) size=({width}x{height})"
    )
    return screen_x, screen_y


def click_client_center(hwnd):
    rect = get_client_rect(hwnd)
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    x, y = client_to_screen(hwnd, width / 2, height / 2)
    log(f"Focus game client center: {x}, {y}")
    click_at(x, y)


def window_title(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""

    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def find_window(keyword):
    log(f"Find window by title keyword: {keyword}")
    found = None

    @EnumWindowsProc
    def callback(hwnd, lparam):
        nonlocal found
        if user32.IsWindowVisible(hwnd):
            title = window_title(hwnd)
            if keyword in title:
                found = hwnd
                return False
        return True

    user32.EnumWindows(callback, 0)
    return found


def activate_window():
    hwnd = find_window(TARGET_TITLE_KEYWORD)
    if not hwnd:
        log(f"Cannot find window: {TARGET_TITLE_KEYWORD}")
        return False

    log(f"Using window: {window_title(hwnd)}")
    log("ShowWindow restore")
    user32.ShowWindow(hwnd, SW_RESTORE)
    delay(100)

    ok = user32.SetForegroundWindow(hwnd)
    log(f"SetForegroundWindow result: {bool(ok)}")
    delay(300)

    foreground = user32.GetForegroundWindow()
    log(f"Foreground hwnd matched: {foreground == hwnd}")
    return hwnd


def fish_once():
    log("=== New loop ===")
    hwnd = activate_window()
    if not hwnd:
        wait(1000)
        return

    if FOCUS_CENTER_BEFORE_ACTION:
        click_client_center(hwnd)
        wait(300)

    wait(500)
    log("First F")
    press_key(VK_F, 110)

    wait(7000)
    log("Second F")
    press_key(VK_F, 110)

    wait(400)
    log("Click left target")
    click_at(*scaled_client_point(hwnd, LEFT_CLICK_REF_X, LEFT_CLICK_REF_Y))

    wait(8000)
    log("Click right target")
    click_at(*scaled_client_point(hwnd, RIGHT_CLICK_REF_X, RIGHT_CLICK_REF_Y))

    wait(400)
    log("Press Esc")
    press_key(VK_ESC, 110)


def wait_for_start():
    log("Ready.")
    log(f"Admin: {is_admin()}")
    log(f"Target window keyword: {TARGET_TITLE_KEYWORD}")
    log("Press F10 to start, F12 to stop.")

    while True:
        if is_pressed(VK_F12):
            return False
        if is_pressed(VK_F10):
            log("Started.")
            wait(500)
            return True
        delay(50)


def main():
    if not wait_for_start():
        return

    try:
        while True:
            if stop_requested():
                break
            fish_once()
    except KeyboardInterrupt:
        pass

    log("Stopped.")


if __name__ == "__main__":
    sys.exit(main())
