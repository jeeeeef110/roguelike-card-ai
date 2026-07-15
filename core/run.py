"""core/run.py — 一輪冒險的完整流程(M2:v2.2 §4.1 核心循環)

選節點 → 戰鬥/事件/商店/休息 → 獎勵 → … → Boss。

設計(與 events.py 同一套哲學):
- RunState 是可變狀態(deck/hp/gold/位置),但所有「玩家選擇」都走
  「查詢選項 → 呼叫端決定 → 執行」的三段式,run.py 不擁有任何 UI 或代理。
- 戰鬥本身委派給呼叫端:battle_hook(run, enemy_id) -> (win, hp_left)。
  headless 測試給它接代理,之後 Pygame 給它接互動戰鬥,run.py 不變。
- 隨機性:RunState.rng(注入 seed),與戰鬥內的 RNG 分離
  (地圖、獎勵、事件抽卡都吃它;同 seed 同一輪冒險)。

經濟數值(初始值,待 A/B 調整,勿當定案):
    戰勝 +25 金;商店:稀有卡 65 金、刪卡 50 金;休息回 30% max HP
"""
from __future__ import annotations

from random import Random

from core.cards import CARDS, PLAYER_HP, RARITY_WEIGHTS, STARTING_DECK
from core.events import EVENT_IDS, _smith_id
from core.potions import (MAX_POTIONS, POTION_DROP_RATE, POTION_PRICE,
                          POTIONS)
from core.map_gen import GameMap, MapNode, generate_map

GOLD_PER_WIN = 25
GOLD_PER_ELITE = 45           # 菁英:高風險高報酬
ELITE_HP_MULT = 1.35          # 菁英強化(初始值待平衡)
ELITE_START_STRENGTH = 1
ASCENSION_HP_STEP = 0.10      # 進階:每級敵人 HP +10%(初始值待平衡)
SHOP_CARD_PRICE = 65
SHOP_REMOVE_PRICE = 50
REST_HEAL_RATIO = 0.30
REWARD_CHOICES = 3


class RunState:
    """一輪冒險的狀態。position 是目前所在節點(進 Boss 前的最後位置)。"""

    __slots__ = ("deck", "hp", "max_hp", "gold", "game_map", "position",
                 "rng", "over", "victory", "floor_log", "ascension", "potions",
                 "unlocked_rares")

    def __init__(self, seed: int, ascension: int = 0, n_layers: int = 10,
                 unlocked_rares: list[str] | None = None):
        # 收集軸:本輪可出現的稀有卡(None=全開,測試/模擬器預設;
        # 正式遊戲由 MetaState.unlocked_rares 傳入)
        self.unlocked_rares = unlocked_rares
        self.ascension = ascension          # 進階等級:通關解鎖下一級(重玩軸)
        self.deck: list[str] = list(STARTING_DECK)
        self.max_hp = PLAYER_HP
        self.hp = PLAYER_HP
        self.gold = 0
        self.potions: list[str] = []
        self.game_map: GameMap = generate_map(seed, n_layers)
        self.position: MapNode | None = None   # None = 尚未踏入第 1 層
        self.rng = Random(seed ^ 0x5EED)       # 與地圖 seed 派生但獨立
        self.over = False
        self.victory = False
        self.floor_log: list[str] = []         # 走過的節點型別(報告/除錯用)


def next_choices(run: RunState) -> tuple[MapNode, ...]:
    """目前可走的下一批節點。冒險結束回傳空 tuple。"""
    if run.over:
        return ()
    if run.position is None:
        return tuple(run.game_map.layers[0])
    return run.game_map.children(run.position)


def spawn_enemy(run: RunState, node: MapNode):
    """依節點與進階等級生成敵人(battle_hook 一律經此,倍率才會一致):
    菁英 = HP ×1.35 + 起手力量 1;進階每級全體敵人 HP +10%。"""
    from core.enemies import make_enemy  # 區域 import:避免 run↔enemies 循環
    e = make_enemy(node.enemy_id)
    mult = 1.0 + ASCENSION_HP_STEP * run.ascension
    if node.node_type == "elite":
        mult *= ELITE_HP_MULT
        e.strength += ELITE_START_STRENGTH
    e.hp = e.max_hp = int(e.max_hp * mult)
    return e


def _rare_allowed(run: RunState, cid: str) -> bool:
    return run.unlocked_rares is None or cid in run.unlocked_rares


def draw_rewards(run: RunState, rare_only: bool = False) -> list[str]:
    """戰勝獎勵:三選一(稀有度加權、同批不重複、起始卡不入池、
    未解鎖的稀有卡不入池)。菁英戰 rare_only=True:全稀有——
    「build 定義時刻」。池內不重複卡種少於 3 時,發多少算多少(防呆)。"""
    pool: list[str] = []
    for cid, card in CARDS.items():
        w = RARITY_WEIGHTS.get(card.rarity, 0)
        if rare_only and card.rarity != "rare":
            w = 0
        if card.rarity == "rare" and not _rare_allowed(run, cid):
            w = 0
        pool.extend([cid] * w)
    picks: list[str] = []
    distinct = len(set(pool))
    while len(picks) < min(REWARD_CHOICES, distinct):
        c = run.rng.choice(pool)
        if c not in picks:
            picks.append(c)
    return picks


def enter_node(run: RunState, node: MapNode, battle_hook) -> dict:
    """走進一個節點並結算「非選擇」的部分,回傳該節點的後續資訊:
    - battle/boss:打完仗。勝 → {"rewards": [三張卡]}(呼叫端再 take_reward)
                   敗 → run.over,{"defeated": True}
    - rest:直接回血,{"healed": n}
    - shop:{"shop": {"card": 稀有卡id, "card_price":…, "remove_price":…}}
    - event:{"event": 事件id}(選項執行走 events.py 的函式)
    """
    if node not in next_choices(run):
        raise ValueError("不可跳層/走沒有連線的節點")
    run.position = node
    run.floor_log.append(node.node_type)

    if node.node_type in ("battle", "elite", "boss"):
        win, hp_left = battle_hook(run, node)
        if not win:
            run.over = True
            return {"defeated": True}
        run.hp = hp_left
        if node.node_type == "boss":
            run.over = True
            run.victory = True
            return {"victory": True}
        if node.node_type == "elite":
            run.gold += GOLD_PER_ELITE
            return {"rewards": draw_rewards(run, rare_only=True)}
        run.gold += GOLD_PER_WIN
        out = {"rewards": draw_rewards(run)}
        if run.rng.random() < POTION_DROP_RATE:
            out["potion_drop"] = run.rng.choice(sorted(POTIONS))
        return out

    if node.node_type == "rest":
        return {"rest_options": ("heal", "upgrade")}

    if node.node_type == "shop":
        rares = [cid for cid, c in CARDS.items()
                 if c.rarity == "rare" and _rare_allowed(run, cid)]
        return {"shop": {"card": run.rng.choice(rares),
                         "card_price": SHOP_CARD_PRICE,
                         "remove_price": SHOP_REMOVE_PRICE,
                         "potion": run.rng.choice(sorted(POTIONS)),
                         "potion_price": POTION_PRICE}}

    return {"event": run.rng.choice(EVENT_IDS)}


def take_reward(run: RunState, rewards: list[str], pick: str | None) -> None:
    """三選一收卡;pick=None = 跳過。"""
    if pick is not None:
        if pick not in rewards:
            raise ValueError("只能拿本批提供的卡")
        run.deck.append(pick)


def shop_buy_card(run: RunState, card_id: str) -> None:
    if run.gold < SHOP_CARD_PRICE:
        raise ValueError("金幣不足")
    run.gold -= SHOP_CARD_PRICE
    run.deck.append(card_id)


def shop_remove_card(run: RunState, position: int) -> None:
    if run.gold < SHOP_REMOVE_PRICE:
        raise ValueError("金幣不足")
    run.gold -= SHOP_REMOVE_PRICE
    del run.deck[position]


def rest_heal(run: RunState) -> int:
    """休息選項 A:回血 30% max HP。回傳實際回復量。"""
    healed = min(run.max_hp - run.hp, int(run.max_hp * REST_HEAL_RATIO))
    run.hp += healed
    return healed


def rest_upgrade(run: RunState, position: int) -> str:
    """休息選項 B:鍛造一張卡(費用 -1,同鐵匠)。回傳升級後的 id。
    《殺戮尖塔》的核心抉擇:回血保命 vs 變強走遠——每個休息點都是一題。"""
    run.deck[position] = _smith_id(run.deck[position])
    return run.deck[position]


def take_potion(run: RunState, potion_id: str) -> bool:
    """拾取藥水;滿 3 瓶回傳 False(UI 可先問要不要丟舊的)。"""
    if len(run.potions) >= MAX_POTIONS:
        return False
    run.potions.append(potion_id)
    return True


def shop_buy_potion(run: RunState, potion_id: str) -> None:
    if run.gold < POTION_PRICE:
        raise ValueError("金幣不足")
    if len(run.potions) >= MAX_POTIONS:
        raise ValueError("藥水已滿(上限 3)")
    run.gold -= POTION_PRICE
    run.potions.append(potion_id)
