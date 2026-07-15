"""tests/test_potions.py — 藥水:戰鬥中使用、免費動作、掉落/商店經濟"""
from random import Random

import pytest
from core.enemies import enemy_ai, make_enemy
from core.engine import apply_action, legal_actions, start_battle, use_potion
from core.models import GameState, PlayerState
from core.potions import MAX_POTIONS, POTIONS, get_potion
from core.run import (RunState, enter_node, next_choices, shop_buy_potion,
                      take_potion, take_reward)


def _battle(potions, seed=1):
    p = PlayerState(hp=50, max_hp=50, deck=["strike"] * 10)
    p.potions = list(potions)
    s = GameState(p, make_enemy("giant_rat"), seed=seed)
    start_battle(s, enemy_ai)
    return s


def test_potion_appears_in_legal_actions_and_dedupes():
    s = _battle(["fire_flask", "fire_flask", "healing_vial"])
    acts = legal_actions(s)
    assert acts.count(("potion", "fire_flask")) == 1
    assert ("potion", "healing_vial") in acts


def test_potion_is_free_action():
    s = _battle(["strength_brew"])
    e_before = s.player.energy
    apply_action(s, ("potion", "strength_brew"), enemy_ai)
    assert s.player.energy == e_before          # 不耗能量
    assert s.player.strength == 2
    assert s.player.potions == []               # 用掉即消失
    assert s.player.attacks_played == 0         # 不計攻擊卡上限


def test_fire_flask_damages_enemy():
    s = _battle(["fire_flask"])
    hp = s.enemy.hp
    use_potion(s, "fire_flask")
    assert s.enemy.hp <= hp - 10                # ≥10(力量會加成)


def test_healing_vial_caps_at_max_hp():
    s = _battle(["healing_vial"])
    s.player.hp = 45
    use_potion(s, "healing_vial")
    assert s.player.hp == 50


def test_use_unowned_potion_raises():
    s = _battle([])
    with pytest.raises(ValueError):
        use_potion(s, "fire_flask")


def test_potion_survives_clone():
    s = _battle(["venom_vial"])
    c = s.clone()
    c.player.potions.pop()
    assert s.player.potions == ["venom_vial"]


def test_take_potion_respects_cap():
    run = RunState(seed=1)
    for pid in list(POTIONS)[:MAX_POTIONS]:
        assert take_potion(run, pid)
    assert not take_potion(run, "fire_flask")
    assert len(run.potions) == MAX_POTIONS


def test_shop_buy_potion_economy():
    run = RunState(seed=2)
    run.gold = 30
    shop_buy_potion(run, "fire_flask")
    assert run.gold == 5 and run.potions == ["fire_flask"]
    with pytest.raises(ValueError):
        shop_buy_potion(run, "fire_flask")      # 金幣不足


def test_potion_drop_rate_roughly_35_percent():
    drops = 0
    for seed in range(300):
        run = RunState(seed=seed)
        out = enter_node(run, next_choices(run)[0],
                         lambda r, n: (True, r.hp))
        drops += "potion_drop" in out
    assert 0.25 < drops / 300 < 0.45


def test_full_run_smoke_with_potions():
    """整輪冒煙:撿藥水、休息選回血,流程不炸。"""
    from tests.test_run import _agent_battle
    for seed in range(10):
        run = RunState(seed=seed)
        while not run.over:
            node = next_choices(run)[0]
            out = enter_node(run, node, _agent_battle)
            if "rewards" in out:
                take_reward(run, out["rewards"], out["rewards"][0])
            if "potion_drop" in out:
                take_potion(run, out["potion_drop"])
            if "rest_options" in out:
                from core.run import rest_heal
                rest_heal(run)
            assert 0 <= run.hp <= run.max_hp
