"""ui/demo_map.py — U3 驗收 demo:互動走完一輪地圖(戰鬥自動勝 stub)

執行:python3 -m ui.demo_map [seed]
操作:點擊呼吸閃爍的節點前進;走到 Boss 即勝利。關窗結束。

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


def _auto_win(run, node):
    return True, run.hp     # U3 stub:自動勝(U4 換成 BattleScene)


async def main(seed: int = 7) -> None:
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("暗夜光網 — 地圖 demo(U3)")
    director = Director(W, H)
    director.push(MapScene(RunState(seed), _auto_win))
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
