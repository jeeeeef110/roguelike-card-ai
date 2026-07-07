"""tests/test_mcts.py — MCTS:正確性、前瞻、確定性、整場行為。"""
from agents.mcts import MCTSAgent
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


def test_takes_immediate_kill():
    s = battle(["strike", "defend"], enemy_hp=5)
    s.enemy.intent = ("attack", 6)
    assert MCTSAgent(iterations=100, seed=1).choose_action(s) == \
        ("play", "strike")


def test_sees_poison_kill_like_expectimax():
    s = battle(["deadly_poison"], enemy_hp=4)
    s.enemy.intent = ("block", 6)
    assert MCTSAgent(iterations=100, seed=1).choose_action(s) == \
        ("play", "deadly_poison")


def test_blocks_lethal_when_survival_leads_to_win():
    """能量 2:鐵壁(2 費)/打擊(1 費)擇一。敵剩 15 血:
    出打擊 → 回合結束挨 10 必死(勝率 0);
    出鐵壁 → 擋下這刀,之後幾回合有充分機會磨死它。
    註:若敵人血量高到反殺無望,MCTS 判斷「擋不擋都輸」是正確行為——
    它最大化的是勝率,不是存活回合數(初版測試就是這樣寫錯的)。"""
    s = battle(["iron_wall", "strike"], enemy_hp=15, energy=2)
    s.player.hp = 8
    s.enemy.intent = ("attack", 10)
    assert MCTSAgent(iterations=300, seed=1).choose_action(s) == \
        ("play", "iron_wall")


def test_deterministic_given_seed():
    for _ in range(2):
        results = []
        for _run in range(2):
            agent = MCTSAgent(iterations=60, seed=9)
            s = battle(["strike", "bash", "defend", "poison_blade"])
            s.enemy.intent = ("attack", 6)
            results.append(agent.choose_action(s))
        assert results[0] == results[1]


def test_actions_always_legal_and_battle_terminates():
    for enemy_id in ["giant_rat", "poison_spider", "stone_golem"]:
        agent = MCTSAgent(iterations=60, seed=3)
        p = PlayerState(hp=50, max_hp=50, deck=list(STARTING_DECK))
        s = GameState(p, make_enemy(enemy_id), seed=17)
        start_battle(s, enemy_ai)
        for _ in range(300):
            if s.battle_over:
                break
            a = agent.choose_action(s)
            assert a in legal_actions(s)
            apply_action(s, a, enemy_ai)
        assert s.battle_over, f"{enemy_id}:300 步沒打完"


def test_wins_reliably_vs_giant_rat():
    from sim.runner import run_battle
    wins = sum(run_battle(MCTSAgent(iterations=80, seed=i), "giant_rat",
                          seed=i)["win"] for i in range(10))
    assert wins >= 8, f"MCTS 對巨鼠只贏 {wins}/10"
