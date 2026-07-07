"""agents/expectimax.py — Expectimax 代理(三版對照的第二版)

搜尋結構(v2.2 §6.1:深度 2-3,機率節點取樣):
- Max 節點:回合內窮舉出牌序(同名牌已由 legal_actions 去重)
- Chance 節點:end_turn(敵人執行意圖 → 下回合抽 5 + 宣告新意圖,皆隨機)
  → 取樣 K 個未來(determinization),取平均
- depth = 看幾個回合。depth=2:打完這回合、看完下回合

它比規則式多看到的:中毒下回合的扣血、蓄勢/透支的下回合能量、
蓄力加成後的下回合輸出、擋不擋得住下一刀。
它仍看不到的:超過 depth 的長線(毒疊三回合、引爆的最佳等待點)
與牌庫組成知識——那是 MCTS 的主場。

變異數控制:同一層的所有候選動作共用同一組取樣 seed
(common random numbers)——比較是公平的,差異來自動作本身。
出牌用 clone(rng=0):回合內抽牌只有洗牌時才用到 RNG,近乎確定。

葉節點評估(刻意簡單,前瞻本身才是主角):
    勝 = +1000 + 剩餘 HP;敗 = -1000
    否則 = 玩家HP − 1.5×敵HP + 敵中毒層數(視野外的毒粗估一層一滴)
"""
from random import Random

from core.engine import apply_action, legal_actions
from core.models import GameState

from agents.base import Agent

_WIN, _LOSS = 1000.0, -1000.0


def _evaluate(state: GameState) -> float:
    if state.battle_over:
        return _WIN + state.player.hp if state.player_won else _LOSS
    return (state.player.hp - 1.5 * state.enemy.hp + state.enemy.poison)


class ExpectimaxAgent(Agent):
    name = "expectimax"

    def __init__(self, depth: int = 2, samples: int = 3, seed: int = 0):
        self.depth = depth
        self.samples = samples
        self.rng = Random(seed)

    def choose_action(self, state: GameState) -> tuple:
        # 這一手的所有取樣共用同一組 seed:候選動作間的比較才公平
        seeds = [self.rng.randrange(1 << 30) for _ in range(self.samples)]
        actions = legal_actions(state)
        scored = [(self._action_value(state, a, self.depth, seeds), str(a), a)
                  for a in actions]
        return max(scored)[2]  # 平手時以字串序穩定 tie-break

    # ---- Max 節點:回合內 ----

    def _turn_value(self, state: GameState, depth: int,
                    seeds: list[int]) -> float:
        if state.battle_over:
            return _evaluate(state)
        return max(self._action_value(state, a, depth, seeds)
                   for a in legal_actions(state))

    def _action_value(self, state: GameState, action: tuple, depth: int,
                      seeds: list[int]) -> float:
        if action[0] == "end_turn":
            return self._chance_value(state, depth, seeds)
        c = state.clone(rng=0)  # 回合內視為確定性(僅洗牌用 RNG)
        apply_action(c, action)
        if c.battle_over:
            return _evaluate(c)
        return self._turn_value(c, depth, seeds)

    # ---- Chance 節點:跨回合 ----

    def _chance_value(self, state: GameState, depth: int,
                      seeds: list[int]) -> float:
        from core.enemies import ENEMIES, enemy_ai
        # 腦內推演的敵人模型:註冊表裡的用真狀態機;未知敵人(測試 dummy)
        # 假設意圖重複——代理的世界模型,不是遊戲規則
        model = (enemy_ai if state.enemy.enemy_id in ENEMIES
                 else (lambda st: st.enemy.intent))
        total = 0.0
        for seed in seeds:
            c = state.clone(rng=seed)  # determinization:這個未來被定下來
            apply_action(c, ("end_turn",), model)
            if c.battle_over or depth <= 1:
                total += _evaluate(c)
            else:
                total += self._turn_value(c, depth - 1, seeds)
        return total / len(seeds)
