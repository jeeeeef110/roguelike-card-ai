"""tests/test_meta.py — 局外養成:Boss 三選一解鎖、存檔、卡池過濾"""
from pathlib import Path
from random import Random

import pytest
from core.cards import get_card
from core.meta import STARTING_RARE_COUNT, MetaState, _all_rares
from core.run import RunState, draw_rewards


def test_new_meta_starts_with_three_rares():
    m = MetaState(meta_seed=1)
    assert len(m.unlocked_rares) == STARTING_RARE_COUNT
    assert all(get_card(c).rarity == "rare" for c in m.unlocked_rares)


def test_different_meta_seed_different_start():
    starts = {tuple(MetaState(meta_seed=s).unlocked_rares) for s in range(20)}
    assert len(starts) >= 3


def test_boss_unlock_cycle():
    m = MetaState(meta_seed=1)
    rng = Random(0)
    choices = m.boss_unlock_choices(rng)
    assert 1 <= len(choices) <= 3
    assert all(c in m.locked_rares() for c in choices)
    pick = choices[0]
    m.unlock_rare(pick)
    assert pick in m.unlocked_rares
    with pytest.raises(ValueError):
        m.unlock_rare(pick)  # 不能重複解鎖


def test_all_unlocked_returns_empty_choices():
    m = MetaState(meta_seed=1)
    for c in list(m.locked_rares()):
        m.unlock_rare(c)
    assert m.boss_unlock_choices(Random(0)) == []


def test_settle_run_rewards_defeat_too():
    m = MetaState(meta_seed=1)
    g_lose = m.settle_run(floors=5, elites=1, boss_killed=False, ascension=0)
    assert g_lose == 5 * 2 + 5 and m.shards == g_lose  # 雖敗猶得
    g_win = m.settle_run(floors=10, elites=2, boss_killed=True, ascension=0)
    assert g_win == 20 + 10 + 20
    assert m.runs == 2 and m.wins == 1 and m.ascension_best == 1


def test_save_load_roundtrip(tmp_path=None):
    path = Path("/tmp/meta_test.json")
    m = MetaState(meta_seed=7)
    m.settle_run(10, 1, True, 0)
    m.save(path)
    loaded = MetaState.load(path)
    for k in MetaState.__slots__:
        assert getattr(loaded, k) == getattr(m, k)


def test_load_rejects_future_version():
    path = Path("/tmp/meta_bad.json")
    m = MetaState(meta_seed=1)
    m.save(path)
    import json
    data = json.loads(path.read_text(encoding="utf-8"))
    data["version"] = 999
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        MetaState.load(path)


def test_run_reward_pool_respects_unlocks():
    m = MetaState(meta_seed=1)
    locked = set(m.locked_rares())
    run = RunState(seed=3, unlocked_rares=list(m.unlocked_rares))
    for _ in range(60):
        for c in draw_rewards(run):
            assert c not in locked
        for c in draw_rewards(run, rare_only=True):
            assert get_card(c).rarity == "rare" and c not in locked


def test_rare_only_with_tiny_pool_does_not_hang():
    run = RunState(seed=3, unlocked_rares=[_all_rares()[0]])
    picks = draw_rewards(run, rare_only=True)
    assert picks == [_all_rares()[0]]  # 池內只有一種:發一張,不卡死


def test_progression_loop_smoke():
    """養成主循環冒煙:連打多輪(自動勝),Boss 解鎖至全開。"""
    m = MetaState(meta_seed=2)
    rng = Random(1)
    for run_no in range(10):
        run = RunState(seed=run_no, unlocked_rares=list(m.unlocked_rares))
        # 模擬:直接視為通關
        m.settle_run(floors=10, elites=1, boss_killed=True,
                     ascension=min(run_no, m.ascension_best))
        choices = m.boss_unlock_choices(rng)
        if choices:
            m.unlock_rare(choices[0])
    assert m.locked_rares() == []          # 4 次擊殺後全解鎖
    assert m.shards > 0 and m.ascension_best >= 1
