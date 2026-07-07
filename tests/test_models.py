"""tests/test_models.py — 資料結構的三件生死攸關的事:
1. clone 完全獨立(改複本不動原本)——MCTS 正確性的前提
2. RNG 同 seed 同結果——重播與模擬可重現性的前提
3. clone 速度——MCTS 效能的前提(基準:每秒 10 萬次以上)
"""
import time

from core.models import Card, EnemyState, GameState, PlayerState


def make_state() -> GameState:
    deck = ["strike"] * 5 + ["defend"] * 4 + ["rampage"]
    p = PlayerState(hp=70, max_hp=70, deck=deck)
    e = EnemyState("giant_rat", hp=28)
    e.pattern = {"charging": False}
    return GameState(p, e, seed=42)


def test_clone_player_independence():
    s = make_state()
    c = s.clone()
    c.player.hp -= 10
    c.player.hand.append("strike")
    c.player.draw_pile.pop()
    c.player.strength += 3
    assert s.player.hp == 70
    assert s.player.hand == []
    assert len(s.player.draw_pile) == 10
    assert s.player.strength == 0


def test_clone_enemy_independence():
    s = make_state()
    c = s.clone()
    c.enemy.hp -= 5
    c.enemy.pattern["charging"] = True
    c.enemy.intent = ("attack", 6)
    assert s.enemy.hp == 28
    assert s.enemy.pattern["charging"] is False
    assert s.enemy.intent == ("none",)


def test_rng_replay_same_seed():
    a = GameState(PlayerState(70, 70, ["x"] * 20), EnemyState("e", 10), seed=7)
    b = GameState(PlayerState(70, 70, ["x"] * 20), EnemyState("e", 10), seed=7)
    seq_a = [a.rng.randint(0, 999) for _ in range(50)]
    seq_b = [b.rng.randint(0, 999) for _ in range(50)]
    assert seq_a == seq_b


def test_rng_replay_mode_continues_identically():
    s = make_state()
    s.rng.random()  # 先前進一步,確認複製的是「當下」狀態
    c = s.clone(rng="replay")
    assert [s.rng.randint(0, 999) for _ in range(20)] == [
        c.rng.randint(0, 999) for _ in range(20)
    ]


def test_rng_share_mode_shares_object():
    s = make_state()
    c = s.clone()  # 預設 share
    assert c.rng is s.rng


def test_rng_seed_mode_is_deterministic():
    s = make_state()
    a = s.clone(rng=123)
    b = s.clone(rng=123)
    assert [a.rng.randint(0, 999) for _ in range(20)] == [
        b.rng.randint(0, 999) for _ in range(20)
    ]
    assert a.rng is not s.rng


def test_card_is_immutable_shared_data():
    card = Card("strike", "打擊", 1, "attack", "starter", (("damage", 6),))
    try:
        card.cost = 2  # type: ignore[misc]
        assert False, "Card 必須不可變"
    except AttributeError:
        pass


def test_clone_benchmark():
    s = make_state()
    s.player.hand = ["strike"] * 5
    s.player.discard_pile = ["defend"] * 8
    n = 20_000
    t0 = time.perf_counter()
    for _ in range(n):
        s.clone()
    per_sec = n / (time.perf_counter() - t0)
    print(f"\nclone 速度:{per_sec:,.0f} 次/秒")
    assert per_sec > 100_000, f"clone 過慢({per_sec:,.0f}/秒),MCTS 會撐不住"
