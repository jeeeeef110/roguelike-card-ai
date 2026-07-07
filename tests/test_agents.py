"""tests/test_agents.py — 規則式代理的五條規則 + 模擬器的公平性。"""
from agents.base import RandomAgent
from agents.rule_based import RuleBasedAgent
from core.cards import STARTING_DECK
from core.enemies import enemy_ai
from core.engine import apply_action, legal_actions, start_battle
from core.models import EnemyState, GameState, PlayerState
from sim.runner import run_battle, run_many


def battle(hand: list[str], enemy_hp: int = 100, energy: int = 3) -> GameState:
    p = PlayerState(hp=50, max_hp=50, deck=list(STARTING_DECK))
    s = GameState(p, EnemyState("dummy", hp=enemy_hp), seed=1)
    start_battle(s)
    s.player.discard_pile.extend(s.player.hand)
    s.player.hand = list(hand)
    s.player.energy = energy
    return s


def test_rule1_kills_when_possible():
    s = battle(["defend", "strike", "bash"], enemy_hp=5)
    s.enemy.intent = ("attack", 20)          # 就算會挨大刀,能殺就殺
    assert RuleBasedAgent().choose_action(s) == ("play", "strike")


def test_rule2_blocks_lethal():
    s = battle(["strike", "defend", "iron_wall"])
    s.player.hp = 8
    s.enemy.intent = ("attack", 10)          # 10 傷 vs 8 HP:致死
    assert RuleBasedAgent().choose_action(s) == ("play", "iron_wall")


def test_rule3_maximizes_immediate_damage():
    s = battle(["defend", "strike", "bash"])
    s.enemy.intent = ("attack", 5)           # 5 傷 vs 50 HP:不致死,照打
    assert RuleBasedAgent().choose_action(s) == ("play", "bash")  # 8 > 6


def test_rule3_prefers_cheaper_on_tie():
    s = battle(["overdraw", "strike"])       # 透支 12 傷 > 打擊 6 傷
    assert RuleBasedAgent().choose_action(s) == ("play", "overdraw")
    s = battle(["strike", "bloodthirst"], enemy_hp=100)
    s.player.energy = 3                      # 飲血 8 傷 2 費 vs 打擊 6 傷 1 費
    assert RuleBasedAgent().choose_action(s) == ("play", "bloodthirst")


def test_shortsighted_ignores_delayed_value():
    """短視是設計:純鋪墊卡(蓄力/蓄勢/猛毒)沒有立即傷害,不會被選。"""
    s = battle(["empower", "momentum", "deadly_poison"])
    s.enemy.intent = ("block", 6)            # 不挨打 → 也不補甲
    assert RuleBasedAgent().choose_action(s) == ("end_turn",)


def test_never_suicides():
    s = battle(["last_stand", "strike"])     # 背水:14 傷但自傷 3
    s.player.hp = 3
    s.enemy.intent = ("none",)
    assert RuleBasedAgent().choose_action(s) == ("play", "strike")


def test_agent_actions_always_legal():
    for enemy_id in ["giant_rat", "poison_spider", "stone_golem"]:
        agent = RuleBasedAgent()
        p = PlayerState(hp=50, max_hp=50, deck=list(STARTING_DECK))
        from core.enemies import make_enemy
        s = GameState(p, make_enemy(enemy_id), seed=3)
        start_battle(s, enemy_ai)
        for _ in range(300):
            if s.battle_over:
                break
            a = agent.choose_action(s)
            assert a in legal_actions(s)
            apply_action(s, a, enemy_ai)


def test_same_seed_same_battle_outcome():
    a = run_battle(RuleBasedAgent(), "giant_rat", seed=42)
    b = run_battle(RuleBasedAgent(), "giant_rat", seed=42)
    assert a == b


def test_run_many_stats_shape():
    s = run_many(lambda i: RandomAgent(seed=i), "giant_rat", n=30)
    assert s["n"] == 30
    assert 0.0 <= s["win_rate"] <= 1.0
    assert s["avg_turns"] > 0


def test_rule_agent_beats_random_baseline():
    """有腦 vs 沒腦:規則式對每隻敵人的勝率都要高於隨機。"""
    for enemy_id in ["giant_rat", "poison_spider", "stone_golem"]:
        rule = run_many(lambda i: RuleBasedAgent(), enemy_id, n=60)
        rand = run_many(lambda i: RandomAgent(seed=i), enemy_id, n=60)
        assert rule["win_rate"] > rand["win_rate"], (
            f"{enemy_id}:rule {rule['win_rate']:.0%} vs random {rand['win_rate']:.0%}")
