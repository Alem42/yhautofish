# -*- coding: utf-8 -*-
"""OCR preprocessing, text matching, and region-reading helpers."""

import threading

from config import *


OCR_READ_LOCK = threading.Lock()


def preprocess_ocr_image(image):
    """Upscale and contrast small UI text before EasyOCR sees it."""
    import cv2

    if OCR_PREPROCESS_SCALE != 1:
        height, width = image.shape[:2]
        image = cv2.resize(
            image,
            (
                max(1, int(round(width * OCR_PREPROCESS_SCALE))),
                max(1, int(round(height * OCR_PREPROCESS_SCALE))),
            ),
            interpolation=cv2.INTER_CUBIC,
        )

    gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    enhanced = cv2.equalizeHist(gray)
    return cv2.cvtColor(enhanced, cv2.COLOR_GRAY2RGB)


def text_seen(result, target):
    return target in normalize_text(format_ocr_result(result))


def normalize_text(text):
    ignored = set(" \t\r\n,，.。!！?？:：;；|/\\-_—[]()（）{}<>《》\"'`")
    variant_map = str.maketrans({
        "\u88dd": "\u88c5",  # "裝" -> "装"
        "\u9b5a": "\u9c7c",  # "魚" -> "鱼"
        "\u990c": "\u9975",  # "餌" -> "饵"
        "\u91e3": "\u9493",  # "釣" -> "钓"
        "\u9264": "\u94a9",  # "鉤" -> "钩"
    })
    normalized = str(text).translate(variant_map)
    return "".join(ch for ch in normalized if ch not in ignored)


def text_seen_any(text, keywords):
    normalized = normalize_text(text)
    return any(keyword in normalized for keyword in keywords)


def bite_text_seen(text):
    """Be tolerant of common OCR mistakes around the bite prompt."""
    normalized = normalize_text(text)
    if any(keyword in normalized for keyword in OCR_BITE_KEYWORDS):
        return True

    # EasyOCR often drops "上" and may misread "点击" around this prompt.
    return (
        "\u9c7c" in normalized
        and ("\u94a9" in normalized or "\u52fe" in normalized)
        and ("\u5feb" in normalized or "\u51fb" in normalized)
    )


def result_overlay_text_seen(text):
    """Detect the result overlay from several fixed labels, not just one prompt."""
    normalized = normalize_text(text)
    if any(keyword in normalized for keyword in OCR_CLOSE_KEYWORDS + OCR_RESULT_KEYWORDS):
        return True

    # Be fuzzy because EasyOCR often drops one or two Chinese characters here.
    return (
        ("\u70b9\u51fb" in normalized and "\u5173\u95ed" in normalized)  # "点击" + "关闭"
        or ("\u7a7a\u767d" in normalized and "\u5173\u95ed" in normalized)  # "空白" + "关闭"
        or ("\u5782" in normalized and "\u7b49\u7ea7" in normalized)  # "垂" + "等级"
        or ("\u9493\u9c7c" in normalized and "\u7ecf\u9a8c" in normalized)  # "钓鱼" + "经验"
        or ("\u83b7\u5f97" in normalized and "\u7ecf\u9a8c" in normalized)  # "获得" + "经验"
    )


def need_bait_text_seen(text):
    """Detect the center banner that says bait must be equipped."""
    normalized = normalize_text(text)
    if len(normalized) >= NEED_BAIT_MIN_TEXT_CHARS:
        return True

    if any(keyword in normalized for keyword in OCR_NEED_BAIT_KEYWORDS):
        return True

    has_bait = "\u9c7c\u9975" in normalized or "\u9975" in normalized  # "鱼饵" / "饵"
    has_fishing = (
        "\u9493\u9c7c" in normalized  # "钓鱼"
        or "\u94a9\u9c7c" in normalized  # EasyOCR may read "钓鱼" as "钩鱼"
        or "\u94a7\u9c7c" in normalized  # EasyOCR may read "钓鱼" as "钧鱼"
        or "\u6784\u9c7c" in normalized  # EasyOCR may read "钓鱼" as "构鱼"
        or "\u67b8\u9c7c" in normalized  # EasyOCR may read "钓鱼" as "枸鱼"
    )

    return (
        has_bait
        and has_fishing
        and (
            "\u9700\u8981" in normalized  # "需要"
            or "\u88c5" in normalized  # "装"
            or "\u5907" in normalized  # "备"
            or "\u53ef\u4ee5" in normalized  # "可以"
            or "\u4ee5" in normalized  # OCR may leave only "以" from "可以"
        )
    )


def text_seen_exact(text, target):
    return normalize_text(text) == normalize_text(target)


def format_ocr_result(result):
    cleaned = [str(text).strip() for text in result if str(text).strip()]
    return " | ".join(cleaned)


def read_easyocr_text(reader, image, allowlist=None):
    image = preprocess_ocr_image(image)
    kwargs = {}
    if allowlist:
        kwargs["allowlist"] = allowlist
    with OCR_READ_LOCK:
        return reader.readtext(
            image,
            detail=0,
            paragraph=True,
            decoder="greedy",
            batch_size=1,
            **kwargs,
        )


def read_ocr_regions(reader, hwnd, capture_client_image, stop_when=None):
    if stop_when is None:
        stop_when = bite_text_seen

    texts = []
    for region in OCR_BITE_REGIONS_REF:
        image = capture_client_image(hwnd, region)
        result = read_easyocr_text(reader, image)
        text = format_ocr_result(result)
        if text:
            texts.append(text)
            if stop_when is not None and stop_when(text):
                return " | ".join(texts)
    return " | ".join(texts)


def read_ocr_region(reader, hwnd, region, capture_client_image):
    image = capture_client_image(hwnd, region)
    result = read_easyocr_text(reader, image)
    return format_ocr_result(result)


def read_result_overlay_text(reader, hwnd, capture_client_image):
    texts = []
    for region in OCR_RESULT_REGIONS_REF:
        text = read_ocr_region(reader, hwnd, region, capture_client_image)
        if text:
            texts.append(text)
    return " | ".join(texts)


def read_ocr_snapshot(reader, hwnd, capture_client_image):
    """Read every OCR region once and return named text blocks."""
    return {
        "bite_text": read_ocr_regions(reader, hwnd, capture_client_image),  # "鱼上钩" / "向左溜鱼"
        "close_text": read_ocr_region(reader, hwnd, OCR_CLOSE_REGIONS_REF[0], capture_client_image),  # "点击空白区域关闭"
        "result_text": read_result_overlay_text(reader, hwnd, capture_client_image),  # "垂钓等级" / "获得钓鱼经验"
        "lost_fish_text": read_ocr_region(reader, hwnd, OCR_LOST_FISH_REGION_REF, capture_client_image),  # "鱼儿溜走了"
        "start_fish_text": read_ocr_region(reader, hwnd, OCR_START_FISH_REGION_REF, capture_client_image),  # "开始钓鱼"
    }


def empty_ocr_snapshot():
    return {
        "bite_text": "",
        "close_text": "",
        "result_text": "",
        "lost_fish_text": "",
        "start_fish_text": "",
    }


def read_ocr_fast_snapshot(reader, hwnd, capture_client_image):
    """Poll lightweight recovery prompts without scanning every OCR region."""
    snapshot = empty_ocr_snapshot()
    snapshot["lost_fish_text"] = read_ocr_region(reader, hwnd, OCR_LOST_FISH_REGION_REF, capture_client_image)  # "鱼儿溜走了"
    snapshot["start_fish_text"] = read_ocr_region(reader, hwnd, OCR_START_FISH_REGION_REF, capture_client_image)  # "开始钓鱼"
    return snapshot
