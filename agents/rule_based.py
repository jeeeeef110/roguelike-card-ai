"""agents/rule_based.py — 規則式代理(三版對照的第一版)

策略(v2.2 §6.1:優先擋致死、再最大化即時輸出,設計上刻意短視):
1. 有動作能直接殺死敵人 → 立刻執行
2. 敵人這回合的攻擊會打死自己 → 選加最多護甲的動作
3. 否則 → 選「立即傷害」最高的動作(同傷害選費用低的)
4. 沒有立即傷害可打 → 若還會挨打,補護甲
5. 都沒有 → 結束回合

「即時輸出」的定義:把動作在複本上試執行一次,量敵方(HP+護甲)總削減——
打進護甲也算輸出,否則會對著石像兵的疊甲發呆到判負(v2.3 模擬實測教訓)。
它天生看不見的仍然很多:中毒的未來扣血、蓄力/蓄勢的延遲收益、引爆的
等待價值、充能/回收的資源轉換(立即輸出=0,永遠墊底)。這些盲點正是
Expectimax / MCTS 要拉開差距的地方——不要「修好」它。

評估用複本一律 clone(rng=0):與本尊 RNG 隔離,試打中的抽牌
不會推進真實戰鬥的亂數序,同 seed 重播才成立。
"""
from random import Random

from core.engine import apply_action, card_cost, enemy_attack_value, legal_actions
from core.models import GameState

from agents.base import Agent


def _incoming_damage(state: GameState) -> int:
    """敵人已宣告意圖這回合會打多少(護甲結算前)。非攻擊意圖 = 0。"""
    intent = state.enemy.intent
    if intent[0] == "attack":
        times = intent[2] if len(intent) > 2 else 1
        return enemy_attack_value(state, intent[1]) * times
    if intent[0] == "attack_poison":
        return enemy_attack_value(state, intent[1])
    return 0


_SCRATCH_RNG = Random(0)  # 評估複本共用,免重複播種


def _try(state: GameState, action: tuple) -> GameState:
    """在隔離 RNG 的複本上試執行一個動作(不推進真實戰鬥的亂數序)。"""
    c = state.clone(rng=_SCRATCH_RNG)
    apply_action(c, action)
    return c


class RuleBasedAgent(Agent):
    name = "rule_based"

    def choose_action(self, state: GameState) -> tuple:
        plays = [a for a in legal_actions(state) if a[0] == "play"]
        if not plays:
            return ("end_turn",)

        # 每個動作試打一次,量立即變化。排序 + 費用 tie-break,保證確定性
        evals = []
        for action in sorted(plays, key=str):
            after = _try(state, action)
            if after.battle_over and not after.player_won:
                continue  # 這一下會把自己打死(如殘血出背水),直接排除
            evals.append((
                action,
                (state.enemy.hp - after.enemy.hp)         # 立即輸出:
                + (state.enemy.block - after.enemy.block),  # 血+甲總削減
                after.player.block - state.player.block,  # 立即護甲
                -card_cost(state, action[1]),             # 同分時選便宜的
                after.battle_over and after.player_won,   # 這一下直接獲勝
            ))
        if not evals:
            return ("end_turn",)

        winners = [e for e in evals if e[4]]
        if winners:  # 規則 1:能殺就殺(多個殺招選便宜的)
            return max(winners, key=lambda x: x[3])[0]

        incoming = _incoming_damage(state)
        p = state.player
        if incoming - p.block >= p.hp:  # 規則 2:擋致死
            action, _, gain, _, _ = max(evals, key=lambda x: (x[2], x[3]))
            if gain > 0:
                return action

        best, dmg, _, _, _ = max(evals, key=lambda x: (x[1], x[3]))
        if dmg > 0:
            return best  # 規則 3:最大化即時輸出

        if incoming > p.block:  # 規則 4:反正要挨打,補甲
            action, _, gain, _, _ = max(evals, key=lambda x: (x[2], x[3]))
            if gain > 0:
                return action

        return ("end_turn",)  # 規則 5:沒事做了
