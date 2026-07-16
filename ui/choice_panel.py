"""ui/choice_panel.py — 共用抉擇面板(藍圖 A3.3)

Reward/Shop/Event/Rest 全部蓋在這一個元件上:呼叫端給選項資料與
on_choose 回呼,面板負責演出——
- 進場:選項從下方錯相依序滑入(delay 80ms 遞增;網格模式 30ms)
- 選中:放大飛向牌堆角落(左下),未選者淡出,然後 pop + 回呼
- 跳過:skip_label 給定時顯示底部按鈕,回呼收到 None
- 稀有時刻:sweep_color 給定時,進場前 0.4s 一道光橫掃(菁英金光)

佈局自動切換:≤4 個選項 = 一排大卡;>4 = 網格(休息鍛造/商店刪卡
的「展開牌組網格」)。選項 enabled=False 畫暗且不可點。
UI 鐵律不變:面板不含任何遊戲規則,效果由呼叫端在 on_choose 執行。
"""
from __future__ import annotations

import pygame

from ui.scenes import BG, Scene
from ui.text import draw_text
from ui.tween import Tween

W, H = 960, 540
PANEL = (11, 20, 36)
DIM = (28, 44, 68)
TEXT_MAIN = (232, 240, 255)
TEXT_SUB = (143, 163, 192)
GOLD = (255, 184, 77)

GRID_THRESHOLD = 4        # 超過就切網格
STAGGER_BIG = 0.08        # 錯相間隔(A3.3:80ms)
STAGGER_GRID = 0.03
SLIDE_SECS = 0.35
FLY_SECS = 0.45           # 選中飛向牌堆角落
SWEEP_SECS = 0.4
DECK_CORNER = (90, H - 70)


class Option:
    """一個可選項。title/lines/badge 是文案;x/y/k/s 是動畫屬性
    (k=亮度 0..1、s=縮放),由面板的 tween 驅動。"""

    __slots__ = ("title", "lines", "accent", "enabled", "badge",
                 "x", "y", "k", "s")

    def __init__(self, title: str, lines=(), accent=(127, 212, 255),
                 enabled: bool = True, badge: str = ""):
        self.title = title
        self.lines = list(lines)
        self.accent = accent
        self.enabled = enabled
        self.badge = badge
        self.x = self.y = 0.0
        self.k = 0.0
        self.s = 1.0


class ChoicePanel(Scene):
    def __init__(self, title: str, options: list[Option], on_choose,
                 skip_label: str | None = None, sweep_color=None):
        self.title = title
        self.options = options
        self.on_choose = on_choose
        self.skip_label = skip_label
        self.sweep_color = sweep_color
        self.age = 0.0
        self.locked = False
        self.grid = len(options) > GRID_THRESHOLD
        self.cw, self.ch = (96, 120) if self.grid else (170, 230)
        self._skip_rect = pygame.Rect(0, 0, 160, 40)
        self._skip_rect.midbottom = (W // 2, H - 16)

    # ------------------------------------------------------------ 佈局

    def _slots(self) -> list[tuple[float, float]]:
        n = len(self.options)
        if not self.grid:
            spacing = self.cw + 30
            x0 = W / 2 - spacing * (n - 1) / 2
            return [(x0 + i * spacing, 285.0) for i in range(n)]
        cols = 9                     # 9×3 = 27 張內不出界(MVP 牌組上限內)
        spacing_x, spacing_y = self.cw + 10, self.ch + 14
        out = []
        for i in range(n):
            row, col = divmod(i, cols)
            row_n = min(cols, n - row * cols)
            x0 = W / 2 - spacing_x * (row_n - 1) / 2
            out.append((x0 + col * spacing_x, 165.0 + row * spacing_y))
        return out

    def on_enter(self):
        tm = self.director.tweens
        stagger = STAGGER_GRID if self.grid else STAGGER_BIG
        for i, (opt, (sx, sy)) in enumerate(zip(self.options, self._slots())):
            opt.x, opt.y, opt.k = sx, sy + 46, 0.0
            tm.add(Tween(opt, "y", opt.y, sy, SLIDE_SECS, delay=i * stagger))
            tm.add(Tween(opt, "k", 0.0, 1.0, SLIDE_SECS, delay=i * stagger))

    # ------------------------------------------------------------ 輸入

    def _rect_of(self, opt: Option) -> pygame.Rect:
        r = pygame.Rect(0, 0, round(self.cw * opt.s), round(self.ch * opt.s))
        r.center = (round(opt.x), round(opt.y))
        return r

    def handle(self, event):
        if (self.locked or event.type != pygame.MOUSEBUTTONDOWN
                or event.button != 1):
            return
        if self.skip_label and self._skip_rect.collidepoint(event.pos):
            self._finish(None)
            return
        for i, opt in enumerate(self.options):
            if opt.enabled and self._rect_of(opt).collidepoint(event.pos):
                self._choose(i)
                return

    def _choose(self, i: int):
        self.locked = True
        tm = self.director.tweens
        for j, opt in enumerate(self.options):
            if j == i:                       # 選中:放大→飛向牌堆角落
                tm.add(Tween(opt, "s", 1.0, 1.15, 0.12))
                tm.add(Tween(opt, "x", opt.x, DECK_CORNER[0], FLY_SECS,
                             delay=0.12))
                tm.add(Tween(opt, "y", opt.y, DECK_CORNER[1], FLY_SECS,
                             delay=0.12,
                             on_done=lambda: self._finish(i)))
            else:                            # 未選:淡出
                tm.add(Tween(opt, "k", opt.k, 0.12, 0.3))

    def _finish(self, i: int | None):
        self.locked = True
        self.director.pop(transition="fade")
        self.on_choose(i)                    # 回呼可再推下一個面板

    # ------------------------------------------------------------ 每幀

    def update(self, dt: float):
        self.age += dt

    def _scaled(self, color, k: float):
        return (int(color[0] * k), int(color[1] * k), int(color[2] * k))

    def draw(self, surface: pygame.Surface):
        surface.fill(BG)
        draw_text(surface, self.title, (W / 2, 64), 28, TEXT_MAIN,
                  bold=True, align="center")
        for opt in self.options:
            r = self._rect_of(opt)
            k = opt.k if opt.enabled else opt.k * 0.45
            pygame.draw.rect(surface, PANEL, r, border_radius=8)
            pygame.draw.rect(surface, self._scaled(opt.accent, max(k, 0.18)),
                             r, width=2, border_radius=8)
            size_t = 14 if self.grid else 18
            draw_text(surface, opt.title, (r.centerx, r.top + 12), size_t,
                      self._scaled(TEXT_MAIN, max(k, 0.3)), align="midtop")
            for li, line in enumerate(opt.lines[:4]):
                draw_text(surface, line,
                          (r.centerx, r.top + 12 + size_t + 10 + li * 15),
                          11, self._scaled(TEXT_SUB, max(k, 0.3)),
                          align="midtop")
            if opt.badge:
                draw_text(surface, opt.badge, (r.right - 8, r.top + 8), 13,
                          self._scaled(GOLD, max(k, 0.3)), align="topright")
        if self.skip_label:
            pygame.draw.rect(surface, PANEL, self._skip_rect, border_radius=8)
            pygame.draw.rect(surface, DIM, self._skip_rect, 2, border_radius=8)
            draw_text(surface, self.skip_label, self._skip_rect.center, 15,
                      TEXT_SUB, align="center")
        if self.sweep_color and self.age < SWEEP_SECS:   # 金光橫掃(菁英)
            band = pygame.Surface((140, H))
            band.fill(self.sweep_color)
            band.set_alpha(70)
            surface.blit(band, (round(-140 + (W + 280) * self.age / SWEEP_SECS),
                                0))
