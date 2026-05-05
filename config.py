# -*- coding: utf-8 -*-
"""
Static configuration for autofish.py.

Only pure constants live here: OCR texts/regions, timing values, reference
coordinates, hotkeys, and visual thresholds. Runtime state such as threading
events, locks, and OCR reader instances stays in autofish.py.
"""

# Window / logging / OCR switches.
TARGET_TITLE_KEYWORD = "\u5f02\u73af"
LOG_ENABLED = True
ACTION_LOG_ENABLED = False
LOG_FILE = "logs/autofish.log"
OCR_ENABLED = True
OCR_GPU_MODE = "auto"

# OCR target texts.
OCR_TARGET_TEXT = "\u5411\u5de6\u6e9c\u9c7c"  # "向左溜鱼"
OCR_BITE_KEYWORDS = (
    "\u9c7c\u4e0a\u94a9",      # "鱼上钩"
    "\u4e0a\u94a9",            # "上钩"
    "\u9c7c\u94a9\u4e86",      # OCR 可能把 "鱼上钩了" 漏掉中间字
    "\u4e0a\u94a9\u4e86",      # "上钩了"
    "\u9c7c\u52fe\u4e86",      # OCR 可能把 "钩" 识别成近似字
)
OCR_CLOSE_KEYWORDS = (
    "\u70b9\u51fb\u7a7a\u767d\u533a\u57df\u5173\u95ed",  # "点击空白区域关闭"
    "\u70b9\u51fb\u7a7a\u767d",                          # "点击空白"
    "\u7a7a\u767d\u533a\u57df",                          # "空白区域"
    "\u533a\u57df\u5173\u95ed",                          # "区域关闭"
)
OCR_RESULT_KEYWORDS = (
    "\u5782\u9493\u7b49\u7ea7",                          # "垂钓等级"
    "\u83b7\u5f97\u9493\u9c7c\u7ecf\u9a8c",              # "获得钓鱼经验"
    "\u9493\u9c7c\u7ecf\u9a8c",                          # "钓鱼经验"
)
OCR_NEED_BAIT_KEYWORDS = (
    "\u9700\u8981\u88c5\u5907\u9c7c\u9975\u624d\u53ef\u4ee5\u9493\u9c7c",  # "需要装备鱼饵才可以钓鱼"
    "\u9700\u8981\u88c5\u5907\u9c7c\u9975",                                # "需要装备鱼饵"
    "\u9c7c\u9975\u624d\u53ef\u4ee5\u9493\u9c7c",                          # "鱼饵才可以钓鱼"
)
OCR_NEED_BAIT_ALLOWLIST = "\u9700\u8981\u88c5\u88dd\u5907\u9c7c\u9b5a\u9975\u990c\u624d\u53ef\u4ee5\u9493\u94a9\u6784\u67b8\u94a7\u6602\u8204\u9c81"  # "需要装备鱼饵才可以钓鱼" plus common OCR variants.
OCR_START_FISH_TEXT = "\u5f00\u59cb\u9493\u9c7c"       # "开始钓鱼"
OCR_LOST_FISH_TEXT = "\u9c7c\u513f\u6e9c\u8d70\u4e86"   # "鱼儿溜走了"

# OCR runtime options.
OCR_INTERVAL_MS = 1000
OCR_PRINT_COOLDOWN_MS = 2000
OCR_LOG_CAPTURE_REGION = False
OCR_PREPROCESS_SCALE = 1.6
OCR_READER_LANGS = ["ch_sim"]

# OCR regions are based on a 1920x1080 client reference. They are split by
# purpose so each event is only triggered by the UI area that should contain it.
OCR_BITE_REGIONS_REF = (
    (450, 120, 1020, 520),
    (620, 850, 1300, 1060),
)
OCR_CLOSE_REGIONS_REF = (
    (620, 850, 1300, 1060),
)
OCR_RESULT_REGIONS_REF = (
    (650, 80, 1260, 180),    # Top result bar: "垂钓等级".
    (600, 800, 1320, 900),   # Bottom reward strip: "获得钓鱼经验".
    (620, 920, 1300, 1030),  # Bottom prompt: "点击空白区域关闭".
)
OCR_NEED_BAIT_REGION_REF = (740, 500, 1175, 575)
OCR_LOST_FISH_REGION_REF = (480, 500, 1440, 660)
OCR_START_FISH_REGION_REF = (1350, 800, 1820, 1030)

# Flow timing.
BITE_WAIT_TIMEOUT_MS = 20000
FIRST_F_RETRY_MS = 8000
CLOSE_WAIT_TIMEOUT_MS = 15000
OCR_READY_TIMEOUT_MS = 60000
NEED_BAIT_CHECK_DELAY_MS = 500
NEED_BAIT_CHECK_TIMEOUT_MS = 1200
NEED_BAIT_ACTION_DELAY_MS = 500
NEED_BAIT_MIN_TEXT_CHARS = 6
RESULT_CLOSE_CLICK_DELAY_MS = 900
RESULT_CLOSE_POST_CLICK_WAIT_MS = 450
RESULT_CLOSE_USE_OCR_CONFIRM = False

# Fishing and result click coordinates.
START_FISH_CLICK_REF_X = 1600
START_FISH_CLICK_REF_Y = 940

# Fishing bar visual detection.
FISH_BAR_REGION_REF = (592, 60, 1327, 86)
FISH_BAR_LOOP_TIMEOUT_MS = 25000
FISH_BAR_POLL_MS = 25
FISH_BAR_MAX_MISSES = 8
FISH_BAR_BLUE_LOWER_HSV = (78, 90, 120)
FISH_BAR_BLUE_UPPER_HSV = (91, 255, 255)
FISH_BAR_YELLOW_LOWER_HSV = (22, 70, 190)
FISH_BAR_YELLOW_UPPER_HSV = (35, 255, 255)
FISH_BAR_TARGET_MIN_WIDTH = 35
FISH_BAR_CURSOR_MIN_WIDTH = 1
FISH_BAR_CURSOR_MAX_WIDTH = 10
FISH_BAR_TARGET_COLUMN_MIN_PIXELS = 3
FISH_BAR_CURSOR_COLUMN_MIN_PIXELS = 5
FISH_BAR_BAND_TOP_RATIO = 0.22
FISH_BAR_BAND_BOTTOM_RATIO = 0.80
FISH_BAR_DEADZONE_RATIO = 0.10
FISH_BAR_MIN_DEADZONE_PX = 8
FISH_BAR_RELEASE_RATIO = 0.60

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
FOCUS_CENTER_Y_OFFSET = 30

# Virtual-key codes.
VK_F = 0x46
VK_A = 0x41
VK_D = 0x44
VK_E = 0x45
VK_R = 0x52
VK_ESC = 0x1B
VK_F10 = 0x79
VK_F12 = 0x7B

# WinAPI constants.
SW_RESTORE = 9
KEYEVENTF_KEYUP = 0x0002
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
