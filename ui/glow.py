"""ui/glow.py — 發光渲染(藍圖 A2.2)

Pygame 沒有內建 bloom,用「同心多層遞增亮度 + BLEND_RGB_ADD」近似:
光暈先烘焙成黑底 Surface(黑=加零),整張用加法混合 blit 到場景上,
多個光源疊加時亮度自然累加,重疊處變亮——這就是 bloom 的視覺語言。

效能守則(A2.2/A5):
- 靜態光暈一律走快取(key = 參數組),每幀只 blit,不重畫圓
- 每元素層數上限 4(BLEND_RGB_ADD 疊太多層會白爆)
- 驗收:200 節點地圖 60fps(tests/test_glow.py 以 clock.get_fps() 斷言)

用法(場景層):
    glow_circle(screen, node_screen_pos, 12, POISON)   # 節點光暈
    glow_line(screen, a_pos, b_pos, NEUTRAL, 2)        # 路徑光線
"""
from __future__ import annotations

import pygame

MAX_LAYERS = 4          # A5:加法混合疊太多層會白爆
_HALO_SCALE = 2.0       # 光暈外緣 = 半徑 × 2
_HALO_STRENGTH = 0.55   # 光暈相對核心的最高亮度(<1 避免大面積死白)

Color = tuple[int, int, int]

_circle_cache: dict[tuple, pygame.Surface] = {}
_line_cache: dict[tuple, pygame.Surface] = {}


def _norm_color(color) -> Color:
    r, g, b = color[0], color[1], color[2]
    return (int(r), int(g), int(b))


def _scaled(color: Color, k: float) -> Color:
    return (min(255, int(color[0] * k)),
            min(255, int(color[1] * k)),
            min(255, int(color[2] * k)))


# ------------------------------------------------------------------ 烘焙

def bake_glow_circle(radius: int, color, layers: int = 4) -> pygame.Surface:
    """烘焙圓形光暈(黑底,供 BLEND_RGB_ADD 使用);同參數回傳同一 Surface。

    同心圓由外而內亮度遞增(等價於各層加法疊加的累積結果),
    最內為全亮核心。
    """
    radius = int(radius)
    if radius <= 0:
        raise ValueError("radius 必須 > 0")
    layers = max(1, min(int(layers), MAX_LAYERS))
    key = (radius, _norm_color(color), layers)
    cached = _circle_cache.get(key)
    if cached is not None:
        return cached

    col = _norm_color(color)
    size = int(radius * _HALO_SCALE) * 2 + 2
    surf = pygame.Surface((size, size))          # 全黑底
    center = (size // 2, size // 2)
    for i in range(layers):                      # 外 → 內,亮度遞增
        frac = (i + 1) / layers
        r = round(radius * (_HALO_SCALE - (_HALO_SCALE - 1.0) * frac))
        pygame.draw.circle(surf, _scaled(col, frac * _HALO_STRENGTH),
                           center, max(r, 1))
    pygame.draw.circle(surf, col, center, radius)  # 全亮核心
    _circle_cache[key] = surf
    return surf


def bake_glow_line(dx: int, dy: int, color, width: int = 2) -> pygame.Surface:
    """烘焙位移為 (dx, dy) 的發光線段(黑底);同參數回傳同一 Surface。

    三層線寬遞減、亮度遞增(A2.2「同理三層線」)。
    地圖邊是靜態的 → 同一批位移反覆命中快取。
    """
    dx, dy = int(dx), int(dy)
    width = max(1, int(width))
    key = (dx, dy, _norm_color(color), width)
    cached = _line_cache.get(key)
    if cached is not None:
        return cached

    col = _norm_color(color)
    pad = width * 4
    surf = pygame.Surface((abs(dx) + pad * 2, abs(dy) + pad * 2))
    a = (pad + max(-dx, 0), pad + max(-dy, 0))
    b = (a[0] + dx, a[1] + dy)
    for w_mul, k in ((4, 0.25), (2, 0.55), (1, 1.0)):   # 外粗暗 → 內細亮
        pygame.draw.line(surf, _scaled(col, k), a, b, width * w_mul)
    _line_cache[key] = surf
    return surf


# ------------------------------------------------------------------ 繪製

def glow_circle(surface: pygame.Surface, pos, radius: int, color,
                layers: int = 4) -> None:
    """在 pos(螢幕座標)畫一顆發光圓;每幀成本 = 一次加法 blit。"""
    baked = bake_glow_circle(radius, color, layers)
    half = baked.get_width() // 2
    surface.blit(baked, (round(pos[0]) - half, round(pos[1]) - half),
                 special_flags=pygame.BLEND_RGB_ADD)


def glow_line(surface: pygame.Surface, a, b, color, width: int = 2) -> None:
    """畫一條 a→b(螢幕座標)的發光線;每幀成本 = 一次加法 blit。"""
    dx = round(b[0]) - round(a[0])
    dy = round(b[1]) - round(a[1])
    baked = bake_glow_line(dx, dy, color, width)
    pad = max(1, int(width)) * 4
    top_left = (round(a[0]) + min(dx, 0) - pad,
                round(a[1]) + min(dy, 0) - pad)
    surface.blit(baked, top_left, special_flags=pygame.BLEND_RGB_ADD)


def clear_cache() -> None:
    """清空烘焙快取(換場景配色或測試用)。"""
    _circle_cache.clear()
    _line_cache.clear()


def cache_size() -> int:
    return len(_circle_cache) + len(_line_cache)
