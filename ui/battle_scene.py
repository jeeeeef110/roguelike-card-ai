"""ui/battle_scene.py — BattleScene 戰鬥場景(藍圖 A3.2,U4 色塊版)

規則零重複:出牌合法性/費用/結算全部問 engine(legal_actions/
apply_action/card_cost),UI 只做呈現與轉譯點擊。文案複用
terminal_play 的 intent_text/card_text(同一套翻譯,兩個前端)。

「所有數值變化皆有動畫」的落法:
- 血條:SmoothBar 300ms 滑動,護甲=條外藍描邊
- 出牌:色塊卡飛向目標(0.25s)→ 目標閃白 2 幀 + 傷害數字上飄淡出
- 意圖:每次宣告用 ease_out_back 從上方彈入
- 藥水:右下三圓槽(A3.2),點擊使用=免費動作,炸出對應色光環
佔位:敵人=色塊剪影+發光描邊;MCTS 建議/Boss 二階段演出接線在
U6–U7(見 PROGRESS)。_choose 卡自動選第一個合法對象。
"""
from __future__ import annotations

import pygame

from core.cards import get_card
from core.engine import apply_action, card_cost, legal_actions
from core.potions import POTIONS
from ui.glow import glow_circle
from ui.scenes import BG, Scene
from ui.terminal_play import ENEMY_NAMES, card_text, intent_text
from ui.text import draw_text
from ui.tween import Tween, ease_out_back
from ui.widgets import ARMOR, PANEL, FloatTextLayer, SmoothBar

W, H = 960, 540
ENEMY_POS = (W // 2, 185)
ENEMY_R = 55
CARD_W, CARD_H = 96, 132
HAND_Y = 524                  # 手牌 midbottom 基準
END_TURN_RECT = pygame.Rect(822, 476, 116, 44)
GHOST_SECS = 0.25             # 出牌飛行時長

HP_GREEN = (61, 255, 158)
HP_RED = (255, 77, 77)
NEUTRAL = (127, 212, 255)
TEXT_MAIN = (232, 240, 255)
TEXT_SUB = (143, 163, 192)
KIND_COLOR = {"attack": HP_RED, "skill": ARMOR}

POTION_SLOTS = ((806, 424), (858, 424), (910, 424))   # 右下三圓槽(A3.2)
POTION_R = 20
BURST_SECS = 0.45          # 使用藥水的光環擴散時長
_EFFECT_COLOR = {"damage": HP_RED, "heal": HP_GREEN, "block": ARMOR,
                 "gain_strength": (255, 184, 77),
                 "apply_poison": (199, 125, 255)}


def _potion_color(pid: str):
    return _EFFECT_COLOR.get(POTIONS[pid].effects[0][0], NEUTRAL)


class _Ghost:
    __slots__ = ("x", "y", "color")

    def __init__(self, x, y, color):
        self.x, self.y, self.color = float(x), float(y), color


class BattleScene(Scene):
    """on_finish(win, hp_left):戰鬥結束、玩家點擊確認後呼叫
    (U5 由 MapScene 接走,把結果餵回 run.enter_node)。"""

    def __init__(self, state, enemy_ai, on_finish=None):
        self.s = state
        self.enemy_ai = enemy_ai
        self.on_finish = on_finish
        self.floats = FloatTextLayer()
        self.outcome: str | None = None
        self._ghost: _Ghost | None = None     # 飛行中 → 輸入鎖
        self._flash = 0                       # 敵人閃白剩餘幀數
        self._intent_pop = 1.0
        self._card_rects: list[tuple] = []    # [(rect, card_id, playable)]
        self._bursts: list[list] = []         # [x, y, age, color] 藥水光環

    def on_enter(self):
        tm = self.director.tweens
        p, e = self.s.player, self.s.enemy
        self.pbar = SmoothBar((30, 26, 280, 14), HP_GREEN, p.max_hp, tm, p.hp)
        self.ebar = SmoothBar((650, 26, 280, 14), HP_RED, e.max_hp, tm, e.hp)
        self._pop_intent()

    # ------------------------------------------------------------ 輸入

    def handle(self, event):
        if event.type != pygame.MOUSEBUTTONDOWN or event.button != 1:
            return
        if self.outcome is not None:
            if self.on_finish is not None:
                self.on_finish(self.s.player_won, max(self.s.player.hp, 0))
            return
        if self._ghost is not None:           # 飛行中不收輸入
            return
        if END_TURN_RECT.collidepoint(event.pos):
            self._end_turn()
            return
        for i, (sx, sy) in enumerate(POTION_SLOTS):
            if ((event.pos[0] - sx) ** 2 + (event.pos[1] - sy) ** 2
                    <= POTION_R ** 2):
                if i < len(self.s.player.potions):
                    self._use_potion(i)
                return
        for rect, cid, playable in reversed(self._card_rects):  # 上層先判
            if rect.collidepoint(event.pos):
                if playable:
                    self._play(cid)
                return

    def _legal_plays(self) -> dict:
        """{card_id: 完整動作}——同名卡取第一個合法動作(_choose 自動選)。"""
        plays = {}
        for a in legal_actions(self.s):
            if a[0] == "play" and a[1] not in plays:
                plays[a[1]] = a
        return plays

    def _play(self, card_id):
        action = self._legal_plays().get(card_id)
        if action is None:
            return
        e0_hp, e0_blk = self.s.enemy.hp, self.s.enemy.block
        p0_hp, p0_blk = self.s.player.hp, self.s.player.block
        apply_action(self.s, action)
        card = get_card(card_id)
        to_enemy = card.kind == "attack"
        tx, ty = ENEMY_POS if to_enemy else (170, 60)
        self._ghost = _Ghost(W / 2, HAND_Y - CARD_H, KIND_COLOR[card.kind])
        tm = self.director.tweens
        tm.add(Tween(self._ghost, "x", self._ghost.x, tx, GHOST_SECS))
        tm.add(Tween(self._ghost, "y", self._ghost.y, ty, GHOST_SECS,
                     on_done=lambda: self._land(e0_hp, e0_blk, p0_hp, p0_blk)))

    def _land(self, e0_hp, e0_blk, p0_hp, p0_blk):
        """卡牌抵達目標:結算已完成,這裡補齊視覺(閃白/飄字/血條)。"""
        self._ghost = None
        p, e = self.s.player, self.s.enemy
        ex, ey = ENEMY_POS
        if e.hp < e0_hp:
            self._flash = 2                   # 受擊閃白 2 幀(A3.2)
            self.floats.spawn(f"-{e0_hp - e.hp}", (ex, ey - ENEMY_R - 8),
                              38, HP_RED)
        if p.block > p0_blk:
            self.floats.spawn(f"+{p.block - p0_blk} 盾", (170, 74), 30, ARMOR)
        if p.hp < p0_hp:                      # 背水等自傷
            self.floats.spawn(f"-{p0_hp - p.hp}", (170, 74), 34, HP_RED)
        self.pbar.set(p.hp)
        self.ebar.set(e.hp)
        self._check_over()

    def _use_potion(self, slot: int):
        """免費動作(不耗能量不計攻擊上限,engine 管);炸對應色光環。"""
        pid = self.s.player.potions[slot]
        if ("potion", pid) not in legal_actions(self.s):
            return
        p, e = self.s.player, self.s.enemy
        p0_hp, p0_blk, e0_hp = p.hp, p.block, e.hp
        apply_action(self.s, ("potion", pid))
        sx, sy = POTION_SLOTS[slot]
        self._bursts.append([sx, sy, 0.0, _potion_color(pid)])
        ex, ey = ENEMY_POS
        if e.hp < e0_hp:
            self._flash = 2
            self.floats.spawn(f"-{e0_hp - e.hp}", (ex, ey - ENEMY_R - 8),
                              38, HP_RED)
        if p.hp > p0_hp:
            self.floats.spawn(f"+{p.hp - p0_hp}", (170, 74), 34, HP_GREEN)
        if p.block > p0_blk:
            self.floats.spawn(f"+{p.block - p0_blk} 盾", (170, 74), 30, ARMOR)
        self.pbar.set(p.hp)
        self.ebar.set(e.hp)
        self._check_over()

    def _end_turn(self):
        p, e = self.s.player, self.s.enemy
        p0_hp, e0_hp = p.hp, e.hp
        apply_action(self.s, ("end_turn",), self.enemy_ai)
        if p.hp < p0_hp:
            self.floats.spawn(f"-{p0_hp - p.hp}", (170, 74), 38, HP_RED)
        if e.hp < e0_hp:                      # 毒 tick
            self.floats.spawn(f"-{e0_hp - e.hp}",
                              (ENEMY_POS[0], ENEMY_POS[1] - ENEMY_R - 8),
                              30, HP_GREEN)
        self.pbar.set(p.hp)
        self.ebar.set(e.hp)
        self._pop_intent()
        self._check_over()

    def _pop_intent(self):
        self._intent_pop = 0.0
        self.director.tweens.add(Tween(self, "_intent_pop", 0.0, 1.0, 0.35,
                                       ease_out_back))

    def _check_over(self):
        if self.s.battle_over:
            self.outcome = "victory" if self.s.player_won else "defeated"

    # ------------------------------------------------------------ 每幀

    def update(self, dt):
        self.floats.update(dt)
        for b in self._bursts:
            b[2] += dt
        self._bursts = [b for b in self._bursts if b[2] < BURST_SECS]

    def draw(self, surface):
        surface.fill(BG)
        s, p, e = self.s, self.s.player, self.s.enemy
        ex, ey = ENEMY_POS

        glow_circle(surface, ENEMY_POS, ENEMY_R, (60, 24, 24))   # 剪影底光
        pygame.draw.circle(surface, PANEL, ENEMY_POS, ENEMY_R)
        pygame.draw.circle(surface, HP_RED, ENEMY_POS, ENEMY_R, width=2)
        if self._flash > 0:                   # 受擊閃白 2 幀
            pygame.draw.circle(surface, TEXT_MAIN, ENEMY_POS, ENEMY_R)
            self._flash -= 1
        draw_text(surface, ENEMY_NAMES[e.enemy_id], (ex, ey + ENEMY_R + 10),
                  18, TEXT_SUB, align="midtop")
        iy = ey - ENEMY_R - 46 - 18 * (1.0 - self._intent_pop)   # 彈入
        draw_text(surface, f"意圖:{intent_text(s, e.intent)}", (ex, iy),
                  22, (255, 184, 77), bold=True, align="midtop")

        self.pbar.draw(surface, armor=p.block)
        self.ebar.draw(surface, armor=e.block)
        draw_text(surface, f"你 {p.hp}/{p.max_hp}"
                  + (f"  盾{p.block}" if p.block else ""), (30, 46), 16, TEXT_MAIN)
        draw_text(surface, f"{ENEMY_NAMES[e.enemy_id]} {e.hp}/{e.max_hp}"
                  + (f"  盾{e.block}" if e.block else ""),
                  (930, 46), 16, TEXT_MAIN, align="topright")
        draw_text(surface, f"能量 {p.energy}  回合 {s.turn}", (30, 70), 16, NEUTRAL)

        self._card_rects = []
        plays = self._legal_plays()
        hand = p.hand
        mx, my = pygame.mouse.get_pos()
        spacing = min(CARD_W + 10, 640 // max(len(hand), 1))
        x0 = W / 2 - spacing * (len(hand) - 1) / 2
        hover = None
        for i, cid in enumerate(hand):
            r = pygame.Rect(0, 0, CARD_W, CARD_H)
            r.midbottom = (round(x0 + i * spacing),
                           HAND_Y + 10 * abs(i - (len(hand) - 1) / 2) ** 0.8)
            if r.collidepoint(mx, my):
                hover = i
        for i, cid in enumerate(hand):
            r = pygame.Rect(0, 0, CARD_W, CARD_H)
            r.midbottom = (round(x0 + i * spacing),
                           HAND_Y + 10 * abs(i - (len(hand) - 1) / 2) ** 0.8)
            if i == hover:
                r.move_ip(0, -20)             # hover 上浮 20px(A3.2)
                r.inflate_ip(8, 10)
            card = get_card(cid)
            playable = cid in plays
            pygame.draw.rect(surface, PANEL, r, border_radius=6)
            pygame.draw.rect(surface, KIND_COLOR[card.kind] if playable
                             else (28, 44, 68), r, width=2, border_radius=6)
            draw_text(surface, str(card_cost(s, cid)), (r.left + 12, r.top + 10),
                      18, NEUTRAL if playable else TEXT_SUB, bold=True)
            draw_text(surface, card.name, (r.centerx, r.top + 30), 16,
                      TEXT_MAIN if playable else TEXT_SUB, align="midtop")
            for li, line in enumerate(card_text(cid).split(";")[:3]):
                draw_text(surface, line, (r.centerx, r.top + 58 + li * 16),
                          11, TEXT_SUB, align="midtop")
            self._card_rects.append((r, cid, playable))

        pygame.draw.rect(surface, PANEL, END_TURN_RECT, border_radius=8)
        pygame.draw.rect(surface, NEUTRAL, END_TURN_RECT, 2, border_radius=8)
        draw_text(surface, "結束回合", END_TURN_RECT.center, 18, TEXT_MAIN,
                  align="center")

        for i, (sx, sy) in enumerate(POTION_SLOTS):   # 藥水三圓槽(A3.2)
            if i < len(p.potions):
                pot = POTIONS[p.potions[i]]
                col = _potion_color(pot.potion_id)
                glow_circle(surface, (sx, sy), POTION_R - 6, col)
                draw_text(surface, pot.name[0], (sx, sy), 15, TEXT_MAIN,
                          bold=True, align="center")
            else:
                pygame.draw.circle(surface, (28, 44, 68), (sx, sy),
                                   POTION_R, width=2)
        for x, y, age, col in self._bursts:           # 使用:光環擴散淡出
            k = age / BURST_SECS
            pygame.draw.circle(
                surface, tuple(int(c * (1 - k)) for c in col),
                (round(x), round(y)), round(POTION_R + 44 * k), width=3)

        if self._ghost is not None:
            g = pygame.Rect(0, 0, 40, 56)
            g.center = (round(self._ghost.x), round(self._ghost.y))
            pygame.draw.rect(surface, self._ghost.color, g, border_radius=4)
        self.floats.draw(surface)

        if self.outcome is not None:
            veil = pygame.Surface((W, H))
            veil.fill(BG)
            veil.set_alpha(190)
            surface.blit(veil, (0, 0))
            msg = "勝利" if self.outcome == "victory" else "倒下了…"
            draw_text(surface, msg, (W / 2, H / 2 - 30), 52, TEXT_MAIN,
                      bold=True, align="center")
            draw_text(surface, "點擊繼續", (W / 2, H / 2 + 30), 18, TEXT_SUB,
                      align="center")
