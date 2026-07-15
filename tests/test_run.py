"""tests/test_run.py — 冒險層:走位合法性、經濟、決定性、完整一輪整合"""
from random import Random

import pytest
from agents.rule_based import RuleBasedAgent
from core.cards import PLAYER_HP, get_card
from core.enemies import enemy_ai
from core.engine import apply_action, start_battle
from core.models import GameState, PlayerState
from core.run import (GOLD_PER_WIN, RunState, draw_rewards, enter_node,
                      next_choices, shop_buy_card, shop_remove_card,
                      spawn_enemy, take_reward)


def _agent_battle(run: RunState, node) -> tuple[bool, int]:
    """headless battle_hook:規則式代理代打。帶入冒險層當前 HP;
    敵人一律經 spawn_enemy(菁英/進階倍率才會生效)。"""
    p = PlayerState(hp=run.hp, max_hp=run.max_hp, deck=list(run.deck))
    state = GameState(p, spawn_enemy(run, node), seed=run.rng.randrange(1 << 30))
    start_battle(state, enemy_ai)
    agent = RuleBasedAgent()
    while not state.battle_over and state.turn <= 100:
        apply_action(state, agent.choose_action(state), enemy_ai)
    return (state.battle_over and state.player_won, max(0, state.player.hp))


def _auto_win(run, node):
    return (True, run.hp)  # 測流程用:必勝、不掉血


def test_first_choices_are_layer_one():
    run = RunState(seed=1)
    choices = next_choices(run)
    assert all(n.layer == 1 for n in choices) and len(choices) == 1


def test_cannot_skip_layers():
    run = RunState(seed=1)
    far_node = run.game_map.layers[4][0]
    with pytest.raises(ValueError):
        enter_node(run, far_node, _auto_win)


def test_battle_win_gives_gold_and_rewards():
    run = RunState(seed=2)
    out = enter_node(run, next_choices(run)[0], _auto_win)
    assert run.gold == GOLD_PER_WIN
    assert len(out["rewards"]) == 3 and len(set(out["rewards"])) == 3
    for cid in out["rewards"]:
        assert get_card(cid).rarity in ("common", "rare")  # 起始卡不入池


def test_take_reward_and_skip():
    run = RunState(seed=2)
    rewards = enter_node(run, next_choices(run)[0], _auto_win)["rewards"]
    n = len(run.deck)
    take_reward(run, rewards, None)          # 跳過
    assert len(run.deck) == n
    take_reward(run, rewards, rewards[0])    # 收卡
    assert len(run.deck) == n + 1
    with pytest.raises(ValueError):
        take_reward(run, rewards, "strike")  # 不在本批


def test_defeat_ends_run():
    run = RunState(seed=3)
    out = enter_node(run, next_choices(run)[0], lambda r, n: (False, 0))
    assert out == {"defeated": True} and run.over and not run.victory
    assert next_choices(run) == ()


def test_rest_two_choices_heal_and_upgrade():
    run = RunState(seed=4)
    run.hp = 10
    # 找一個可達的 rest 節點(倒數第二層全 rest)
    run.position = run.game_map.layers[-3][0]
    rest = next(n for n in next_choices(run) if n.node_type == "rest")
    out = enter_node(run, rest, _auto_win)
    assert out == {"rest_options": ("heal", "upgrade")}
    # 選項 A:回血 30%(不超過上限)
    from core.run import rest_heal, rest_upgrade
    healed = rest_heal(run)
    assert healed == min(run.max_hp - 10, int(run.max_hp * 0.30))
    assert run.hp == 10 + healed
    # 選項 B:鍛造(費用 -1);0 費卡報錯
    idx = run.deck.index("strike")
    assert rest_upgrade(run, idx) == "strike_s" and run.deck[idx] == "strike_s"
    import pytest as _pt
    with _pt.raises(ValueError):
        rest_upgrade(run, run.deck.index("rampage"))  # 0 費不能再鍛造


def test_shop_economy():
    run = RunState(seed=5)
    run.gold = 200
    n = len(run.deck)
    shop_buy_card(run, "detonate")
    assert run.gold == 135 and run.deck[-1] == "detonate"
    shop_remove_card(run, 0)
    assert run.gold == 85 and len(run.deck) == n
    run.gold = 0
    with pytest.raises(ValueError):
        shop_buy_card(run, "detonate")


def test_same_seed_same_run_offers():
    a, b = RunState(seed=9), RunState(seed=9)
    assert a.game_map == b.game_map
    enter_node(a, next_choices(a)[0], _auto_win)
    enter_node(b, next_choices(b)[0], _auto_win)
    assert draw_rewards(a) == draw_rewards(b)


def test_full_run_with_agent_smoke():
    """整合冒煙:規則式代理走完整輪(貪心選第一個節點、永遠拿第一張獎勵、
    商店/事件跳過)。30 個 seed 內至少要有幾輪能推進到後段或通關,
    且全程不拋例外、狀態一致。"""
    deep_runs = 0
    for seed in range(30):
        run = RunState(seed=seed)
        while not run.over:
            node = next_choices(run)[0]
            out = enter_node(run, node, _agent_battle)
            if "rewards" in out:
                take_reward(run, out["rewards"], out["rewards"][0])
            if "rest_options" in out:
                from core.run import rest_heal
                rest_heal(run)
            assert 0 <= run.hp <= run.max_hp
        assert run.floor_log  # 至少走了一步
        if run.victory or len(run.floor_log) >= 8:
            deep_runs += 1
    assert deep_runs >= 5, f"30 輪只有 {deep_runs} 輪推進到後段,流程可能有問題"
