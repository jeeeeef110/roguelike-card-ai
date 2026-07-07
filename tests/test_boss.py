"""tests/test_boss.py — 腐化騎士:狂暴計時、階段切換、多段攻擊結算。"""
from core.cards import STARTING_DECK
from core.enemies import (
    BOSS_ENRAGE_EVERY, BOSS_P1_ATTACK, BOSS_P2_ATTACK, enemy_ai, make_enemy,
)
from core.engine import end_turn, start_battle
from core.models import GameState, PlayerState


def boss_battle(seed: int = 42) -> GameState:
    p = PlayerState(hp=50, max_hp=50, deck=list(STARTING_DECK))
    s = GameState(p, make_enemy("corrupted_knight"), seed=seed)
    start_battle(s, enemy_ai)
    return s


def test_boss_stats():
    b = make_enemy("corrupted_knight")
    assert b.max_hp == 90
    assert b.block_persists is False


def test_phase1_heavy_blow_phase2_triple():
    s = boss_battle()
    assert s.enemy.intent == ("attack", BOSS_P1_ATTACK)   # 一階段:單次重擊
    s.enemy.hp = 44                           # 半血以下(90 的 50% = 45)
    end_turn(s, enemy_ai)
    assert s.enemy.intent == ("attack", *BOSS_P2_ATTACK)  # 二階段:3 連擊


def test_enrage_cadence():
    s = boss_battle()
    assert s.enemy.strength == 0              # 回合 1:未狂暴
    for turn in range(2, 2 * BOSS_ENRAGE_EVERY + 2):
        end_turn(s, enemy_ai)
        assert s.enemy.strength == turn // BOSS_ENRAGE_EVERY, f"回合 {turn}"


def test_enraged_triple_attack_scales_three_times():
    """狂暴的力量在 3 連擊上吃三次加成——二階段隨時間急遽變痛。"""
    s = boss_battle()
    s.enemy.hp = 40
    s.enemy.strength = 3
    s.enemy.intent = ("attack", 5, 3)
    end_turn(s, enemy_ai)
    # (5+3)×3 = 24;回合 2 宣告時狂暴再 +1(不影響已結算的這刀)
    assert s.player.hp == 50 - 24


def test_full_boss_battle_reaches_ending():
    from agents.rule_based import RuleBasedAgent
    from sim.runner import run_battle
    r = run_battle(RuleBasedAgent(), "corrupted_knight", seed=7)
    assert r["turns"] <= 30                   # 狂暴計時保證不會無限拖
