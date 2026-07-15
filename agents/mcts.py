"""agents/mcts.py — MCTS+UCB1 代理(三版對照的第三版,v2.2 §6.1)

每次迭代四步:
1. Determinization:root.clone(rng=取樣 seed)——把未知資訊(之後的洗牌、
   敵人意圖骰子)在這個假想未來裡「定下來」
2. 選擇:沿樹用 UCB1 走(只在該 determinization 下合法的動作中選,
   Information-Set MCTS 的簡化版:同一棵樹在多個假想未來上取平均)
3. 擴展 + 模擬:碰到沒展開的動作就展開,之後隨機亂打到終局
4. 回傳:勝 1 / 敗 0,超過模擬回合上限用血量差折算,沿路徑更新

它比 Expectimax 多看到的:超過固定深度的長線(毒疊多回合再引爆、
蓄力幾回合再亂舞)——rollout 隨機撞到好結局,樹就會往那邊長。
代價:同樣的思考時間,答案是統計性的(iterations 越多越準)。

確定性:給定 seed,determinization 序列與 rollout 選擇全部可重播。
"""
from math import log, sqrt
from random import Random

from core.cards import get_card
from core.engine import apply_action, legal_actions
from core.models import GameState

from agents.base import Agent, enemy_model


class _Node:
    __slots__ = ("visits", "value", "children")

    def __init__(self):
        self.visits = 0
        self.value = 0.0
        self.children: dict[tuple, _Node] = {}


def _terminal_value(state: GameState) -> float:
    """勝 1、敗 0;沒打完(模擬上限)用雙方血量比例折算到 0.05–0.95。"""
    if state.battle_over:
        return 1.0 if state.player_won else 0.0
    diff = (state.player.hp / state.player.max_hp
            - state.enemy.hp / state.enemy.max_hp)
    return min(0.95, max(0.05, 0.5 + 0.4 * diff))


class MCTSAgent(Agent):
    name = "mcts"

    def __init__(self, iterations: int = 200, c: float = 1.4,
                 rollout_turns: int = 20, seed: int = 0,
                 rollout: str = "random"):
        self.iterations = iterations
        self.c = c
        self.rollout_turns = rollout_turns
        self.rng = Random(seed)
        assert rollout in ("random", "heuristic")
        self.rollout = rollout

    def choose_action(self, state: GameState) -> tuple:
        actions = legal_actions(state)
        if len(actions) == 1:
            return actions[0]
        model = enemy_model(state)
        root = _Node()
        for _ in range(self.iterations):
            d = state.clone(rng=self.rng.randrange(1 << 30))
            rollout_rng = Random(self.rng.randrange(1 << 30))
            self._iterate(root, d, model, rollout_rng)
        # 選訪問次數最多的動作(比選平均值穩);tie-break 字串序,保證確定性
        return max(root.children.items(),
                   key=lambda kv: (kv[1].visits, str(kv[0])))[0]

    def _iterate(self, node: _Node, d: GameState, model, rng: Random) -> None:
        path = [node]
        value = None
        while not d.battle_over:
            acts = legal_actions(d)
            fresh = [a for a in acts if a not in node.children]
            if fresh:  # 擴展:先鋪滿沒試過的動作
                action = rng.choice(fresh)
                child = _Node()
                node.children[action] = child
                apply_action(d, action, model)
                path.append(child)
                value = self._rollout(d, model, rng)
                break
            # UCB1 選擇(只看這個 determinization 下合法的孩子)
            log_n = log(node.visits)
            action = max(acts, key=lambda a: (
                node.children[a].value / node.children[a].visits
                + self.c * sqrt(log_n / node.children[a].visits)))
            node = node.children[action]
            apply_action(d, action, model)
            path.append(node)
        if value is None:  # 走到終局才跳出:直接評分
            value = _terminal_value(d)
        for n in path:
            n.visits += 1
            n.value += value

    def _rollout(self, d: GameState, model, rng: Random) -> float:
        limit = d.turn + self.rollout_turns
        pick = (self._heuristic_pick if self.rollout == "heuristic"
                else (lambda st, acts, r: r.choice(acts)))
        while not d.battle_over and d.turn < limit:
            acts = legal_actions(d)
            apply_action(d, pick(d, acts, rng), model)
        return _terminal_value(d)

    @staticmethod
    def _heuristic_pick(d: GameState, acts: list[tuple], rng: Random) -> tuple:
        """ε-greedy 快速策略(rollout 專用,零複本試打):
        80% 選靜態分數最高的動作,20% 均勻亂選(保留探索,避免 rollout
        全走同一條線讓估值變成單點)。

        靜態分數 = 卡面傷害 + 卡面護甲(敵人意圖是攻擊時護甲加權 1.2)。
        刻意粗糙:只讀卡牌定義,不模擬。它的工作不是「玩得好」,
        是讓 rollout 的雜訊小到樹統計得出「防禦有價值」——
        隨機 rollout 低估防禦的問題(PROGRESS 待辦 #2 歸因 (2))出在
        亂打的未來裡護甲常常白疊,估值分不出好壞。
        """
        if rng.random() < 0.2:
            return rng.choice(acts)
        incoming = d.enemy.intent[0] in ("attack", "attack_poison")
        best, best_score = acts[0], -1.0
        for a in acts:
            if a[0] != "play":
                score = 0.0  # end_turn:墊底但存在,全負分時可被選
            else:
                dmg = blk = 0
                for eff in get_card(a[1]).effects:
                    op = eff[0]
                    if op == "damage":
                        dmg += eff[1]
                    elif op in ("damage_bonus_vs_vulnerable",
                                "damage_per_vulnerable",
                                "damage_per_attack_played",
                                "damage_shatter"):
                        dmg += eff[1]
                    elif op == "damage_equal_block":   # 反甲擊:看當下護甲
                        dmg += d.player.block
                    elif op == "detonate_poison":      # 引爆:看當下毒層
                        dmg += d.enemy.poison * eff[1]
                    elif op == "block":
                        blk += eff[1]
                score = dmg + blk * (1.2 if incoming else 0.5)
            if score > best_score:
                best, best_score = a, score
        return best
