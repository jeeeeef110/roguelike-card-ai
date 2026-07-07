"""tests/test_expectimax.py — 前瞻能力:規則式看不見的,Expectimax 要看見。"""
from agents.expectimax import ExpectimaxAgent
from agents.rule_based import RuleBasedAgent
from core.cards import STARTING_DECK
from core.enemies import enemy_ai, make_enemy
from core.engine import apply_action, legal_actions, start_battle
from core.models import EnemyState, GameState, PlayerState


def battle(hand: list[str], enemy_hp: int = 100, energy: int = 3) -> GameState:
    p = PlayerState(hp=50, max_hp=50, deck=list(STARTING_DECK))
    s = GameState(p, EnemyState("dummy", hp=enemy_hp), seed=1)
    start_battle(s)
    s.player.discard_pile.extend(s.player.hand)
    s.player.hand = list(hand)
    s.player.energy = energy
    return s


def test_sees_poison_killing_next_turn_where_rule_agent_is_blind():
    """敵剩 4 血,手上只有猛毒(立即傷害 0)。
    規則式:沒有立即輸出 → 直接結束回合(盲點)。
    Expectimax depth=2:毒 4 → 下回合開始 tick 4 → 敵死 → 出毒。"""
    def scenario():
        s = battle(["deadly_poison"], enemy_hp=4)
        s.enemy.intent = ("block", 6)
        return s
    assert RuleBasedAgent().choose_action(scenario()) == ("end_turn",)
    assert ExpectimaxAgent(depth=2).choose_action(scenario()) == \
        ("play", "deadly_poison")


def test_takes_immediate_kill():
    s = battle(["strike", "defend"], enemy_hp=5)
    assert ExpectimaxAgent().choose_action(s) == ("play", "strike")


def test_blocks_lethal_via_lookahead():
    """不出防禦 → 下回合已死(-1000)。前瞻自然導出擋致死,不需手寫規則。"""
    s = battle(["iron_wall", "strike"])
    s.player.hp = 8
    s.enemy.intent = ("attack", 10)
    assert ExpectimaxAgent(depth=2).choose_action(s) == ("play", "iron_wall")


def test_deterministic_given_seed():
    a = ExpectimaxAgent(seed=7)
    b = ExpectimaxAgent(seed=7)
    s1, s2 = battle(["strike", "bash", "defend"]), battle(["strike", "bash", "defend"])
    for _ in range(3):
        x, y = a.choose_action(s1), b.choose_action(s2)
        assert x == y
        apply_action(s1, x)
        apply_action(s2, y)


def test_actions_always_legal_full_battles():
    for enemy_id in ["giant_rat", "poison_spider", "stone_golem"]:
        agent = ExpectimaxAgent(seed=5)
        p = PlayerState(hp=50, max_hp=50, deck=list(STARTING_DECK))
        s = GameState(p, make_enemy(enemy_id), seed=11)
        start_battle(s, enemy_ai)
        for _ in range(200):
            if s.battle_over:
                break
            a = agent.choose_action(s)
            assert a in legal_actions(s)
            apply_action(s, a, enemy_ai)
        assert s.battle_over  # 200 步內要打完
