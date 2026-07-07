"""core/engine.py — 戰鬥規則引擎(W1 主體)

職責:解讀 cards.py 的效果指令集、推進回合流程、執行敵人意圖、判定勝負。
本檔不含敵人的「腦」——意圖怎麼選是 enemies.py 的事,由呼叫端以
enemy_ai(state) -> intent 注入;engine 只負責「宣告的意圖如何執行」。

代理接口(三版 AI 與 UI 都只用這三個函式):
    start_battle(state, enemy_ai)             開場:洗牌、進第 1 回合、宣告意圖
    legal_actions(state) -> list[Action]      目前所有合法動作
    apply_action(state, action, enemy_ai)     執行一步(原地修改,搭配 clone 用)

Action 格式:
    ("play", card_id)                出牌
    ("play", card_id, choice_id)     出需要選擇的牌(充能=棄誰 / 回收=撿誰)
    ("end_turn",)                    結束回合

規則定案(v2.2 §3 + 2026-07-07 決策 + v2.3 平衡修正):
- 攻擊上限:每回合最多出 ATTACK_LIMIT 張攻擊卡,「破限」解除當回合上限
- 傷害管線:基礎值 → +力量(逐次攻擊各加成)→ 易傷 ×1.5 向下取整 → 護甲抵銷
- 中毒:玩家回合開始結算雙方,無視護甲、不吃易傷加成,層數 -1
- 引爆:純轉換——不吃力量、不吃易傷、可被護甲抵擋(毒的 tick 穿甲、引爆不穿)
- 易傷:雙方層數在回合結束(敵人行動後)各 -1
- 織網(敵) → attack_cost_delta 在回合結束先歸零、再執行意圖,故效果落在下一回合

敵人意圖指令集(enemies.py 將產生這些;engine 負責執行):
    ("attack", n)  ("attack", n, times)  ("attack_poison", n, p)
    ("block", n)  ("poison", n)  ("web",)  ("charge",)  ("none",)
"""
from core.cards import get_card
from core.models import GameState

# v2.3 平衡修正(Jeff 拍板):每回合最多出 3 張攻擊卡,「破限」可解除當回合上限
ATTACK_LIMIT = 3

# ---------------------------------------------------------------- 傷害管線


def _hit_enemy(state: GameState, base: int, *, use_strength: bool = True,
               use_vulnerable: bool = True) -> None:
    """玩家對敵人的一次攻擊。引爆走 use_strength=use_vulnerable=False。"""
    dmg = base + (state.player.strength if use_strength else 0)
    if use_vulnerable and state.enemy.vulnerable > 0:
        dmg = dmg * 3 // 2
    blocked = min(state.enemy.block, dmg)
    state.enemy.block -= blocked
    state.enemy.hp -= dmg - blocked
    _check_battle_end(state)


def _hit_player(state: GameState, base: int) -> None:
    """敵人對玩家的一次攻擊。"""
    dmg = base + state.enemy.strength
    if state.player.vulnerable > 0:
        dmg = dmg * 3 // 2
    blocked = min(state.player.block, dmg)
    state.player.block -= blocked
    state.player.hp -= dmg - blocked
    _check_battle_end(state)


def _check_battle_end(state: GameState) -> None:
    if state.battle_over:
        return
    if state.enemy.hp <= 0:
        state.battle_over = True
        state.player_won = True
    elif state.player.hp <= 0:
        state.battle_over = True
        state.player_won = False


# ---------------------------------------------------------------- 抽牌


def _draw(state: GameState, n: int) -> None:
    """抽 n 張;牌庫空了就把棄牌堆洗回(用注入的 RNG,同 seed 同順序)。"""
    p = state.player
    for _ in range(n):
        if not p.draw_pile:
            if not p.discard_pile:
                return  # 兩堆皆空,抽不到就算了
            p.draw_pile = p.discard_pile
            p.discard_pile = []
            state.rng.shuffle(p.draw_pile)
        p.hand.append(p.draw_pile.pop())


# ---------------------------------------------------------------- 效果解讀器


def _execute_effect(state: GameState, effect: tuple, choice: str | None) -> None:
    p, e = state.player, state.enemy
    op = effect[0]
    if op == "damage":
        _hit_enemy(state, effect[1])
    elif op == "damage_bonus_vs_vulnerable":
        base, bonus = effect[1], effect[2]
        _hit_enemy(state, base + (bonus if e.vulnerable > 0 else 0))
    elif op == "damage_per_vulnerable":
        _hit_enemy(state, effect[1] + effect[2] * e.vulnerable)
    elif op == "damage_per_attack_played":
        _hit_enemy(state, effect[1] + effect[2] * p.attacks_played)
    elif op == "damage_equal_block":
        _hit_enemy(state, p.block)
    elif op == "damage_shatter":
        _hit_enemy(state, effect[1])
        if e.block > 0:  # 追加傷害 = 移除的護甲量,直接進 HP
            shattered = e.block
            e.block = 0
            e.hp -= shattered
            _check_battle_end(state)
    elif op == "detonate_poison":
        if e.poison > 0:
            _hit_enemy(state, e.poison * effect[1],
                       use_strength=False, use_vulnerable=False)
            e.poison = 0
    elif op == "block":
        p.block += effect[1]
    elif op == "retain_block":
        p.block_retain = True
    elif op == "lift_attack_limit":
        p.attack_limit_off = True
    elif op == "apply_vulnerable":
        e.vulnerable += effect[1]
    elif op == "apply_poison":
        e.poison += effect[1]
    elif op == "gain_strength":
        p.strength += effect[1]
    elif op == "draw":
        _draw(state, effect[1])
    elif op == "gain_energy":
        p.energy += effect[1]
    elif op == "next_turn_energy":
        p.next_energy_delta += effect[1]
    elif op == "heal":
        p.hp = min(p.max_hp, p.hp + effect[1])
    elif op == "self_damage":  # 代價自選:直接扣 HP、不經護甲,可能陣亡
        p.hp -= effect[1]
        _check_battle_end(state)
    elif op == "discard_choose":  # 充能:沒牌可棄就跳過,能量照拿
        if choice is not None and choice in p.hand:
            p.hand.remove(choice)
            p.discard_pile.append(choice)
    elif op == "retrieve_choose":  # 回收:棄牌堆空就落空
        if choice is not None and choice in p.discard_pile:
            p.discard_pile.remove(choice)
            p.hand.append(choice)
    else:
        raise ValueError(f"未知的效果 opcode:{op!r}")


# ---------------------------------------------------------------- 出牌


def card_cost(state: GameState, card_id: str) -> int:
    """實際費用:攻擊卡吃織網修正,下限 0。"""
    card = get_card(card_id)
    if card.kind == "attack":
        return max(0, card.cost + state.player.attack_cost_delta)
    return card.cost


def play_card(state: GameState, card_id: str, choice: str | None = None) -> None:
    p = state.player
    if state.battle_over:
        raise ValueError("戰鬥已結束,不能出牌")
    if card_id not in p.hand:
        raise ValueError(f"手牌中沒有 {card_id!r}")
    cost = card_cost(state, card_id)
    if p.energy < cost:
        raise ValueError(f"能量不足:{card_id} 需要 {cost},只有 {p.energy}")
    card = get_card(card_id)
    if (card.kind == "attack" and p.attacks_played >= ATTACK_LIMIT
            and not p.attack_limit_off):
        raise ValueError(f"本回合攻擊卡已達上限 {ATTACK_LIMIT} 張(破限可解除)")
    p.energy -= cost
    p.hand.remove(card_id)  # 先離手:充能不能棄自己、回收不能撿到自己
    for effect in card.effects:
        _execute_effect(state, effect, choice)
        if state.battle_over:
            break
    p.discard_pile.append(card_id)
    if card.kind == "attack":
        p.attacks_played += 1  # 撕裂計數:結算後才 +1,故撕裂不算自己


# ---------------------------------------------------------------- 敵人意圖執行


def _execute_intent(state: GameState) -> None:
    intent = state.enemy.intent
    kind = intent[0]
    if kind == "attack":
        times = intent[2] if len(intent) > 2 else 1
        for _ in range(times):
            if state.battle_over:
                return
            _hit_player(state, intent[1])
    elif kind == "attack_poison":
        _hit_player(state, intent[1])
        if not state.battle_over:
            state.player.poison += intent[2]
    elif kind == "block":
        state.enemy.block += intent[1]
    elif kind == "poison":
        state.player.poison += intent[1]
    elif kind == "web":  # 織網:玩家下回合攻擊卡費用 +1
        state.player.attack_cost_delta += 1
    elif kind in ("charge", "none"):
        pass  # 蓄力的「下回合打 12」由 enemies.py 的狀態機決定
    else:
        raise ValueError(f"未知的意圖:{kind!r}")


# ---------------------------------------------------------------- 回合流程


def _start_turn(state: GameState) -> None:
    p, e = state.player, state.enemy
    state.turn += 1
    # 格擋歸零(堅守例外,旗標用過即清)
    if p.block_retain:
        p.block_retain = False
    else:
        p.block = 0
    # 中毒結算:雙方都在玩家回合開始,無視護甲、不吃易傷,層數 -1
    if e.poison > 0:
        e.hp -= e.poison
        e.poison -= 1
        _check_battle_end(state)
    if p.poison > 0 and not state.battle_over:
        p.hp -= p.poison
        p.poison -= 1
        _check_battle_end(state)
    # 能量回滿 + 蓄勢/透支修正(修正用過即清)
    p.energy = max(0, p.base_energy + p.next_energy_delta)
    p.next_energy_delta = 0
    _draw(state, 5)


def start_battle(state: GameState, enemy_ai=None) -> None:
    """開場:洗牌庫、進第 1 回合、宣告意圖。"""
    state.rng.shuffle(state.player.draw_pile)
    _start_turn(state)
    if enemy_ai is not None:
        state.enemy.intent = enemy_ai(state)


def end_turn(state: GameState, enemy_ai=None) -> None:
    """回合結束:棄手牌 → 敵人行動 → 易傷倒數 → 進下一回合並宣告新意圖。"""
    p, e = state.player, state.enemy
    p.discard_pile.extend(p.hand)
    p.hand = []
    p.attacks_played = 0
    p.attack_limit_off = False
    p.attack_cost_delta = 0  # 先清,織網若在下面執行會重新設上 → 效果落在下回合
    if not e.block_persists:
        e.block = 0
    if not state.battle_over:
        _execute_intent(state)
    p.vulnerable = max(0, p.vulnerable - 1)
    e.vulnerable = max(0, e.vulnerable - 1)
    if not state.battle_over:
        _start_turn(state)
        if enemy_ai is not None:
            e.intent = enemy_ai(state)


# ---------------------------------------------------------------- 代理接口


def legal_actions(state: GameState) -> list[tuple]:
    """目前所有合法動作。同名手牌只列一次(搜尋分支去重)。"""
    if state.battle_over:
        return []
    p = state.player
    actions: list[tuple] = []
    seen: set[tuple] = set()
    at_limit = p.attacks_played >= ATTACK_LIMIT and not p.attack_limit_off
    for card_id in p.hand:
        if p.energy < card_cost(state, card_id):
            continue
        card = get_card(card_id)
        if card.kind == "attack" and at_limit:
            continue
        needs_choice = any(e[0].endswith("_choose") for e in card.effects)
        if not needs_choice:
            a = ("play", card_id)
            if a not in seen:
                seen.add(a)
                actions.append(a)
            continue
        # 充能:可棄對象 = 其他手牌;回收:可撿對象 = 棄牌堆。無對象也可打(效果落空)
        pool = (p.discard_pile if any(e[0] == "retrieve_choose" for e in card.effects)
                else [c for c in p.hand if c != card_id])
        for target in (list(dict.fromkeys(pool)) or [None]):
            a = ("play", card_id, target)
            if a not in seen:
                seen.add(a)
                actions.append(a)
    actions.append(("end_turn",))
    return actions


def apply_action(state: GameState, action: tuple, enemy_ai=None) -> None:
    if action[0] == "play":
        play_card(state, action[1], action[2] if len(action) > 2 else None)
    elif action[0] == "end_turn":
        end_turn(state, enemy_ai)
    else:
        raise ValueError(f"未知的動作:{action!r}")
