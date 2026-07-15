"""ui/demo_map.py — 完整一輪冒險 demo:地圖 ↔ 互動戰鬥(U3+U4 串接)

執行:python3 -m ui.demo_map [seed]
操作:點擊呼吸閃爍的節點前進;戰鬥節點會進入 BattleScene 手動對戰,
打完自動回地圖(獎勵暫自動拿第一張,U5 換抉擇面板)。關窗結束。

主迴圈用 Pygbag 相容寫法(async + await asyncio.sleep(0)),
之後打包網頁版不用改(A5 守則:一開始就這樣寫)。
"""
from __future__ import annotations

import asyncio
import sys

import pygame

from core.run import RunState
from ui.map_scene import MapScene
from ui.scenes import Director

W, H = 960, 540


async def main(seed: int = 7) -> None:
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("暗夜光網 — 一輪冒險 demo(U3+U4)")
    director = Director(W, H)
    director.push(MapScene(RunState(seed)))     # 無 hook → 互動戰鬥
    clock = pygame.time.Clock()
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            director.handle(event)
        director.update(clock.tick(60) / 1000)
        director.draw(screen)
        pygame.display.flip()
        await asyncio.sleep(0)      # Pygbag:每幀讓出控制權
    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main(int(sys.argv[1]) if len(sys.argv) > 1 else 7))
