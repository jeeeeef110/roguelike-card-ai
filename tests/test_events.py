"""tests/test_events.py — 三個事件:行為、合法性驗證、純函式性、實戰整合"""
from random import Random

import pytest
from core.cards import CARDS, UPGRADES, get_card
from core.events import (blacksmith_upgrade, is_poison_card,
                         old_warrior_trade, poison_merchant_commit,
                         poison_merchant_sample)

DECK = ["strike", "defend", "poison_blade", "deadly_poison", "bash", "rampage"]


def test_blacksmith_reduces_cost_and_keeps_effects():
    new = blacksmith_upgrade(DECK, 0)  # 鍛造打擊
    card = get_card(new[0])
    assert new[0] == "strike_s" and card.cost == 0
    assert card.effects == get_card("strike").effects


def test_blacksmith_rejects_zero_cost():
    with pytest.raises(ValueError):
        blacksmith_upgrade(DECK, 5)  # 狂暴 0 費


def test_blacksmith_does_not_mutate_input_or_cards():
    before = list(DECK)
    n_cards = len(CARDS)
    blacksmith_upgrade(DECK, 0)
    assert DECK == before          # 純函式:輸入不變
    assert len(CARDS) == n_cards   # 基礎卡池不變(升級卡進 UPGRADES)
    assert "strike_s" in UPGRADES


def test_poison_merchant_commit_upgrades_all_poison_cards():
    new = poison_merchant_commit(DECK, 4)  # 棄重擊(非毒攻擊卡)
    assert "bash" not in new and len(new) == len(DECK) - 1
    blade = get_card(new[new.index("poison_blade_p")])
    assert ("apply_poison", 3) in blade.effects   # 2 → 3
    dp = get_card(new[new.index("deadly_poison_p")])
    assert ("apply_poison", 5) in dp.effects      # 4 → 5


def test_poison_merchant_rejects_bad_price():
    with pytest.raises(ValueError):
        poison_merchant_commit(DECK, 2)  # 毒刃是毒卡,不能當代價
    with pytest.raises(ValueError):
        poison_merchant_commit(DECK, 1)  # 防禦不是攻擊卡


def test_poison_merchant_sample_adds_blade():
    new = poison_merchant_sample(DECK)
    assert new.count("poison_blade") == 2 and len(new) == len(DECK) + 1


def test_old_warrior_swaps_defend_for_attack():
    new, gained = old_warrior_trade(DECK, Random(0))
    assert new.count("defend") == DECK.count("defend") - 1
    assert gained in new and get_card(gained).kind == "attack"
    assert get_card(gained).rarity in ("common", "rare")  # 起始卡不入池


def test_old_warrior_requires_defend():
    with pytest.raises(ValueError):
        old_warrior_trade(["strike"], Random(0))


def test_old_warrior_deterministic_with_seed():
    a = old_warrior_trade(DECK, Random(7))
    b = old_warrior_trade(DECK, Random(7))
    assert a == b


def test_upgraded_cards_work_in_battle():
    """整合:鍛造+淬毒的牌組真的能打——升級卡經 get_card 進引擎無障礙。"""
    from core.enemies import enemy_ai, make_enemy
    from core.engine import apply_action, legal_actions, start_battle
    from core.models import GameState, PlayerState

    deck = poison_merchant_commit(blacksmith_upgrade(DECK, 0), 4) * 2
    p = PlayerState(hp=50, max_hp=50, deck=deck)
    state = GameState(p, make_enemy("giant_rat"), seed=1)
    start_battle(state, enemy_ai)
    rng = Random(2)
    for _ in range(300):
        if state.battle_over:
            break
        apply_action(state, rng.choice(legal_actions(state)), enemy_ai)
    assert state.battle_over or state.turn > 3  # 至少正常運轉多回合


def test_is_poison_card():
    assert is_poison_card("poison_blade") and is_poison_card("deadly_poison")
    assert not is_poison_card("strike") and not is_poison_card("bash")
