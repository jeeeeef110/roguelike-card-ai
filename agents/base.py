"""agents/base.py — 代理介面與隨機基線

三版代理(rule_based → expectimax → mcts)都實作同一個介面:
    choose_action(state) -> action(engine.legal_actions 回傳格式之一)

代理自帶獨立 RNG(不碰 state.rng),確保:
同一組戰鬥 seed 下,換代理不會改變抽牌序,對照實驗才乾淨。
"""
from random import Random

from core.engine import legal_actions
from core.models import GameState


class Agent:
    """代理基底。子類別覆寫 choose_action。"""

    name = "base"

    def choose_action(self, state: GameState) -> tuple:
        raise NotImplementedError


class RandomAgent(Agent):
    """均勻亂選的地板基線:任何有腦的代理都該贏過它。"""

    name = "random"

    def __init__(self, seed: int = 0):
        self.rng = Random(seed)

    def choose_action(self, state: GameState) -> tuple:
        return self.rng.choice(legal_actions(state))
