# -*- coding: utf-8 -*-
"""
Main automation entrypoint.

Static values such as OCR regions, timing knobs, key codes, and reference
coordinates live in config.py. This file keeps runtime state and behavior:
window control, OCR execution, visual fishing-bar tracking, and flow logic.
"""

import ctypes
import logging
import os
import sys
import threading
import time
from ctypes import wintypes

from config import *  # Static script configuration; runtime state remains here.
from ocr_utils import (
    bite_text_seen,
    empty_ocr_snapshot,
    format_ocr_result,
    need_bait_text_seen,
    normalize_text,
    read_easyocr_text,
    read_ocr_fast_snapshot,
    read_ocr_region,
    read_ocr_regions,
    read_result_overlay_text,
    result_overlay_text_seen,
    text_seen_any,
    text_seen_exact,
)

# Cross-thread runtime state shared by the OCR thread and the action thread.
OCR_READY_EVENT = threading.Event()
BITE_DETECTED_EVENT = threading.Event()
CLOSE_DETECTED_EVENT = threading.Event()
START_FISH_DETECTED_EVENT = threading.Event()
LOST_FISH_DETECTED_EVENT = threading.Event()
LAST_OCR_TEXT_LOCK = threading.Lock()
LAST_OCR_TEXT = ""
OCR_READER_LOCK = threading.Lock()
OCR_READER = None
OCR_TARGETED_READ_EVENT = threading.Event()


class RestartLoop(Exception):
    """Raised when OCR tells the action loop to abandon the current cycle."""
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


# ===== Logging / timing helpers =====
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
    if not LOG_ENABLED:
        return
    if threading.current_thread().name == "Action" and not ACTION_LOG_ENABLED:
        return
    logging.info(message)


def log_force(message):
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


# ===== OCR-driven restart hooks =====
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


def wait_no_restart(ms, stop_event=None):
    """Delay between deterministic UI steps without OCR-driven loop restarts."""
    log(f"Wait {ms}ms without OCR restart")
    end = time.perf_counter() + ms / 1000.0
    while time.perf_counter() < end:
        if stop_event is not None and stop_event.is_set():
            raise KeyboardInterrupt
        if stop_requested():
            log("F12 detected")
            if stop_event is not None:
                stop_event.set()
            raise KeyboardInterrupt
        delay(50)


# ===== Mouse / keyboard input helpers =====
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


class DirectionKeyController:
    """Track held A/D state so the fishing loop can steer smoothly."""

    def __init__(self):
        self.current = None

    def set_direction(self, direction):
        if direction == self.current:
            return

        if self.current == "left":
            log("Release A")
            key_up(VK_A)
        elif self.current == "right":
            log("Release D")
            key_up(VK_D)

        self.current = None

        if direction == "left":
            log("Hold A")
            key_down(VK_A)
            self.current = "left"
        elif direction == "right":
            log("Hold D")
            key_down(VK_D)
            self.current = "right"

    def release_all(self):
        self.set_direction(None)


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


def click_client_ref(hwnd, ref_x, ref_y):
    click_at(*scaled_client_point(hwnd, ref_x, ref_y))


# ===== Window and coordinate helpers =====
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
    x, y = client_to_screen(hwnd, width / 2, height / 2 + FOCUS_CENTER_Y_OFFSET)
    log(f"Focus game client center offset: {x}, {y}")
    click_at(x, y)


def window_title(hwnd):
    length = user32.GetWindowTextLengthW(hwnd)
    if length <= 0:
        return ""

    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return buf.value


def find_window(keyword, announce=True):
    """Find the first visible top-level window whose title contains keyword."""
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
    """Restore the game window and bring it to the foreground."""
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
    """Capture the whole client or a reference sub-region for OCR."""
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

    if OCR_LOG_CAPTURE_REGION:
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


def largest_contour_rect(mask, min_width=1, min_height=1, max_width=None, min_area=1):
    import cv2

    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    best = None
    best_score = 0

    for contour in contours:
        x, y, w, h = cv2.boundingRect(contour)
        area = w * h
        if w < min_width or h < min_height or area < min_area:
            continue
        if max_width is not None and w > max_width:
            continue
        if area > best_score:
            best = (x, y, w, h)
            best_score = area

    return best


def longest_mask_run(column_counts, min_pixels, min_width=1, max_width=None):
    best = None
    start = None

    for index, count in enumerate(column_counts):
        active = count >= min_pixels
        if active and start is None:
            start = index
            continue

        if active:
            continue

        if start is None:
            continue

        width = index - start
        if width >= min_width and (max_width is None or width <= max_width):
            if best is None or width > best[2]:
                best = (start, index - 1, width)
        start = None

    if start is not None:
        width = len(column_counts) - start
        if width >= min_width and (max_width is None or width <= max_width):
            if best is None or width > best[2]:
                best = (start, len(column_counts) - 1, width)

    return best


def detect_fishing_bar_state(hwnd):
    """Locate the target zone and cursor inside the fishing bar."""
    import cv2
    import numpy as np

    image = capture_client_image(hwnd, FISH_BAR_REGION_REF)
    hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
    height, width = image.shape[:2]
    band_top = max(0, int(round(height * FISH_BAR_BAND_TOP_RATIO)))
    band_bottom = min(height, int(round(height * FISH_BAR_BAND_BOTTOM_RATIO)))
    if band_bottom - band_top < 6:
        return None

    inner_hsv = hsv[band_top:band_bottom, :]

    blue_mask = cv2.inRange(
        inner_hsv,
        np.array(FISH_BAR_BLUE_LOWER_HSV, dtype=np.uint8),
        np.array(FISH_BAR_BLUE_UPPER_HSV, dtype=np.uint8),
    )
    yellow_mask = cv2.inRange(
        inner_hsv,
        np.array(FISH_BAR_YELLOW_LOWER_HSV, dtype=np.uint8),
        np.array(FISH_BAR_YELLOW_UPPER_HSV, dtype=np.uint8),
    )

    blue_mask = cv2.morphologyEx(blue_mask, cv2.MORPH_CLOSE, np.ones((7, 3), dtype=np.uint8))
    yellow_mask = cv2.morphologyEx(yellow_mask, cv2.MORPH_CLOSE, np.ones((3, 3), dtype=np.uint8))

    blue_counts = np.count_nonzero(blue_mask, axis=0)
    yellow_counts = np.count_nonzero(yellow_mask, axis=0)

    target_run = longest_mask_run(
        blue_counts,
        min_pixels=FISH_BAR_TARGET_COLUMN_MIN_PIXELS,
        min_width=FISH_BAR_TARGET_MIN_WIDTH,
    )
    cursor_run = longest_mask_run(
        yellow_counts,
        min_pixels=FISH_BAR_CURSOR_COLUMN_MIN_PIXELS,
        min_width=FISH_BAR_CURSOR_MIN_WIDTH,
        max_width=FISH_BAR_CURSOR_MAX_WIDTH,
    )

    if not target_run or not cursor_run:
        return None

    target_start, target_end, target_width = target_run
    cursor_start, cursor_end, cursor_width = cursor_run
    target_rect = (target_start, band_top, target_width, band_bottom - band_top)
    cursor_rect = (cursor_start, band_top, cursor_width, band_bottom - band_top)

    return {
        "target_left": target_start,
        "target_right": target_end,
        "target_center_x": (target_start + target_end) / 2.0,
        "target_width": target_width,
        "cursor_center_x": (cursor_start + cursor_end) / 2.0,
        "cursor_width": cursor_width,
        "target_rect": target_rect,
        "cursor_rect": cursor_rect,
        "sample_band": (band_top, band_bottom),
        "image_shape": image.shape,
    }


# ===== OCR runtime state helpers =====
def set_last_ocr_text(text):
    global LAST_OCR_TEXT
    with LAST_OCR_TEXT_LOCK:
        LAST_OCR_TEXT = text


def get_last_ocr_text():
    with LAST_OCR_TEXT_LOCK:
        return LAST_OCR_TEXT


def set_ocr_reader(reader):
    global OCR_READER
    with OCR_READER_LOCK:
        OCR_READER = reader


def get_ocr_reader():
    with OCR_READER_LOCK:
        return OCR_READER


def update_detection_events(snapshot):
    """Update cross-thread event flags from one OCR snapshot."""
    bite_text = snapshot["bite_text"]
    close_text = snapshot["close_text"]
    result_text = snapshot["result_text"]
    lost_fish_text = snapshot["lost_fish_text"]
    start_fish_text = snapshot["start_fish_text"]

    bite_seen = bite_text_seen(bite_text)  # "鱼上钩" / "上钩了"
    close_seen = text_seen_any(close_text, OCR_CLOSE_KEYWORDS) or result_overlay_text_seen(result_text)  # Result overlay: "点击空白区域关闭" / "垂钓等级" / "获得钓鱼经验"
    lost_fish_seen = text_seen_exact(lost_fish_text, OCR_LOST_FISH_TEXT)  # "鱼儿溜走了"
    start_fish_seen = normalize_text(OCR_START_FISH_TEXT) in normalize_text(start_fish_text)  # "开始钓鱼"
    target_seen = OCR_TARGET_TEXT in normalize_text(bite_text)  # "向左溜鱼"

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

    snapshot["bite_seen"] = bite_seen
    snapshot["close_seen"] = close_seen
    snapshot["lost_fish_seen"] = lost_fish_seen
    snapshot["start_fish_seen"] = start_fish_seen
    snapshot["target_seen"] = target_seen
    snapshot["combined_text"] = " | ".join(
        part for part in snapshot.values() if isinstance(part, str) and part
    )
    if snapshot["combined_text"]:
        set_last_ocr_text(snapshot["combined_text"])
    return snapshot


def ocr_status(snapshot):
    """Pick the most important label for logging this OCR pass."""
    if snapshot["start_fish_seen"]:
        return "START"
    if snapshot["lost_fish_seen"]:
        return "LOST"
    if snapshot["close_seen"]:
        return "CLOSE"
    if snapshot["bite_seen"]:
        return "BITE"
    if snapshot["target_seen"]:
        return "MATCH"
    return "TEXT"


def wait_for_ocr_ready(stop_event):
    """Block the action thread until OCR is ready or timeout occurs."""
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
    """Wait until OCR sees a bite-related prompt."""
    return wait_for_bite_text_after_first_f(None, stop_event)


def read_need_bait_text_once(hwnd, log_attempt=False):
    reader = get_ocr_reader()
    if not hwnd:
        if log_attempt:
            log_force("[NeedBait] skip OCR: hwnd not found")
        return False
    if reader is None:
        if log_attempt:
            log_force("[NeedBait] skip OCR: reader not ready")
        return False

    image = capture_client_image(hwnd, OCR_NEED_BAIT_REGION_REF)
    raw_text = format_ocr_result(read_easyocr_text(reader, image))  # "需要装备鱼饵才可以钓鱼"
    allowlist_text = ""
    if not need_bait_text_seen(raw_text):
        allowlist_text = format_ocr_result(
            read_easyocr_text(reader, image, allowlist=OCR_NEED_BAIT_ALLOWLIST)
        )
    text = " | ".join(part for part in (raw_text, allowlist_text) if part)
    if text:
        set_last_ocr_text(text)
    normalized = normalize_text(text)
    seen = need_bait_text_seen(text)
    if log_attempt or text:
        log_force(
            "[NeedBait] "
            f"region={OCR_NEED_BAIT_REGION_REF} raw={raw_text!r} "
            f"allowlist={allowlist_text!r} normalized={normalized!r} "
            f"len={len(normalized)} seen={seen}"
        )
    return seen


def wait_for_bite_text_after_first_f(hwnd, stop_event):
    """Wait for "鱼上钩", and press the first F again if it stalls for 8s."""
    log_force("[Bite] wait until OCR sees bite text")
    end = time.perf_counter() + BITE_WAIT_TIMEOUT_MS / 1000.0
    next_first_f = time.perf_counter() + FIRST_F_RETRY_MS / 1000.0
    OCR_TARGETED_READ_EVENT.set()
    try:
        while time.perf_counter() < end:
            if stop_event.is_set() or stop_requested():
                stop_event.set()
                raise KeyboardInterrupt
            maybe_restart_from_ocr_events(stop_event)
            if hwnd is None:
                hwnd = find_window(TARGET_TITLE_KEYWORD, announce=False)
            reader = get_ocr_reader()
            if hwnd and reader is not None:
                snapshot = empty_ocr_snapshot()
                snapshot["bite_text"] = read_ocr_regions(reader, hwnd, capture_client_image)  # "鱼上钩" / "向左溜鱼"
                update_detection_events(snapshot)
            if BITE_DETECTED_EVENT.is_set():
                log_force(f"[Bite] detected: {get_last_ocr_text()}")
                BITE_DETECTED_EVENT.clear()
                return True
            if time.perf_counter() >= next_first_f:
                log_force("[Bite] not seen for 8s; press first F again")
                BITE_DETECTED_EVENT.clear()
                press_key(VK_F, 110)
                wait_no_restart(NEED_BAIT_CHECK_DELAY_MS, stop_event)
                if wait_for_need_bait_text_from_hwnd(hwnd, stop_event, NEED_BAIT_CHECK_TIMEOUT_MS):
                    log_force(f"[NeedBait] detected after first-F retry: {get_last_ocr_text()}")
                    recover_missing_bait(hwnd, stop_event)
                next_first_f = time.perf_counter() + FIRST_F_RETRY_MS / 1000.0
            delay(150)
    finally:
        OCR_TARGETED_READ_EVENT.clear()

    log_force(f"[Bite] timeout; last OCR text: {get_last_ocr_text()}")
    return False


def wait_for_close_text(stop_event):
    """Wait until OCR sees the close-overlay prompt."""
    log("Wait until OCR sees close text.")
    end = time.perf_counter() + CLOSE_WAIT_TIMEOUT_MS / 1000.0
    OCR_TARGETED_READ_EVENT.set()
    try:
        while time.perf_counter() < end:
            if stop_event.is_set() or stop_requested():
                stop_event.set()
                raise KeyboardInterrupt
            maybe_restart_from_ocr_events(stop_event)
            hwnd = find_window(TARGET_TITLE_KEYWORD, announce=False)
            reader = get_ocr_reader()
            if hwnd and reader is not None:
                snapshot = empty_ocr_snapshot()
                snapshot["close_text"] = read_ocr_region(reader, hwnd, OCR_CLOSE_REGIONS_REF[0], capture_client_image)  # "点击空白区域关闭"
                snapshot["result_text"] = read_result_overlay_text(reader, hwnd, capture_client_image)  # "垂钓等级" / "获得钓鱼经验"
                update_detection_events(snapshot)
            if CLOSE_DETECTED_EVENT.is_set():
                log(f"Close text detected: {get_last_ocr_text()}")
                CLOSE_DETECTED_EVENT.clear()
                return True
            delay(150)
    finally:
        OCR_TARGETED_READ_EVENT.clear()

    log(f"Close text timeout; last OCR text: {get_last_ocr_text()}")
    return False


def wait_for_need_bait_text(stop_event):
    """Check the center banner for "需要装备鱼饵才可以钓鱼" after the first F."""
    wait(NEED_BAIT_CHECK_DELAY_MS, stop_event)
    log_force("[NeedBait] check after first F")
    return wait_for_need_bait_text_from_hwnd(None, stop_event, NEED_BAIT_CHECK_TIMEOUT_MS)


def wait_for_need_bait_text_from_hwnd(hwnd, stop_event, timeout_ms):
    """Poll the center banner for "需要装备鱼饵才可以钓鱼"."""
    log_force(f"[NeedBait] poll start timeout={timeout_ms}ms")
    end = time.perf_counter() + timeout_ms / 1000.0
    OCR_TARGETED_READ_EVENT.set()
    try:
        while time.perf_counter() < end:
            if stop_event.is_set() or stop_requested():
                stop_event.set()
                raise KeyboardInterrupt
            if hwnd is None:
                hwnd = find_window(TARGET_TITLE_KEYWORD, announce=False)
            if read_need_bait_text_once(hwnd, log_attempt=True):
                log_force(f"[NeedBait] detected: {get_last_ocr_text()}")
                return True
            delay(150)
    finally:
        OCR_TARGETED_READ_EVENT.clear()

    log_force(f"[NeedBait] poll timeout; last OCR text: {get_last_ocr_text()}")
    return False


def bait_action_pause(stop_event):
    wait_no_restart(NEED_BAIT_ACTION_DELAY_MS, stop_event)


def recover_missing_bait(hwnd, stop_event):
    """Equip bait through the fixed UI path, then restart the fishing loop."""
    log_force("[NeedBait] ENTER recover_missing_bait")
    log_force("[NeedBait] press R")
    press_key(VK_R, 110)
    bait_action_pause(stop_event)
    log_force("[NeedBait] click bait UI point 1 ref=(360,230)")
    click_client_ref(hwnd, 360, 230)
    bait_action_pause(stop_event)
    log_force("[NeedBait] click bait UI point 2 ref=(1824,948)")
    click_client_ref(hwnd, 1824, 948)
    bait_action_pause(stop_event)
    log_force("[NeedBait] click bait UI point 3 ref=(1612,1030)")
    click_client_ref(hwnd, 1612, 1030)
    bait_action_pause(stop_event)
    log_force("[NeedBait] click bait UI point 4 ref=(1160,700)")
    click_client_ref(hwnd, 1160, 700)
    bait_action_pause(stop_event)
    bait_action_pause(stop_event)
    bait_action_pause(stop_event)
    click_close_overlay_target(hwnd)
    bait_action_pause(stop_event)
    log_force("[NeedBait] press Esc")
    press_key(VK_ESC, 110)
    bait_action_pause(stop_event)
    bait_action_pause(stop_event)
    bait_action_pause(stop_event)
    log_force("[NeedBait] press E")
    press_key(VK_E, 110)
    bait_action_pause(stop_event)
    log_force("[NeedBait] click final confirm ref=(1165,700)")
    click_client_ref(hwnd, 1165, 700)
    bait_action_pause(stop_event)
    bait_action_pause(stop_event)
    log_force("[NeedBait] recover_missing_bait finished; restart loop")
    raise RestartLoop


def click_close_overlay_target(hwnd):
    """Dismiss the result overlay by clicking the known bottom-right blank area."""
    log("Click right target")
    CLOSE_DETECTED_EVENT.clear()
    click_client_ref(hwnd, RIGHT_CLICK_REF_X, RIGHT_CLICK_REF_Y)


def close_result_overlay(hwnd, stop_event):
    """Dismiss the result overlay quickly after the fishing bar disappears."""
    wait(RESULT_CLOSE_CLICK_DELAY_MS, stop_event)

    if RESULT_CLOSE_USE_OCR_CONFIRM and not wait_for_close_text(stop_event):
        log("Result overlay OCR not confirmed; click fallback anyway.")

    click_close_overlay_target(hwnd)
    wait(RESULT_CLOSE_POST_CLICK_WAIT_MS, stop_event)
    return True


def choose_fishing_direction(error, deadzone, release_zone, current_direction):
    """Map bar offset to A/D direction with a small hysteresis band."""
    if current_direction == "left":
        if error >= release_zone:
            return "left"
        if error <= -deadzone:
            return "right"
        return None

    if current_direction == "right":
        if error <= -release_zone:
            return "right"
        if error >= deadzone:
            return "left"
        return None

    if error >= deadzone:
        return "left"
    if error <= -deadzone:
        return "right"
    return None


def play_fishing_bar(hwnd, stop_event):
    """Steer the yellow cursor with A/D so it stays inside the blue target zone."""
    log("Start visual fishing bar control.")
    controller = DirectionKeyController()
    end = time.perf_counter() + FISH_BAR_LOOP_TIMEOUT_MS / 1000.0
    miss_count = 0
    last_logged_error = None

    try:
        while time.perf_counter() < end:
            if stop_event.is_set():
                raise KeyboardInterrupt
            if stop_requested():
                log("F12 detected")
                stop_event.set()
                raise KeyboardInterrupt

            maybe_restart_from_ocr_events(stop_event)

            if CLOSE_DETECTED_EVENT.is_set():
                log("Close text detected during visual control.")
                return True

            state = detect_fishing_bar_state(hwnd)
            if state is None:
                miss_count += 1
                controller.release_all()
                if miss_count >= FISH_BAR_MAX_MISSES:
                    log("Fishing bar detection lost; stop visual control.")
                    return False
                delay(FISH_BAR_POLL_MS)
                continue

            miss_count = 0
            target_width = state["target_width"]
            deadzone = max(FISH_BAR_MIN_DEADZONE_PX, int(target_width * FISH_BAR_DEADZONE_RATIO))
            release_zone = max(1, int(deadzone * FISH_BAR_RELEASE_RATIO))
            error = state["cursor_center_x"] - state["target_center_x"]
            direction = choose_fishing_direction(
                error,
                deadzone,
                release_zone,
                controller.current,
            )
            controller.set_direction(direction)

            rounded_error = int(round(error))
            if last_logged_error is None or abs(rounded_error - last_logged_error) >= 20:
                log(
                    f"Fishing bar track: cursor={state['cursor_center_x']:.1f} "
                    f"target={state['target_center_x']:.1f} width={target_width} "
                    f"error={rounded_error} direction={direction}"
                )
                last_logged_error = rounded_error

            delay(FISH_BAR_POLL_MS)
    finally:
        controller.release_all()

    log("Fishing bar control timeout; stop visual control.")
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


# ===== OCR thread =====
def ocr_loop(stop_event):
    """Continuously OCR the game window and publish detection events."""
    if not OCR_ENABLED:
        return

    try:
        import easyocr

        log("OCR thread loading EasyOCR model...")
        use_gpu = should_use_ocr_gpu()
        log(f"OCR EasyOCR gpu={use_gpu}")
        reader = easyocr.Reader(OCR_READER_LANGS, gpu=use_gpu)
        set_ocr_reader(reader)
        log("OCR thread ready.")
        OCR_READY_EVENT.set()

        last_print = 0
        while not stop_event.is_set():
            hwnd = find_window(TARGET_TITLE_KEYWORD, announce=False)
            if hwnd and not OCR_TARGETED_READ_EVENT.is_set():
                snapshot = update_detection_events(read_ocr_fast_snapshot(reader, hwnd, capture_client_image))
                text = snapshot["combined_text"]

                if text:
                    now = time.perf_counter()
                    if (now - last_print) * 1000 >= OCR_PRINT_COOLDOWN_MS:
                        log(f"OCR {ocr_status(snapshot)}: {text}")
                        last_print = now

            stop_event.wait(OCR_INTERVAL_MS / 1000.0)
    except Exception as exc:
        logging.exception("OCR thread stopped by error: %s", exc)
        OCR_READY_EVENT.set()
        log("OCR disabled for this run; action loop will continue.")


# ===== Fishing flow =====
def fish_once(stop_event):
    """Run one fishing cycle from focus acquisition to cleanup."""
    log_force("[Flow] === New loop ===")
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
    wait(300, stop_event)
    click_close_overlay_target(hwnd)    # left bottom click
    wait(300, stop_event)
    log_force("[Flow] First F")
    BITE_DETECTED_EVENT.clear()
    press_key(VK_F, 110)

    log_force("[Flow] call wait_for_need_bait_text after First F")
    if wait_for_need_bait_text(stop_event):
        log_force("[Flow] wait_for_need_bait_text returned True; call recover_missing_bait")
        recover_missing_bait(hwnd, stop_event)
    log_force("[Flow] wait_for_need_bait_text returned False; continue to bite wait")

    if not wait_for_bite_text_after_first_f(hwnd, stop_event):
        log_force("[Flow] bite wait returned False; restart loop")
        raise RestartLoop
    maybe_restart_from_ocr_events(stop_event)
    log_force("[Flow] Second F")
    press_key(VK_F, 110)


    CLOSE_DETECTED_EVENT.clear()
    wait(300, stop_event)
    play_fishing_bar(hwnd, stop_event)
    close_result_overlay(hwnd, stop_event)

    wait(300, stop_event)
    maybe_restart_from_ocr_events(stop_event)

def wait_for_start():
    """Wait for the user hotkey that starts the automation."""
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


# ===== Action / application threads =====
def action_loop(stop_event):
    """Main action thread that repeatedly executes fishing cycles."""
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
    """Program entry point: wait for start, then launch OCR + action threads."""
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
