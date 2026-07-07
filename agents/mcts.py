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
                 rollout_turns: int = 20, seed: int = 0):
        self.iterations = iterations
        self.c = c
        self.rollout_turns = rollout_turns
        self.rng = Random(seed)

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
        while not d.battle_over and d.turn < limit:
            apply_action(d, rng.choice(legal_actions(d)), model)
        return _terminal_value(d)
