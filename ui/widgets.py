"""ui/widgets.py — 戰鬥用小元件(藍圖 A3.2 的共用件)

SmoothBar:數值條。「血條永不瞬降」——set() 只下 tween,顯示值
300ms 滑到新值;護甲畫成條外的藍色描邊(A3.2)。

FloatTextLayer:傷害/護甲數字上飄淡出。每個飄字持有自己的 Surface
複本(ui.text 的快取是共享物件,不能對它 set_alpha)。
"""
from __future__ import annotations

import pygame

from ui.text import text as render_text
from ui.tween import Tween, TweenManager

BAR_SLIDE_SECS = 0.3      # A3.2:血條總是 300ms 滑到新值
PANEL = (11, 20, 36)      # 面板 #0B1424
ARMOR = (77, 166, 255)    # 反甲藍 #4DA6FF

FLOAT_RISE = 46           # 飄字上升速度(px/s)
FLOAT_LIFE = 0.9          # 飄字壽命(s);後 60% 漸淡


class SmoothBar:
    """display 是浮點顯示值,由注入的 TweenManager 驅動;
    value 才是遊戲真值(set 時記下,draw 顯示文字用)。"""

    def __init__(self, rect, color, max_value: int, tm: TweenManager,
                 value: int | None = None):
        self.rect = pygame.Rect(rect)
        self.color = color
        self.max_value = max_value
        self.tm = tm
        self.value = max_value if value is None else value
        self.display = float(self.value)

    def set(self, value: int) -> None:
        """更新真值;顯示值 300ms 滑過去(永不瞬跳)。"""
        if value == self.value:
            return
        self.value = value
        self.tm.add(Tween(self, "display", self.display, value,
                          BAR_SLIDE_SECS))

    def draw(self, surface: pygame.Surface, armor: int = 0) -> None:
        pygame.draw.rect(surface, PANEL, self.rect, border_radius=4)
        frac = max(0.0, min(1.0, self.display / self.max_value))
        if frac > 0:
            fill = self.rect.copy()
            fill.width = max(2, round(self.rect.width * frac))
            pygame.draw.rect(surface, self.color, fill, border_radius=4)
        if armor > 0:                      # 護甲=條外藍描邊(A3.2)
            ring = self.rect.inflate(6, 6)
            pygame.draw.rect(surface, ARMOR, ring, width=2, border_radius=6)


class _Float:
    __slots__ = ("surf", "x", "y", "age")

    def __init__(self, surf: pygame.Surface, x: float, y: float):
        self.surf = surf
        self.x = x
        self.y = y
        self.age = 0.0


class FloatTextLayer:
    """spawn 後自主上飄淡出;update 回收壽終的字。"""

    def __init__(self):
        self._floats: list[_Float] = []

    def spawn(self, s: str, pos, size: int = 34, color=(232, 240, 255)) -> None:
        surf = render_text(s, size, color, bold=True).copy()  # 複本才能改 alpha
        self._floats.append(_Float(surf, pos[0], pos[1]))

    def update(self, dt: float) -> None:
        for f in self._floats:
            f.age += dt
            f.y -= FLOAT_RISE * dt
        self._floats = [f for f in self._floats if f.age < FLOAT_LIFE]

    def draw(self, surface: pygame.Surface) -> None:
        for f in self._floats:
            fade_from = FLOAT_LIFE * 0.4
            if f.age > fade_from:
                k = 1.0 - (f.age - fade_from) / (FLOAT_LIFE - fade_from)
                f.surf.set_alpha(round(255 * k))
            surface.blit(f.surf, f.surf.get_rect(
                center=(round(f.x), round(f.y))))

    @property
    def active_count(self) -> int:
        return len(self._floats)
