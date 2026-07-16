"""ui/map_scene.py — MapScene 地圖場景(藍圖 A3.1,U3 色塊版)

分層 DAG 畫成「暗夜光網」:節點發光、可走的下一批呼吸閃爍(錯相)、
走過的路徑亮中性光。點擊可走節點 → 鏡頭推近(zoom 1→1.6, 0.7s)→
經 core 公開 API 結算 → 鏡頭拉回。UI 內不含任何遊戲規則(鐵律)。

節點結算:戰鬥推 BattleScene(U4)、獎勵/休息/商店/事件推抉擇面板
(U5,見 ui/choice_scenes.py);給定 battle_hook 時全部同步結算
(headless 測試/模擬用,不開任何場景)。
佔位:節點=色塊圓(icon U4 美術階段才上);藥水掉落自動撿、滿則放棄。

效能:發光走 ui.glow 烘焙快取——呼吸亮度與縮放半徑都做量化
(亮度 8 階、半徑步進 2),快取鍵有界,不隨動畫幀數膨脹;
邊用普通線(glow_line 的鍵含位移量,鏡頭縮放時會撐爆快取)。
"""
from __future__ import annotations

import math

import pygame

from core.enemies import enemy_ai
from core.engine import start_battle
from core.models import GameState, PlayerState
from core.run import (RunState, enter_node, next_choices, rest_heal,
                      spawn_enemy, take_potion, take_reward)
from ui.battle_scene import BattleScene
from ui.choice_scenes import open_node_result
from ui.glow import glow_circle
from ui.scenes import BG, Scene
from ui.text import draw_text
from ui.tween import Tween

ROW_H = 96              # 每層世界座標高度差(y 遞減 → 越深越上面)
BASE_SPACING = 150      # 第 1 層節點間距
PERSPECTIVE = 0.93      # 每層 x 間距壓縮 7%(近大遠小,A3.1)
NODE_R = 14             # 節點世界半徑(boss ×1.6、菁英 ×1.2)
CLICK_PAD = 10          # 點擊判定加寬
PUSH_ZOOM = 1.6         # 進節點的推近倍率
CAM_SECS = 0.7          # 鏡頭推拉時長(A1:600–900ms)
BREATH_PERIOD = 1.8     # 呼吸週期(A3.1)
BREATH_STAGGER = 2.2    # 可走節點間的相位差(弧度,錯相)
DRIFT_PERIOD = 7.0      # 待機 ±1px 漂浮週期(A1:6–8s)

DIM_LINE = (28, 44, 68)       # 線稿 #1C2C44
NEUTRAL = (127, 212, 255)     # 中性光 #7FD4FF(走過的路徑)
TYPE_COLORS = {               # 色塊版的型別區分(U4 換 icon)
    "battle": (127, 212, 255),   # 中性
    "elite": (255, 184, 77),     # 金(A3.1 稀有時刻)
    "rest": (61, 255, 158),      # 綠
    "shop": (199, 125, 255),     # 紫
    "event": (232, 240, 255),    # 亮白
    "boss": (255, 77, 77),       # 紅、光暈更大
}


def _scaled_color(color, k: float, steps: int = 8):
    """亮度縮放 + 量化(8 階)——量化讓 glow 快取鍵有界。"""
    q = round(max(0.0, min(1.0, k)) * steps) / steps
    return (int(color[0] * q), int(color[1] * q), int(color[2] * q))


def _layout(game_map) -> dict:
    """節點世界座標:{(layer, index): (x, y)}。第 1 層在下(y 大),
    每層 y 遞減、x 間距壓縮 → 近大遠小的透視感。"""
    pos = {}
    n = len(game_map.layers)
    for row in game_map.layers:
        li = row[0].layer
        spacing = BASE_SPACING * PERSPECTIVE ** (li - 1)
        k = len(row)
        for node in row:
            pos[(li, node.index)] = ((node.index - (k - 1) / 2) * spacing,
                                     (n - li) * ROW_H)
    return pos


class MapScene(Scene):
    """battle_hook(run, node) -> (win, hp_left):
    - 給定(headless 測試/模擬)→ 戰鬥同步結算,不開場景
    - None(預設,正式遊戲)→ 戰鬥節點推 BattleScene 互動對戰,
      打完把結果餵回 enter_node(core 三段式不變)"""

    def __init__(self, run: RunState, battle_hook=None, on_run_over=None):
        self.run = run
        self.battle_hook = battle_hook
        self.on_run_over = on_run_over    # 冒險結束(鏡頭拉回後)通知呼叫端
        self.pos = _layout(run.game_map)
        self.t = 0.0
        self.busy = False               # 鏡頭動畫中 → 輸入忽略
        self.outcome: str | None = None  # "victory" / "defeated"
        self.walked: list[tuple] = []    # 走過的節點座標(亮路徑用)

    # ------------------------------------------------------------ 生命週期

    def on_enter(self):
        cam = self.director.camera
        cam.x, cam.y = self._focus_point()
        cam.zoom = 1.0

    def _focus_point(self) -> tuple[float, float]:
        """鏡頭焦點:目前位置往上半層(下一批選項保持在畫面內)。"""
        p = self.run.position
        x, y = self.pos[(p.layer, p.index) if p else (1, 0)]
        return x, y - ROW_H / 2

    # ------------------------------------------------------------ 輸入

    def handle(self, event):
        if (self.busy or self.outcome is not None
                or event.type != pygame.MOUSEBUTTONDOWN or event.button != 1):
            return
        wx, wy = self.director.camera.screen_to_world(*event.pos)
        for node in next_choices(self.run):
            nx, ny = self.pos[(node.layer, node.index)]
            if (wx - nx) ** 2 + (wy - ny) ** 2 <= (NODE_R + CLICK_PAD) ** 2:
                self._walk_to(node)
                return

    def _walk_to(self, node):
        self.busy = True
        cam, tm = self.director.camera, self.director.tweens
        nx, ny = self.pos[(node.layer, node.index)]
        tm.add(Tween(cam, "x", cam.x, nx, CAM_SECS))
        tm.add(Tween(cam, "y", cam.y, ny, CAM_SECS))
        tm.add(Tween(cam, "zoom", cam.zoom, PUSH_ZOOM, CAM_SECS,
                     on_done=lambda: self._resolve(node)))

    def _resolve(self, node):
        """推近完成:戰鬥節點走互動對戰,其餘直接經 core 結算。"""
        if (self.battle_hook is None
                and node.node_type in ("battle", "elite", "boss")):
            self._launch_battle(node)
            return
        self._after_enter(node, enter_node(self.run, node, self.battle_hook))

    def _launch_battle(self, node):
        """把 run 狀態帶進互動戰鬥(藥水進場、戰後寫回剩餘),
        打完以「重播結果」的 hook 餵回 enter_node——core 介面不變。"""
        enemy = spawn_enemy(self.run, node)
        p = PlayerState(hp=self.run.hp, max_hp=self.run.max_hp,
                        deck=list(self.run.deck))
        p.potions = list(self.run.potions)
        state = GameState(p, enemy, seed=self.run.rng.randrange(2 ** 31))
        start_battle(state, enemy_ai)

        def finish(win: bool, hp_left: int):
            self.run.potions = list(state.player.potions)
            self.director.pop(transition="fade")
            self._after_enter(node, enter_node(
                self.run, node, lambda _run, _node: (win, hp_left)))

        self.director.push(BattleScene(state, enemy_ai, on_finish=finish),
                           transition="fade")

    def _after_enter(self, node, out: dict):
        """enter_node 之後:掉落自動撿(藥水滿則放棄,U6 再做替換 UI)。
        互動模式:玩家抉擇交給抉擇面板(U5),收完呼叫 _finish_node;
        headless 模式(有 battle_hook):維持同步佔位策略,不開場景。"""
        self.walked.append((node.layer, node.index))
        if "potion_drop" in out:
            take_potion(self.run, out["potion_drop"])
        if out.get("victory"):
            self.outcome = "victory"
        elif out.get("defeated"):
            self.outcome = "defeated"
        if self.battle_hook is not None:      # headless:獎勵拿第一張、必回血
            if "rewards" in out:
                take_reward(self.run, out["rewards"], out["rewards"][0])
            if "rest_options" in out:
                rest_heal(self.run)
            self._finish_node()
        else:
            open_node_result(self, node, out, self._finish_node)

    def _finish_node(self):
        """節點完全結束:鏡頭拉回、解鎖輸入;冒險結束則通知呼叫端。"""
        cam, tm = self.director.camera, self.director.tweens
        fx, fy = self._focus_point()

        def landed():
            self.busy = False
            if self.outcome is not None and self.on_run_over is not None:
                self.on_run_over(self.run)

        tm.add(Tween(cam, "x", cam.x, fx, CAM_SECS))
        tm.add(Tween(cam, "y", cam.y, fy, CAM_SECS))
        tm.add(Tween(cam, "zoom", cam.zoom, 1.0, CAM_SECS, on_done=landed))

    # ------------------------------------------------------------ 每幀

    def update(self, dt: float):
        self.t += dt

    def _breath(self, i: int) -> float:
        """可走節點的呼吸亮度:0.6↔1.0,週期 1.8s,第 i 個錯相。"""
        return 0.8 + 0.2 * math.sin(2 * math.pi * self.t / BREATH_PERIOD
                                    + i * BREATH_STAGGER)

    def draw(self, surface: pygame.Surface):
        surface.fill(BG)
        cam = self.director.camera
        drift = math.sin(2 * math.pi * self.t / DRIFT_PERIOD)  # ±1px 漂浮
        reachable = {(n.layer, n.index): i
                     for i, n in enumerate(next_choices(self.run))}
        walked_edges = set(zip(self.walked, self.walked[1:]))

        def screen(coord):
            x, y = cam.world_to_screen(*self.pos[coord])
            return (x, y + drift)

        for coord, kids in self.run.game_map.edges.items():
            a = screen(coord)
            for kid in kids:
                lit = (coord, kid) in walked_edges
                pygame.draw.line(surface, NEUTRAL if lit else DIM_LINE,
                                 a, screen(kid), 2 if lit else 1)

        here = self.run.position
        here_coord = (here.layer, here.index) if here else None
        walked = set(self.walked)
        for row in self.run.game_map.layers:
            for node in row:
                coord = (node.layer, node.index)
                if coord in reachable:
                    k = self._breath(reachable[coord])    # 呼吸閃爍
                elif coord == here_coord:
                    k = 1.0                               # 目前所在:全亮
                elif coord in walked:
                    k = 0.7                               # 走過:中亮
                else:
                    k = 0.4                               # 其餘:暗
                mult = 1.6 if node.node_type == "boss" else \
                    1.2 if node.node_type == "elite" else 1.0
                r = max(4, round(NODE_R * mult * cam.zoom / 2) * 2)  # 步進 2
                glow_circle(surface, screen(coord), r,
                            _scaled_color(TYPE_COLORS[node.node_type], k))

        if self.outcome is not None:
            veil = pygame.Surface(surface.get_size())
            veil.fill(BG)
            veil.set_alpha(180)
            surface.blit(veil, (0, 0))
            win = self.outcome == "victory"
            draw_text(surface, "冒險勝利" if win else "冒險失敗",
                      (surface.get_width() / 2, surface.get_height() / 2),
                      52, TYPE_COLORS["rest" if win else "boss"],
                      bold=True, align="center")
