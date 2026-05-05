# -*- coding: utf-8 -*-

import ctypes
import csv
import os
import time
from datetime import datetime
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


VK_F12 = 0x7B

user32.GetCursorPos.argtypes = [ctypes.POINTER(wintypes.POINT)]
user32.GetCursorPos.restype = wintypes.BOOL
user32.ScreenToClient.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.POINT)]
user32.ScreenToClient.restype = wintypes.BOOL
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short


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


def is_pressed(vk):
    return bool(user32.GetAsyncKeyState(vk) & 0x8000)


def make_capture_file():
    capture_dir = os.path.join(os.path.dirname(__file__), "captures")
    os.makedirs(capture_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(capture_dir, f"mouse_points_{timestamp}.csv")
    with open(path, "w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "index",
                "timestamp",
                "window_title",
                "client_width",
                "client_height",
                "screen_x",
                "screen_y",
                "client_x",
                "client_y",
                "ref_x",
                "ref_y",
                "inside_client",
            ]
        )
    return path


def append_capture_row(
    csv_path,
    index,
    title,
    width,
    height,
    screen_x,
    screen_y,
    client_x,
    client_y,
    ref_x,
    ref_y,
    inside,
):
    with open(csv_path, "a", newline="", encoding="utf-8-sig") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                index,
                datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                title,
                width,
                height,
                screen_x,
                screen_y,
                client_x,
                client_y,
                f"{ref_x:.1f}",
                f"{ref_y:.1f}",
                inside,
            ]
        )


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
    csv_path = make_capture_file()

    print(f"Window: {title}")
    print(f"Client size: {width} x {height}")
    print(f"Reference size: {REFERENCE_WIDTH} x {REFERENCE_HEIGHT}")
    print(f"Current LEFT ref ({LEFT_CLICK_REF_X}, {LEFT_CLICK_REF_Y}) -> screen {left_screen}")
    print(f"Current RIGHT ref ({RIGHT_CLICK_REF_X}, {RIGHT_CLICK_REF_Y}) -> screen {right_screen}")
    print(f"Client center -> screen {center_screen}")
    print(f"Capture file: {csv_path}")
    print("Move mouse to any target. Press F12 to append one point. Press Ctrl+C to stop.")
    print("")

    capture_count = 0
    last_f12_down = False

    try:
        while True:
            screen_x, screen_y = cursor_screen_pos()
            client_x, client_y = screen_to_client(hwnd, screen_x, screen_y)
            inside = 0 <= client_x < width and 0 <= client_y < height
            ref_x = client_x * REFERENCE_WIDTH / width
            ref_y = client_y * REFERENCE_HEIGHT / height
            f12_down = is_pressed(VK_F12)

            clear_line()
            print(
                f"screen=({screen_x:4d},{screen_y:4d})  "
                f"client=({client_x:4d},{client_y:4d})  "
                f"ref=({ref_x:7.1f},{ref_y:7.1f})  "
                f"inside={inside}  captures={capture_count}",
                end="",
                flush=True,
            )

            if f12_down and not last_f12_down:
                capture_count += 1
                append_capture_row(
                    csv_path,
                    capture_count,
                    title,
                    width,
                    height,
                    screen_x,
                    screen_y,
                    client_x,
                    client_y,
                    ref_x,
                    ref_y,
                    inside,
                )
                clear_line()
                print(
                    f"[F12] saved #{capture_count}: "
                    f"screen=({screen_x},{screen_y})  "
                    f"client=({client_x},{client_y})  "
                    f"ref=({ref_x:.1f},{ref_y:.1f})  "
                    f"inside={inside}  "
                    f"file={csv_path}"
                )

            last_f12_down = f12_down
            time.sleep(0.08)
    except KeyboardInterrupt:
        clear_line()
        print(f"Stopped. Captures saved: {capture_count}. File: {csv_path}")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
