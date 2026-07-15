"""tests/test_variety.py — 變化性擴充:新敵人謎題、菁英、進階、深度分池"""
from random import Random

from core.enemies import enemy_ai, make_enemy
from core.engine import apply_action, legal_actions, start_battle
from core.map_gen import ELITE_MIN_LAYER, generate_map, validate_map
from core.models import GameState, PlayerState
from core.run import (ASCENSION_HP_STEP, ELITE_HP_MULT, RunState, enter_node,
                      next_choices, spawn_enemy, take_reward)
from core.cards import get_card


def _battle(deck, enemy_id, seed=1):
    p = PlayerState(hp=50, max_hp=50, deck=deck)
    s = GameState(p, make_enemy(enemy_id), seed=seed)
    start_battle(s, enemy_ai)
    return s


# ---------------------------------------------------------------- 吸血蝠


def test_blood_bat_lifesteal_heals_actual_damage():
    s = _battle(["strike"] * 10, "blood_bat", seed=3)
    s.enemy.hp = 20
    s.enemy.intent = ("attack_lifesteal", 7)
    s.player.block = 0
    hp_p, hp_e = s.player.hp, s.enemy.hp
    from core.engine import _execute_intent
    _execute_intent(s)
    dealt = hp_p - s.player.hp
    assert dealt > 0 and s.enemy.hp == hp_e + dealt


def test_blood_bat_full_block_heals_nothing():
    s = _battle(["strike"] * 10, "blood_bat", seed=3)
    s.enemy.hp = 20
    s.enemy.intent = ("attack_lifesteal", 7)
    s.player.block = 99
    hp_e = s.enemy.hp
    from core.engine import _execute_intent
    _execute_intent(s)
    assert s.enemy.hp == hp_e and s.player.hp == 50  # 全擋=吸不到


def test_blood_bat_lifesteal_caps_at_max_hp():
    s = _battle(["strike"] * 10, "blood_bat", seed=3)
    s.enemy.intent = ("attack_lifesteal", 7)
    s.player.block = 0
    from core.engine import _execute_intent
    _execute_intent(s)
    assert s.enemy.hp <= s.enemy.max_hp


# ---------------------------------------------------------------- 狂戰士


def test_berserker_gains_strength_per_hit():
    s = _battle(["double_strike"] * 10, "berserker", seed=2)
    from core.engine import _hit_enemy
    _hit_enemy(s, 3)
    _hit_enemy(s, 3)
    _hit_enemy(s, 3)
    str_before = s.enemy.strength
    intent = enemy_ai(s)  # 宣告時吃掉 hits_taken
    assert s.enemy.strength == str_before + 3
    assert intent[0] in ("attack", "block")
    assert s.enemy.pattern.get("hits_taken", 0) == 0  # 已歸零


def test_berserker_poison_tick_does_not_enrage():
    s = _battle(["strike"] * 10, "berserker", seed=2)
    s.enemy.poison = 5
    s.enemy.pattern.pop("hits_taken", None)
    str_before = s.enemy.strength
    # 走一次完整回合流程(含毒 tick),期間玩家不出牌
    apply_action(s, ("end_turn",), enemy_ai)
    enemy_ai(s)
    assert s.enemy.strength <= str_before + 1  # 至多循環自然增長,毒不餵力量


# ---------------------------------------------------------------- 菁英與進階


def test_spawn_enemy_elite_and_ascension_scaling():
    run0 = RunState(seed=1)
    run2 = RunState(seed=1, ascension=2)
    m = run0.game_map
    battle_node = m.layers[0][0]
    base = spawn_enemy(run0, battle_node)
    asc = spawn_enemy(run2, battle_node)
    assert asc.max_hp == int(base.max_hp * (1 + ASCENSION_HP_STEP * 2))
    # 手工造一個菁英節點驗倍率
    from core.map_gen import MapNode
    elite_node = MapNode(5, 0, "elite", "berserker")
    e = spawn_enemy(run0, elite_node)
    assert e.max_hp == int(make_enemy("berserker").max_hp * ELITE_HP_MULT)
    assert e.strength == 1


def test_elite_rewards_are_all_rare():
    run = RunState(seed=11)
    # 直接測 draw_rewards 的 rare_only 分支
    from core.run import draw_rewards
    for _ in range(10):
        assert all(get_card(c).rarity == "rare"
                   for c in draw_rewards(run, rare_only=True))


def test_full_run_with_elites_smoke():
    """含菁英與新敵人的完整冒險冒煙(12 層 + 進階 1)。"""
    deep = 0
    for seed in range(20):
        run = RunState(seed=seed, ascension=1, n_layers=12)
        from tests.test_run import _agent_battle
        while not run.over:
            node = next_choices(run)[0]
            out = enter_node(run, node, _agent_battle)
            if "rewards" in out:
                take_reward(run, out["rewards"], out["rewards"][0])
            if "rest_options" in out:
                from core.run import rest_heal
                rest_heal(run)
            assert 0 <= run.hp <= run.max_hp
        if len(run.floor_log) >= 6:
            deep += 1
    assert deep >= 3


# ---------------------------------------------------------------- 地圖變化


def test_map_layers_param_and_validation():
    for n in (10, 12, 15):
        for seed in range(100):
            m = generate_map(seed, n_layers=n)
            assert len(m.layers) == n
            assert not validate_map(m), validate_map(m)


def test_depth_pools_early_layers_have_no_heavy_enemies():
    heavy = {"stone_golem", "blood_bat", "berserker"}
    for seed in range(200):
        m = generate_map(seed)
        for row in m.layers[:4]:
            for n in row:
                if n.node_type == "battle":
                    assert n.enemy_id not in heavy


def test_elites_exist_and_respect_min_layer():
    seen = 0
    for seed in range(200):
        for row in generate_map(seed).layers:
            for n in row:
                if n.node_type == "elite":
                    seen += 1
                    assert n.layer >= ELITE_MIN_LAYER
    assert seen > 20  # 菁英確實會出現
