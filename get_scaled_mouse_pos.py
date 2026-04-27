# -*- coding: utf-8 -*-

import ctypes
import time
from ctypes import wintypes

from autofish import (
    LEFT_CLICK_REF_X,
    LEFT_CLICK_REF_Y,
    REFERENCE_HEIGHT,
    REFERENCE_WIDTH,
    RIGHT_CLICK_REF_X,
    RIGHT_CLICK_REF_Y,
    TARGET_TITLE_KEYWORD,
    client_to_screen,
    find_window,
    get_client_rect,
    scaled_client_point,
    user32,
    window_title,
)


user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.ScreenToClient.restype = wintypes.BOOL


def cursor_screen_pos():
    point = wintypes.POINT()
    if not user32.GetCursorPos(ctypes.byref(point)):
        raise RuntimeError("GetCursorPos failed")
    return point.x, point.y


def screen_to_client(hwnd, x, y):
    point = wintypes.POINT(x, y)
    if not user32.ScreenToClient(hwnd, ctypes.byref(point)):
        raise RuntimeError("ScreenToClient failed")
    return point.x, point.y


def clear_line():
    print("\r" + " " * 150 + "\r", end="", flush=True)


def main():
    hwnd = find_window(TARGET_TITLE_KEYWORD)
    if not hwnd:
        print(f"Cannot find window: {TARGET_TITLE_KEYWORD}")
        return 1

    title = window_title(hwnd)
    rect = get_client_rect(hwnd)
    width = rect.right - rect.left
    height = rect.bottom - rect.top
    left_screen = scaled_client_point(hwnd, LEFT_CLICK_REF_X, LEFT_CLICK_REF_Y)
    right_screen = scaled_client_point(hwnd, RIGHT_CLICK_REF_X, RIGHT_CLICK_REF_Y)
    center_screen = client_to_screen(hwnd, width / 2, height / 2)

    print(f"Window: {title}")
    print(f"Client size: {width} x {height}")
    print(f"Reference size: {REFERENCE_WIDTH} x {REFERENCE_HEIGHT}")
    print(f"Current LEFT ref ({LEFT_CLICK_REF_X}, {LEFT_CLICK_REF_Y}) -> screen {left_screen}")
    print(f"Current RIGHT ref ({RIGHT_CLICK_REF_X}, {RIGHT_CLICK_REF_Y}) -> screen {right_screen}")
    print(f"Client center -> screen {center_screen}")
    print("Move mouse to a target. Press Ctrl+C to stop.")
    print("")

    try:
        while True:
            screen_x, screen_y = cursor_screen_pos()
            client_x, client_y = screen_to_client(hwnd, screen_x, screen_y)
            inside = 0 <= client_x < width and 0 <= client_y < height
            ref_x = client_x * REFERENCE_WIDTH / width
            ref_y = client_y * REFERENCE_HEIGHT / height

            clear_line()
            print(
                f"screen=({screen_x:4d},{screen_y:4d})  "
                f"client=({client_x:4d},{client_y:4d})  "
                f"ref=({ref_x:7.1f},{ref_y:7.1f})  "
                f"inside={inside}",
                end="",
                flush=True,
            )
            time.sleep(0.08)
    except KeyboardInterrupt:
        clear_line()
        print("Stopped.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
