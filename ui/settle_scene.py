"""ui/settle_scene.py — SettleScene 結算場景(藍圖 A3.3,U6 養成接線)

一輪結束(勝敗皆有,「雖敗猶得」):
- 碎片數字滾動累加(A3.3;點擊可快轉)
- 勝利且尚有未解鎖稀有卡 → Boss 解鎖三選一(收集軸主循環,
  複用 ChoicePanel + 金光橫掃;聚光燈演出留 U7 打磨)
- 每次進度變動即存檔(save_path=None 則不落地,測試/headless 用)

規則零重複:結算數字全來自 meta.settle_run,解鎖走 meta.unlock_rare。
"""
from __future__ import annotations

from pathlib import Path

import pygame

from core.meta import MetaState
from ui.choice_panel import GOLD, ChoicePanel
from ui.choice_scenes import card_option
from ui.scenes import BG, Scene
from ui.text import draw_text
from ui.tween import Tween, linear

W, H = 960, 540
TEXT_MAIN = (232, 240, 255)
TEXT_SUB = (143, 163, 192)
GREEN = (61, 255, 158)
RED = (255, 77, 77)
ROLL_SECS = 1.2


class SettleScene(Scene):
    """on_done():結算(含可能的解鎖三選一)全部結束後呼叫——
    呼叫端接「再來一輪」或關閉。"""

    def __init__(self, meta: MetaState, run, on_done,
                 save_path: str | Path | None = None):
        self.meta = meta
        self.run = run
        self.on_done = on_done
        self.save_path = save_path
        self.shown = 0.0              # 滾動中的碎片數字(tween 驅動)
        self.gained = 0
        self._unlocking = False       # 解鎖面板已推出

    def on_enter(self):
        if self._unlocking:           # 解鎖面板 pop 回來(不重複結算)
            return
        r = self.run
        self.floors = len(r.floor_log)
        self.elites = r.floor_log.count("elite")
        self.gained = self.meta.settle_run(self.floors, self.elites,
                                           r.victory, r.ascension)
        self._save()
        self.director.tweens.add(
            Tween(self, "shown", 0.0, self.gained, ROLL_SECS, linear))

    def _save(self):
        if self.save_path is not None:
            path = Path(self.save_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            self.meta.save(path)

    # ------------------------------------------------------------ 輸入

    def handle(self, event):
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if self.shown < self.gained:          # 第一下:快轉滾動
            self.director.tweens.add(
                Tween(self, "shown", self.gained, self.gained, 0.001))
            return
        if self._unlocking:
            return
        choices = (self.meta.boss_unlock_choices(self.run.rng)
                   if self.run.victory else [])
        if choices:
            self._unlocking = True

            def choose(i):
                self.meta.unlock_rare(choices[i])
                self._save()
                self.on_done()

            self.director.push(ChoicePanel(
                "擊殺 Boss:解鎖一張稀有卡(永久入池)",
                [card_option(c) for c in choices], choose,
                sweep_color=GOLD))            # 不可跳過:收集軸主循環
        else:
            self.on_done()

    # ------------------------------------------------------------ 繪製

    def draw(self, surface):
        surface.fill(BG)
        m, r = self.meta, self.run
        win = r.victory
        draw_text(surface, "冒險勝利" if win else "冒險失敗",
                  (W / 2, 96), 52, GREEN if win else RED,
                  bold=True, align="center")
        lines = [
            f"走過 {self.floors} 層 × 2",
            f"菁英 {self.elites} 場 × 5",
        ]
        if win:
            lines.append("擊殺 Boss + 20")
        if win and r.ascension + 1 == m.ascension_best:
            lines.append(f"解鎖進階 {m.ascension_best}!")
        for i, line in enumerate(lines):
            draw_text(surface, line, (W / 2, 190 + i * 30), 18, TEXT_SUB,
                      align="center")
        draw_text(surface, f"碎片 +{int(self.shown)}", (W / 2, 330), 40,
                  GOLD, bold=True, align="center")
        draw_text(surface, f"總碎片 {m.shards}   戰績 {m.wins}/{m.runs}",
                  (W / 2, 390), 16, TEXT_SUB, align="center")
        hint = ("點擊快轉" if self.shown < self.gained else
                "點擊解鎖新卡" if (r.victory and self.meta.locked_rares()
                                   and not self._unlocking) else "點擊繼續")
        draw_text(surface, hint, (W / 2, H - 44), 15, TEXT_SUB,
                  align="center")
