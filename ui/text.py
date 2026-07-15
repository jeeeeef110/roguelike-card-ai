"""ui/text.py — 文字快取渲染(A5 守則:Pygame 文字每幀重 render 很慢)

同一段字只 render 一次,之後每幀只 blit(key = (字串, 字級, 顏色, 粗體))。
字體依 A1 找思源黑體/系統中文黑體,找不到退回 pygame 預設
(退回時 CJK 會變豆腐,只影響外觀不影響功能)。

快取上限 512 條:超過即整批清空重來——戰鬥中的 HP/傷害數字是
不斷變化的短字串,無上限會慢慢吃記憶體;整批清空最簡單且夠用
(重建成本 = 畫面上同時可見的幾十條字,一幀內完成)。
"""
from __future__ import annotations

import pygame

# SysFont 接受逗號串列,由左到右找,全落空退回預設字體
_FONT_NAMES = "notosanstc,notosanscjktc,pingfangtc,heititc,arialunicode"
_MAX_ENTRIES = 512

_fonts: dict[tuple, pygame.font.Font] = {}
_texts: dict[tuple, pygame.Surface] = {}


def get_font(size: int, bold: bool = False) -> pygame.font.Font:
    key = (size, bold)
    f = _fonts.get(key)
    if f is None:
        f = pygame.font.SysFont(_FONT_NAMES, size, bold=bold)
        _fonts[key] = f
    return f


def text(s: str, size: int, color, bold: bool = False) -> pygame.Surface:
    """回傳快取的文字 Surface(共享物件,呼叫端不得改動它)。"""
    key = (s, size, tuple(color), bold)
    surf = _texts.get(key)
    if surf is None:
        if len(_texts) >= _MAX_ENTRIES:
            _texts.clear()
        surf = get_font(size, bold).render(s, True, color)
        _texts[key] = surf
    return surf


def draw_text(surface: pygame.Surface, s: str, pos, size: int, color,
              bold: bool = False, align: str = "topleft") -> pygame.Rect:
    """畫一段字;align 是 Rect 錨點名(topleft/center/midtop/topright…)。
    回傳實際佔用的 Rect(呼叫端排版用)。"""
    img = text(s, size, color, bold)
    r = img.get_rect(**{align: (round(pos[0]), round(pos[1]))})
    surface.blit(img, r)
    return r


def cache_size() -> int:
    return len(_texts)


def clear_cache() -> None:
    _texts.clear()
