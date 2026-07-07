"""tests/test_engine.py — 規則引擎:每個測試 = 一條規則。

分四組:傷害管線 / 回合流程與資源 / 特殊卡結算 / 代理接口與勝負。
"""
import pytest

from core.cards import STARTING_DECK
from core.engine import (
    apply_action, card_cost, end_turn, legal_actions, play_card, start_battle,
)
from core.models import EnemyState, GameState, PlayerState


def battle(deck: list[str] | None = None, enemy_hp: int = 100,
           seed: int = 42) -> GameState:
    p = PlayerState(hp=70, max_hp=70, deck=deck or list(STARTING_DECK))
    s = GameState(p, EnemyState("dummy", hp=enemy_hp), seed=seed)
    start_battle(s)
    return s


def force_hand(s: GameState, cards: list[str]) -> None:
    """測試用:直接指定手牌,原手牌移去棄牌堆。"""
    s.player.discard_pile.extend(s.player.hand)
    s.player.hand = list(cards)


# ---------------------------------------------------------------- 傷害管線


def test_strike_deals_6():
    s = battle()
    force_hand(s, ["strike"])
    play_card(s, "strike")
    assert s.enemy.hp == 94


def test_strength_adds_per_hit():
    s = battle()
    force_hand(s, ["empower", "double_strike"])
    play_card(s, "empower")        # 力量 +2
    play_card(s, "double_strike")  # (3+2) ×2 次
    assert s.enemy.hp == 100 - 10


def test_vulnerable_multiplies_1_5_floor():
    s = battle()
    force_hand(s, ["bash", "strike"])
    play_card(s, "bash")    # 8 傷 + 易傷 2
    play_card(s, "strike")  # 6 ×1.5 = 9
    assert s.enemy.hp == 100 - 8 - 9


def test_vulnerable_floor_rounding():
    s = battle()
    force_hand(s, ["bash", "poison_blade"])
    play_card(s, "bash")          # 易傷 2
    play_card(s, "poison_blade")  # 3 ×1.5 = 4.5 → 4
    assert s.enemy.hp == 100 - 8 - 4


def test_enemy_block_absorbs_then_hp():
    s = battle()
    s.enemy.block = 4
    force_hand(s, ["strike"])
    play_card(s, "strike")  # 6 傷:4 進護甲、2 進 HP
    assert s.enemy.block == 0
    assert s.enemy.hp == 98


def test_poison_ticks_at_turn_start_ignores_block_and_vulnerable():
    s = battle()
    force_hand(s, ["deadly_poison", "bash"])
    play_card(s, "deadly_poison")  # 中毒 4
    play_card(s, "bash")           # 易傷 2(毒不吃易傷)
    s.enemy.block = 99             # 毒無視護甲
    hp = s.enemy.hp
    end_turn(s)
    assert s.enemy.hp == hp - 4    # 扣層數等量,沒被 ×1.5
    assert s.enemy.poison == 3     # 層數 -1


def test_player_poison_also_ticks():
    s = battle()
    s.player.poison = 3
    end_turn(s)
    assert s.player.hp == 70 - 3
    assert s.player.poison == 2


# ---------------------------------------------------------------- 回合流程與資源


def test_battle_starts_with_5_cards_3_energy():
    s = battle()
    assert len(s.player.hand) == 5
    assert s.player.energy == 3
    assert s.turn == 1


def test_shuffle_is_seed_deterministic():
    a, b = battle(seed=7), battle(seed=7)
    assert a.player.hand == b.player.hand


def test_end_turn_discards_hand_draws_new_5():
    s = battle()
    end_turn(s)
    assert len(s.player.hand) == 5
    assert s.turn == 2


def test_reshuffle_discard_into_draw_pile():
    s = battle()  # 牌庫 10 張:回合 1 抽 5、回合 2 抽 5、回合 3 需洗回
    end_turn(s)
    end_turn(s)
    assert len(s.player.hand) == 5
    assert len(s.player.draw_pile) + len(s.player.discard_pile) == 5


def test_energy_gate_blocks_unaffordable_card():
    s = battle()
    force_hand(s, ["iron_wall", "iron_wall"])  # 2 費 ×2,能量 3
    play_card(s, "iron_wall")
    with pytest.raises(ValueError):
        play_card(s, "iron_wall")


def test_momentum_gives_5_energy_next_turn():
    s = battle()
    force_hand(s, ["momentum"])
    play_card(s, "momentum")
    end_turn(s)
    assert s.player.energy == 5


def test_overdraw_costs_1_energy_next_turn():
    s = battle()
    force_hand(s, ["overdraw"])
    play_card(s, "overdraw")
    assert s.enemy.hp == 88
    end_turn(s)
    assert s.player.energy == 2


def test_block_resets_unless_entrench():
    s = battle()
    force_hand(s, ["defend"])
    play_card(s, "defend")
    end_turn(s)
    assert s.player.block == 0
    force_hand(s, ["entrench"])
    play_card(s, "entrench")
    end_turn(s)
    assert s.player.block == 8      # 堅守:跨回合保留
    end_turn(s)
    assert s.player.block == 0      # 只保留一回合


def test_web_raises_attack_cost_next_turn_only():
    s = battle()
    s.enemy.intent = ("web",)
    end_turn(s)
    assert card_cost(s, "strike") == 2   # 織網生效:攻擊 +1 費
    assert card_cost(s, "defend") == 1   # 技能不受影響
    s.enemy.intent = ("none",)
    end_turn(s)
    assert card_cost(s, "strike") == 1   # 只影響一回合


def test_enemy_attack_hits_through_pipeline():
    s = battle()
    force_hand(s, ["defend"])
    play_card(s, "defend")               # 護甲 5
    s.enemy.intent = ("attack", 8)
    end_turn(s)
    assert s.player.hp == 70 - 3         # 8 - 5

def test_enemy_multi_attack_and_strength():
    s = battle()
    s.enemy.strength = 1
    s.enemy.intent = ("attack", 5, 3)    # Boss 二階段型:(5+1) ×3
    end_turn(s)
    assert s.player.hp == 70 - 18


def test_vulnerable_counts_down_each_turn():
    s = battle()
    force_hand(s, ["bash"])
    play_card(s, "bash")
    assert s.enemy.vulnerable == 2
    end_turn(s)
    assert s.enemy.vulnerable == 1
    end_turn(s)
    assert s.enemy.vulnerable == 0


# ---------------------------------------------------------------- 特殊卡結算


def test_follow_slash_bonus_only_vs_vulnerable():
    s = battle()
    s.player.energy = 4            # 1 + 2 + 1 費
    force_hand(s, ["follow_slash", "bash", "follow_slash"])
    play_card(s, "follow_slash")   # 無易傷:4
    play_card(s, "bash")           # 8 + 易傷 2
    play_card(s, "follow_slash")   # (4+4) ×1.5 = 12
    assert s.enemy.hp == 100 - 4 - 8 - 12


def test_judgment_scales_with_vulnerable_stacks():
    s = battle(deck=["judgment"] * 10)
    s.enemy.vulnerable = 3
    force_hand(s, ["judgment"])
    play_card(s, "judgment")       # (6 + 4×3) ×1.5 = 27
    assert s.enemy.hp == 100 - 27


def test_rend_counts_attacks_played_before_it():
    s = battle()
    s.player.energy = 5
    force_hand(s, ["strike", "strike", "rend"])
    play_card(s, "strike")
    play_card(s, "strike")
    play_card(s, "rend")           # 2 + 2×2 = 6,不算自己
    assert s.enemy.hp == 100 - 6 - 6 - 6


def test_armor_strike_equals_current_block():
    s = battle()
    force_hand(s, ["iron_wall", "armor_strike"])
    play_card(s, "iron_wall")
    play_card(s, "armor_strike")   # 傷害 = 護甲 11
    assert s.enemy.hp == 100 - 11


def test_armor_break_shatters_remaining_block():
    s = battle()
    s.enemy.block = 12
    force_hand(s, ["armor_break"])
    play_card(s, "armor_break")    # 5 進護甲(剩 7)→ 移除 7 追加 7 傷
    assert s.enemy.block == 0
    assert s.enemy.hp == 100 - 7


def test_detonate_pure_conversion():
    s = battle()
    s.player.strength = 5          # 不吃力量
    s.enemy.vulnerable = 2         # 不吃易傷
    s.enemy.poison = 4
    force_hand(s, ["detonate"])
    play_card(s, "detonate")       # 4×2 = 8,清空中毒
    assert s.enemy.hp == 100 - 8
    assert s.enemy.poison == 0


def test_recharge_trades_card_for_energy():
    s = battle()
    force_hand(s, ["recharge", "strike"])
    play_card(s, "recharge", choice="strike")
    assert s.player.energy == 4
    assert s.player.hand == []
    assert "strike" in s.player.discard_pile


def test_salvage_retrieves_from_discard():
    s = battle()
    force_hand(s, ["salvage"])
    s.player.discard_pile.append("bash")
    play_card(s, "salvage", choice="bash")
    assert "bash" in s.player.hand


def test_last_stand_self_damage_can_kill():
    s = battle()
    s.player.hp = 3
    s.player.block = 99            # 自傷不經護甲
    force_hand(s, ["last_stand"])
    play_card(s, "last_stand")
    assert s.battle_over and not s.player_won


def test_bloodthirst_heals_capped_at_max():
    s = battle()
    s.player.hp = 69
    force_hand(s, ["bloodthirst"])
    play_card(s, "bloodthirst")
    assert s.player.hp == 70


# ---------------------------------------------------------------- 攻擊上限(v2.3)


def test_fourth_attack_blocked_by_limit():
    s = battle()
    force_hand(s, ["rampage", "rampage", "rampage", "strike"])
    for _ in range(3):
        play_card(s, "rampage")        # 0 費攻擊 ×3,達上限
    with pytest.raises(ValueError):
        play_card(s, "strike")


def test_limit_excludes_attacks_from_legal_actions_but_not_skills():
    s = battle()
    s.player.attacks_played = 3
    force_hand(s, ["strike", "defend"])
    acts = legal_actions(s)
    assert ("play", "strike") not in acts
    assert ("play", "defend") in acts


def test_limit_break_lifts_cap_this_turn_only():
    s = battle()
    s.player.attacks_played = 3
    force_hand(s, ["limit_break", "strike"])
    play_card(s, "limit_break")
    play_card(s, "strike")             # 第 4 張攻擊:破限後合法
    assert s.enemy.hp == 94
    end_turn(s)
    assert s.player.attack_limit_off is False  # 只管本回合


def test_limit_resets_next_turn():
    s = battle()
    s.player.attacks_played = 3
    end_turn(s)
    assert s.player.attacks_played == 0
    force_hand(s, ["strike"])
    play_card(s, "strike")             # 新回合正常出攻擊


# ---------------------------------------------------------------- 代理接口與勝負


def test_win_sets_flags_and_stops_play():
    s = battle(enemy_hp=5)
    force_hand(s, ["strike", "strike"])
    play_card(s, "strike")
    assert s.battle_over and s.player_won
    assert legal_actions(s) == []
    with pytest.raises(ValueError):
        play_card(s, "strike")


def test_legal_actions_dedupes_and_respects_energy():
    s = battle()
    force_hand(s, ["strike", "strike", "iron_wall", "iron_wall"])
    s.player.energy = 2
    acts = legal_actions(s)
    assert acts.count(("play", "strike")) == 1
    assert acts.count(("play", "iron_wall")) == 1  # 2 費付得起一張
    assert ("end_turn",) in acts


def test_legal_actions_enumerates_choices():
    s = battle()
    force_hand(s, ["recharge", "strike", "defend"])
    acts = legal_actions(s)
    assert ("play", "recharge", "strike") in acts
    assert ("play", "recharge", "defend") in acts
    assert ("play", "recharge", "recharge") not in acts  # 不能棄自己


def test_apply_action_full_random_playout():
    """冒煙測試:代理接口隨機打 200 步不炸、狀態不變壞。"""
    s = battle(enemy_hp=60, seed=3)
    s.enemy.intent = ("attack", 6)
    for _ in range(200):
        if s.battle_over:
            break
        acts = legal_actions(s)
        apply_action(s, s.rng.choice(acts),
                     enemy_ai=lambda st: ("attack", 6))
        assert s.player.hp <= 70 and s.enemy.hp <= 60
        assert len(s.player.hand) <= 10
