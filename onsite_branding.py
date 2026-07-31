"""기프트클린 브랜딩 유틸 — 로고 오버레이, CTA 엔딩 슬라이드, BGM 선택.

image_generator.py의 슬라이드 렌더링 헬퍼(그라데이션/텍스트카드/줄바꿈)를
그대로 재사용해 CTA 슬라이드의 디자인을 정보형 슬라이드와 통일합니다.
"""
from __future__ import annotations

import glob
import os

from PIL import ImageDraw

import image_generator as ig

DEFAULT_LOGO_PATH = os.path.join("assets", "logo.png")
DEFAULT_BGM_DIR = os.path.join("assets", "bgm")
DEFAULT_CTA_TEXT = "더 궁금한 점이 있으신가요?"
DEFAULT_CTA_SUBTEXT = "프로필 링크에서 무료 견적을 확인하세요"

_SYSTEM_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
    "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
]


def _resolve_font_path() -> str | None:
    """assets/fonts에 폰트가 있으면 그것을, 없으면 OS에 설치된 나눔고딕을,
    그것도 없으면 image_generator의 온라인 다운로드를 시도한다.
    (다운로드가 네트워크 정책 등으로 막힌 환경에서도 한글이 깨지지 않도록 함)
    """
    asset_font = os.path.join("assets", "fonts", "NotoSansKR.ttf")
    if os.path.exists(asset_font):
        return asset_font
    for path in _SYSTEM_FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    return ig._ensure_font()

CTA_THEME = {
    "gradient": ["#0f0c29", "#302b63"],
    "text_color": "#FFFFFF",
    "accent_color": "#FFD700",
}


def resolve_logo_path(logo_path: str = None) -> str | None:
    """로고 파일 경로를 확인한다. 파일이 없으면 None (오버레이 생략)."""
    path = logo_path or DEFAULT_LOGO_PATH
    return path if path and os.path.exists(path) else None


def create_cta_slide(output_path: str, main_text: str = None, sub_text: str = None,
                      width: int = 1080, height: int = 1920) -> str:
    """마지막에 붙는 CTA(브랜드 각인 + 행동유도) 슬라이드 이미지를 만든다."""
    text = main_text or DEFAULT_CTA_TEXT
    sub = sub_text or DEFAULT_CTA_SUBTEXT

    font_path = _resolve_font_path()
    img = ig._create_gradient(width, height, CTA_THEME["gradient"])
    ig._add_background_decoration(img, CTA_THEME["accent_color"])
    draw = ImageDraw.Draw(img)

    main_font = ig._get_font(font_path, 56)
    sub_font = ig._get_font(font_path, 36)
    max_width = width - 240

    main_h = ig._calc_text_block_height(text, main_font, max_width, line_spacing=20)
    sub_h = ig._calc_text_block_height(sub, sub_font, max_width) + 50
    total_h = main_h + sub_h

    card_y = height // 2 - total_h // 2 - 40
    ig._draw_text_card(img, 80, card_y - 40, width - 160, total_h + 120)
    draw = ImageDraw.Draw(img)

    end_y = ig._draw_text_wrapped(
        draw, text, main_font, max_width, width // 2, card_y,
        ig._hex_to_rgb(CTA_THEME["text_color"]), line_spacing=20,
    )
    ig._draw_text_wrapped(
        draw, sub, sub_font, max_width, width // 2, end_y + 30,
        ig._hex_to_rgb(CTA_THEME["accent_color"]),
    )

    brand_font = ig._get_font(font_path, 44)
    ig._draw_text_wrapped(
        draw, "기프트클린", brand_font, max_width, width // 2, height - 220,
        ig._hex_to_rgb(CTA_THEME["text_color"]),
    )

    img.save(output_path, "PNG")
    return output_path


def find_bgm(name: str = None, bgm_dir: str = DEFAULT_BGM_DIR) -> str | None:
    """BGM 파일을 찾는다. name을 지정하면 그 파일을, 아니면 폴더의 첫 곡을 사용."""
    if name:
        candidate = name if os.path.isabs(name) else os.path.join(bgm_dir, name)
        return candidate if os.path.exists(candidate) else None

    if not os.path.exists(bgm_dir):
        return None
    for ext in ("*.mp3", "*.wav", "*.m4a", "*.ogg"):
        files = sorted(glob.glob(os.path.join(bgm_dir, ext)))
        if files:
            return files[0]
    return None


def list_bgm_options(bgm_dir: str = DEFAULT_BGM_DIR) -> list:
    if not os.path.exists(bgm_dir):
        return []
    files = []
    for ext in ("*.mp3", "*.wav", "*.m4a", "*.ogg"):
        files.extend(glob.glob(os.path.join(bgm_dir, ext)))
    return sorted(os.path.basename(f) for f in files)
