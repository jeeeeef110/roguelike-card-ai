"""ui/demo_map.py — 完整遊戲循環 demo(U3–U6 串接)

執行:python3 -m ui.demo_map [seed] [進階等級]
循環:讀存檔(save/meta.json)→ 選進階等級 → 一輪冒險(地圖↔戰鬥↔
抉擇面板)→ 結算(碎片/Boss 解鎖三選一/自動存檔)→ 再來一輪。
給了進階等級參數就跳過選擇面板(疊代測試方便)。關窗結束。

養成鐵律(core/meta.py):解鎖「變化」不解鎖「變強」——存檔只影響
可出現的稀有卡池與進階上限,玩家數值不變。
主迴圈 Pygbag 相容(async + await asyncio.sleep(0),A5 守則)。
"""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pygame

from core.meta import MetaState
from core.run import RunState
from ui.choice_panel import ChoicePanel, Option
from ui.map_scene import MapScene
from ui.scenes import Director, Scene
from ui.settle_scene import SettleScene

W, H = 960, 540
SAVE_PATH = Path("save/meta.json")


async def main(seed: int = 7, ascension: int | None = None) -> None:
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("暗夜光網 — 完整循環 demo(U3–U6)")
    meta = (MetaState.load(SAVE_PATH) if SAVE_PATH.exists()
            else MetaState())
    director = Director(W, H)
    director.push(Scene(), transition=None)      # 面板的底層(U7 換 Title)
    state = {"seed": seed, "running": True}

    def start_run(asc: int) -> None:
        run = RunState(state["seed"], ascension=asc,
                       unlocked_rares=list(meta.unlocked_rares))
        director.replace(MapScene(run, on_run_over=run_over))

    def run_over(run) -> None:
        director.push(SettleScene(meta, run, on_done=next_run,
                                  save_path=SAVE_PATH))

    def next_run() -> None:
        state["seed"] += 1
        director.pop(transition=None)   # 收掉結算場景(堆疊回到地圖)
        pick_ascension()                # 選完進階 → replace 成新地圖

    def pick_ascension() -> None:
        if ascension is not None:                # CLI 指定:跳過選擇
            start_run(ascension)
            return
        levels = list(range(meta.ascension_best + 2))

        def choose(i):
            start_run(levels[i])

        director.push(ChoicePanel("選擇進階等級(通關解鎖下一級)", [
            Option(f"進階 {lv}",
                   ["基準難度" if lv == 0 else f"敵人 HP +{lv * 10}%",
                    f"總碎片 {meta.shards}"],
                   (127, 212, 255) if lv == 0 else (255, 184, 77))
            for lv in levels[:4]
        ], choose))

    pick_ascension()
    clock = pygame.time.Clock()
    while state["running"]:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                state["running"] = False
            director.handle(event)
        director.update(clock.tick(60) / 1000)
        director.draw(screen)
        pygame.display.flip()
        await asyncio.sleep(0)      # Pygbag:每幀讓出控制權
    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 7,
                     int(sys.argv[2]) if len(sys.argv) > 2 else None))
