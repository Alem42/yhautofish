# -*- coding: utf-8 -*-

import ctypes
import logging
import os
import sys
import threading
import time
from ctypes import wintypes


# ===== Config =====
TARGET_TITLE_KEYWORD = "\u5f02\u73af"
LOG_ENABLED = True
LOG_FILE = "logs/autofish.log"
OCR_ENABLED = True
OCR_GPU_MODE = "auto"
OCR_TARGET_TEXT = "\u5411\u5de6\u6e9c\u9c7c"
OCR_BITE_KEYWORDS = (
    "\u9c7c\u4e0a\u94a9",
    "\u4e0a\u94a9",
)
OCR_CLOSE_KEYWORDS = (
    "\u70b9\u51fb\u7a7a\u767d\u533a\u57df\u5173\u95ed",
    "\u70b9\u51fb\u7a7a\u767d",
    "\u7a7a\u767d\u533a\u57df",
    "\u533a\u57df\u5173\u95ed",
)
OCR_START_FISH_TEXT = "\u5f00\u59cb\u9493\u9c7c"       # "开始钓鱼"
OCR_LOST_FISH_TEXT = "\u9c7c\u513f\u6e9c\u8d70\u4e86"
OCR_INTERVAL_MS = 1000
OCR_PRINT_COOLDOWN_MS = 2000
# OCR regions are based on a 1920x1080 client reference. They are split by
# purpose so each event is only triggered by the UI area that should contain it.
OCR_BITE_REGIONS_REF = (
    (450, 120, 1020, 520),
    (620, 850, 1300, 1060),
)
OCR_CLOSE_REGIONS_REF = (
    (620, 850, 1300, 1060),
)
OCR_LOST_FISH_REGION_REF = (480, 500, 1440, 660)
OCR_START_FISH_REGION_REF = (1350, 800, 1820, 1030)
BITE_WAIT_TIMEOUT_MS = 20000
CLOSE_WAIT_TIMEOUT_MS = 15000
OCR_READY_TIMEOUT_MS = 60000
START_FISH_CLICK_REF_X = 1600
START_FISH_CLICK_REF_Y = 940

# Coordinates from the original macro, measured on a 1920x1080 game client.
# They are scaled to the current game window client size at runtime.
REFERENCE_WIDTH = 1920
REFERENCE_HEIGHT = 1080
LEFT_CLICK_REF_X = 60
LEFT_CLICK_REF_Y = 1020
RIGHT_CLICK_REF_X = 1880
RIGHT_CLICK_REF_Y = 1040

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

OCR_READY_EVENT = threading.Event()
BITE_DETECTED_EVENT = threading.Event()
CLOSE_DETECTED_EVENT = threading.Event()
START_FISH_DETECTED_EVENT = threading.Event()
LOST_FISH_DETECTED_EVENT = threading.Event()
LAST_OCR_TEXT_LOCK = threading.Lock()
LAST_OCR_TEXT = ""


class RestartLoop(Exception):
    pass


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


def setup_logging():
    log_dir = os.path.dirname(LOG_FILE)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(threadName)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(LOG_FILE, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
        force=True,
    )


def delay(ms):
    time.sleep(ms / 1000.0)


def log(message):
    if LOG_ENABLED:
        logging.info(message)


def is_admin():
    try:
        return bool(shell32.IsUserAnAdmin())
    except Exception:
        return False


def is_pressed(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def stop_requested():
    return is_pressed(VK_F12)


def maybe_restart_from_start_fishing():
    if not START_FISH_DETECTED_EVENT.is_set():
        return

    log(f"Start fishing text detected: {get_last_ocr_text()}")
    START_FISH_DETECTED_EVENT.clear()
    BITE_DETECTED_EVENT.clear()
    CLOSE_DETECTED_EVENT.clear()
    hwnd = find_window(TARGET_TITLE_KEYWORD, announce=False)
    if not hwnd:
        log("Start fishing click skipped because target window was not found.")
        return

    # The button lives inside the game client, so the reference point must be
    # scaled to the current client rect before we click it.
    click_at(*scaled_client_point(hwnd, START_FISH_CLICK_REF_X, START_FISH_CLICK_REF_Y))
    delay(300)
    raise RestartLoop


def maybe_restart_from_lost_fish(stop_event=None):
    if not LOST_FISH_DETECTED_EVENT.is_set():
        return

    log(f"Lost fish text detected: {get_last_ocr_text()}")
    BITE_DETECTED_EVENT.clear()
    CLOSE_DETECTED_EVENT.clear()

    # Keep waiting until the center banner disappears, then restart the main
    # fishing loop from the beginning.
    while LOST_FISH_DETECTED_EVENT.is_set():
        if stop_event is not None and stop_event.is_set():
            raise KeyboardInterrupt
        if stop_requested():
            log("F12 detected")
            if stop_event is not None:
                stop_event.set()
            raise KeyboardInterrupt
        delay(50)

    log("Lost fish text cleared; restart main loop.")
    raise RestartLoop


def maybe_restart_from_ocr_events(stop_event=None):
    maybe_restart_from_start_fishing()
    maybe_restart_from_lost_fish(stop_event)


def wait(ms, stop_event=None):
    """Delay in small steps, so F12 can stop quickly."""
    log(f"Wait {ms}ms")
    end = time.perf_counter() + ms / 1000.0
    while time.perf_counter() < end:
        if stop_event is not None and stop_event.is_set():
            raise KeyboardInterrupt
        if stop_requested():
            log("F12 detected")
            if stop_event is not None:
                stop_event.set()
            raise KeyboardInterrupt
        maybe_restart_from_ocr_events(stop_event)
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


def find_window(keyword, announce=True):
    if announce:
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


def ref_region_to_screen(hwnd, ref_region):
    rect = get_client_rect(hwnd)
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    ref_left, ref_top, ref_right, ref_bottom = ref_region
    client_left = ref_left * width / REFERENCE_WIDTH
    client_top = ref_top * height / REFERENCE_HEIGHT
    client_right = ref_right * width / REFERENCE_WIDTH
    client_bottom = ref_bottom * height / REFERENCE_HEIGHT
    screen_left, screen_top = client_to_screen(hwnd, client_left, client_top)
    screen_right, screen_bottom = client_to_screen(hwnd, client_right, client_bottom)
    return screen_left, screen_top, screen_right, screen_bottom


def capture_client_image(hwnd, ref_region=None):
    import mss
    import numpy as np

    if ref_region:
        left, top, right, bottom = ref_region_to_screen(hwnd, ref_region)
        width = max(1, right - left)
        height = max(1, bottom - top)
    else:
        rect = get_client_rect(hwnd)
        width = rect.right - rect.left
        height = rect.bottom - rect.top
        left, top = client_to_screen(hwnd, 0, 0)

    log(f"OCR capture region screen=({left},{top},{width},{height})")

    with mss.mss() as sct:
        shot = sct.grab({
            "left": left,
            "top": top,
            "width": width,
            "height": height,
        })

    # EasyOCR expects RGB image data. MSS returns BGRA.
    return np.asarray(shot)[:, :, :3][:, :, ::-1]


def text_seen(result, target):
    return target in normalize_text(format_ocr_result(result))


def normalize_text(text):
    ignored = set(" \t\r\n,，.。!！?？:：;；|/\\-_—[]()（）{}<>《》\"'`")
    return "".join(ch for ch in str(text) if ch not in ignored)


def text_seen_any(text, keywords):
    normalized = normalize_text(text)
    return any(keyword in normalized for keyword in keywords)


def text_seen_exact(text, target):
    return normalize_text(text) == normalize_text(target)


def set_last_ocr_text(text):
    global LAST_OCR_TEXT
    with LAST_OCR_TEXT_LOCK:
        LAST_OCR_TEXT = text


def get_last_ocr_text():
    with LAST_OCR_TEXT_LOCK:
        return LAST_OCR_TEXT


def format_ocr_result(result):
    cleaned = [str(text).strip() for text in result if str(text).strip()]
    return " | ".join(cleaned)


def read_ocr_regions(reader, hwnd):
    texts = []
    for region in OCR_BITE_REGIONS_REF:
        image = capture_client_image(hwnd, region)
        result = reader.readtext(image, detail=0, paragraph=True)
        text = format_ocr_result(result)
        if text:
            texts.append(text)
    return " | ".join(texts)


def read_ocr_region(reader, hwnd, region):
    image = capture_client_image(hwnd, region)
    result = reader.readtext(image, detail=0, paragraph=True)
    return format_ocr_result(result)


def wait_for_ocr_ready(stop_event):
    if not OCR_ENABLED:
        log("OCR disabled; skip waiting for OCR model.")
        return False

    log("Wait for OCR model ready.")
    end = time.perf_counter() + OCR_READY_TIMEOUT_MS / 1000.0
    while time.perf_counter() < end:
        if stop_event.is_set() or stop_requested():
            stop_event.set()
            raise KeyboardInterrupt
        if OCR_READY_EVENT.is_set():
            log("OCR model ready; action loop can start.")
            return True
        delay(100)

    log("OCR model ready timeout; continue with timeout fallback.")
    return False


def wait_for_bite_text(stop_event):
    log("Wait until OCR sees bite text.")
    end = time.perf_counter() + BITE_WAIT_TIMEOUT_MS / 1000.0
    while time.perf_counter() < end:
        if stop_event.is_set() or stop_requested():
            stop_event.set()
            raise KeyboardInterrupt
        maybe_restart_from_ocr_events(stop_event)
        if BITE_DETECTED_EVENT.is_set():
            log(f"Bite text detected: {get_last_ocr_text()}")
            BITE_DETECTED_EVENT.clear()
            return True
        delay(50)

    log(f"Bite text timeout; last OCR text: {get_last_ocr_text()}")
    return False


def wait_for_close_text(stop_event):
    log("Wait until OCR sees close text.")
    end = time.perf_counter() + CLOSE_WAIT_TIMEOUT_MS / 1000.0
    while time.perf_counter() < end:
        if stop_event.is_set() or stop_requested():
            stop_event.set()
            raise KeyboardInterrupt
        maybe_restart_from_ocr_events(stop_event)
        if CLOSE_DETECTED_EVENT.is_set():
            log(f"Close text detected: {get_last_ocr_text()}")
            CLOSE_DETECTED_EVENT.clear()
            return True
        delay(50)

    log(f"Close text timeout; last OCR text: {get_last_ocr_text()}")
    return False


def should_use_ocr_gpu():
    if OCR_GPU_MODE is True:
        return True
    if OCR_GPU_MODE is False:
        return False
    if str(OCR_GPU_MODE).lower() != "auto":
        return False

    try:
        import torch

        available = torch.cuda.is_available()
        if available:
            log(f"OCR GPU available: {torch.cuda.get_device_name(0)}")
        else:
            log(f"OCR GPU unavailable; torch={torch.__version__}")
        return available
    except Exception as exc:
        log(f"OCR GPU check failed: {exc}")
        return False


def ocr_loop(stop_event):
    if not OCR_ENABLED:
        return

    try:
        import easyocr

        log("OCR thread loading EasyOCR model...")
        use_gpu = should_use_ocr_gpu()
        log(f"OCR EasyOCR gpu={use_gpu}")
        reader = easyocr.Reader(["ch_sim", "en"], gpu=use_gpu)
        log("OCR thread ready.")
        OCR_READY_EVENT.set()

        last_print = 0
        while not stop_event.is_set():
            hwnd = find_window(TARGET_TITLE_KEYWORD, announce=False)
            if hwnd:
                bite_text = read_ocr_regions(reader, hwnd)
                close_text = read_ocr_region(reader, hwnd, OCR_CLOSE_REGIONS_REF[0])
                lost_fish_text = read_ocr_region(reader, hwnd, OCR_LOST_FISH_REGION_REF)
                start_fish_text = read_ocr_region(reader, hwnd, OCR_START_FISH_REGION_REF)

                # Keep one merged OCR snapshot for logging/debugging, but make
                # each event depend on its own dedicated UI region.
                text = " | ".join(
                    part for part in (bite_text, close_text, lost_fish_text, start_fish_text) if part
                )
                set_last_ocr_text(text)

                seen = OCR_TARGET_TEXT in normalize_text(bite_text)
                bite_seen = text_seen_any(bite_text, OCR_BITE_KEYWORDS)
                close_seen = text_seen_any(close_text, OCR_CLOSE_KEYWORDS)
                lost_fish_seen = text_seen_exact(lost_fish_text, OCR_LOST_FISH_TEXT)
                start_fish_seen = (
                    normalize_text(OCR_START_FISH_TEXT) in normalize_text(start_fish_text)
                )
                if bite_seen:
                    BITE_DETECTED_EVENT.set()
                if close_seen:
                    CLOSE_DETECTED_EVENT.set()
                if lost_fish_seen:
                    LOST_FISH_DETECTED_EVENT.set()
                else:
                    LOST_FISH_DETECTED_EVENT.clear()
                if start_fish_seen:
                    START_FISH_DETECTED_EVENT.set()

                if text:
                    now = time.perf_counter()
                    if (now - last_print) * 1000 >= OCR_PRINT_COOLDOWN_MS:
                        if start_fish_seen:
                            status = "START"
                        elif lost_fish_seen:
                            status = "LOST"
                        elif close_seen:
                            status = "CLOSE"
                        elif bite_seen:
                            status = "BITE"
                        elif seen:
                            status = "MATCH"
                        else:
                            status = "TEXT"
                        log(f"OCR {status}: {text}")
                        last_print = now

            stop_event.wait(OCR_INTERVAL_MS / 1000.0)
    except Exception as exc:
        logging.exception("OCR thread stopped by error: %s", exc)
        OCR_READY_EVENT.set()
        log("OCR disabled for this run; action loop will continue.")


def fish_once(stop_event):
    log("=== New loop ===")
    maybe_restart_from_ocr_events(stop_event)
    hwnd = activate_window()
    if not hwnd:
        wait(1000, stop_event)
        return

    if FOCUS_CENTER_BEFORE_ACTION:
        # Ensure the game client has focus before sending keyboard input.
        click_client_center(hwnd)
        wait(300, stop_event)

    # Main fishing cycle. Any wait below can be interrupted by OCR if the
    # bottom-right "开始钓鱼" button appears again.
    wait(500, stop_event)
    log("First F")
    BITE_DETECTED_EVENT.clear()
    press_key(VK_F, 110)

    wait_for_bite_text(stop_event)
    maybe_restart_from_ocr_events(stop_event)
    log("Second F")
    press_key(VK_F, 110)


    wait(650, stop_event)
    maybe_restart_from_ocr_events(stop_event)
    log("Click left target")
    CLOSE_DETECTED_EVENT.clear()
    click_at(*scaled_client_point(hwnd, LEFT_CLICK_REF_X, LEFT_CLICK_REF_Y))
    

    if wait_for_close_text(stop_event):
        log("Click right target")
        click_at(*scaled_client_point(hwnd, RIGHT_CLICK_REF_X, RIGHT_CLICK_REF_Y))
    else:
        log("Close text timeout; skip right target click.")

    wait(400, stop_event)
    maybe_restart_from_ocr_events(stop_event)
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
            return True
        delay(50)


def action_loop(stop_event):
    try:
        wait_for_ocr_ready(stop_event)
        while not stop_event.is_set():
            if stop_requested():
                stop_event.set()
                break
            try:
                fish_once(stop_event)
            except RestartLoop:
                log("Restart requested; return to autofish loop start.")
                continue
    except KeyboardInterrupt:
        stop_event.set()
    except Exception as exc:
        logging.exception("Action thread stopped by error: %s", exc)
        stop_event.set()


def main():
    setup_logging()
    log("Log file: " + os.path.abspath(LOG_FILE))

    if not wait_for_start():
        return

    stop_event = threading.Event()
    threads = [
        threading.Thread(target=ocr_loop, args=(stop_event,), name="OCR"),
        threading.Thread(target=action_loop, args=(stop_event,), name="Action"),
    ]

    for thread in threads:
        thread.start()

    try:
        while not stop_event.is_set():
            if stop_requested():
                log("F12 detected in main thread")
                stop_event.set()
                break
            delay(50)
    except KeyboardInterrupt:
        stop_event.set()
    except Exception as exc:
        logging.exception("Main thread stopped by error: %s", exc)
        stop_event.set()

    for thread in threads:
        thread.join()

    log("Stopped.")


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        setup_logging()
        logging.exception("Fatal error: %s", exc)
        raise
