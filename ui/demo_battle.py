"""ui/demo_battle.py — U4 驗收 demo:手動打一場戰鬥

執行:python3 -m ui.demo_battle [giant_rat|poison_spider|stone_golem|
                                 blood_bat|berserker|corrupted_knight] [seed]
操作:點卡牌出牌、點「結束回合」換敵人行動;打完點擊關閉。

主迴圈 Pygbag 相容(async + await asyncio.sleep(0),A5 守則)。
"""
from __future__ import annotations

import asyncio
import sys

import pygame

from core.cards import PLAYER_HP, STARTING_DECK
from core.enemies import ENEMIES, enemy_ai, make_enemy
from core.engine import start_battle
from core.models import GameState, PlayerState
from ui.battle_scene import BattleScene
from ui.scenes import Director

W, H = 960, 540


async def main(enemy_id: str = "giant_rat", seed: int = 0) -> None:
    pygame.init()
    screen = pygame.display.set_mode((W, H))
    pygame.display.set_caption("暗夜光網 — 戰鬥 demo(U4)")
    p = PlayerState(hp=PLAYER_HP, max_hp=PLAYER_HP, deck=list(STARTING_DECK))
    s = GameState(p, make_enemy(enemy_id), seed=seed)
    start_battle(s, enemy_ai)

    finished = []
    director = Director(W, H)
    director.push(BattleScene(s, enemy_ai,
                              on_finish=lambda win, hp: finished.append(win)))
    clock = pygame.time.Clock()
    while not finished:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                finished.append(False)
            director.handle(event)
        director.update(clock.tick(60) / 1000)
        director.draw(screen)
        pygame.display.flip()
        await asyncio.sleep(0)      # Pygbag:每幀讓出控制權
    pygame.quit()


if __name__ == "__main__":
    args = sys.argv[1:]
    eid = args[0] if args and args[0] in ENEMIES else "giant_rat"
    asyncio.run(main(eid, int(args[1]) if len(args) > 1 else 0))
