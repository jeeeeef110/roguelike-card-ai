"""tests/test_cards.py — 卡牌資料與 v2.2 §3.3 定稿(+v2.3 平衡修正)的一致性:
1. 26 張、id 唯一、註冊表 key 與 card_id 一致
2. 起始牌組組成、稀有度分佈(起始 3 / 稀有 7 / 普通 16)照定稿
3. effects 結構合法(engine 可解讀的 (opcode, *int 參數) 序列)
4. kind 分類規則:會造成傷害的卡 = attack,其餘 = skill
"""
import pytest

from core.cards import CARDS, RARITY_WEIGHTS, STARTING_DECK, get_card

# 所有會對敵造成傷害的 opcode(與 core/cards.py 檔頭指令集同步維護)
DAMAGE_OPS = {
    "damage",
    "damage_bonus_vs_vulnerable",
    "damage_per_vulnerable",
    "damage_per_attack_played",
    "damage_equal_block",
    "damage_shatter",
    "detonate_poison",
}


def test_exactly_26_cards_with_consistent_ids():
    assert len(CARDS) == 26
    for card_id, card in CARDS.items():
        assert card.card_id == card_id


def test_starting_deck_composition():
    assert len(STARTING_DECK) == 10
    assert STARTING_DECK.count("strike") == 5
    assert STARTING_DECK.count("defend") == 4
    assert STARTING_DECK.count("rampage") == 1
    assert all(cid in CARDS for cid in STARTING_DECK)


def test_rarity_distribution_matches_spec():
    by_rarity: dict[str, set[str]] = {"starter": set(), "common": set(), "rare": set()}
    for card in CARDS.values():
        by_rarity[card.rarity].add(card.card_id)
    assert by_rarity["starter"] == {"strike", "defend", "rampage"}
    # §3.5:build 定義卡(反甲擊、兵法、引爆、亂舞、回收、制裁)全為稀有;
    # v2.3 新增破限(攻擊上限 payoff)亦為稀有
    assert by_rarity["rare"] == {
        "armor_strike", "tactics", "detonate", "flurry", "salvage", "judgment",
        "limit_break",
    }
    assert len(by_rarity["common"]) == 16
    assert set(RARITY_WEIGHTS) == {"common", "rare"}


def test_effects_structure_is_engine_readable():
    for card in CARDS.values():
        assert card.kind in ("attack", "skill")
        assert 0 <= card.cost <= 2
        assert isinstance(card.effects, tuple) and card.effects
        for effect in card.effects:
            assert isinstance(effect, tuple) and effect
            opcode, *params = effect
            assert isinstance(opcode, str)
            assert all(isinstance(p, int) for p in params)


def test_kind_rule_damage_means_attack():
    for card in CARDS.values():
        deals_damage = any(e[0] in DAMAGE_OPS for e in card.effects)
        expected = "attack" if deals_damage else "skill"
        assert card.kind == expected, f"{card.card_id} 的 kind 違反分類規則"


def test_spot_check_key_cards_against_spec():
    # 表格逐格抽查:基礎、多段攻擊、延遲效果、轉換效果
    assert get_card("strike").effects == (("damage", 6),)
    assert get_card("bash") == CARDS["bash"]
    assert get_card("bash").effects == (("damage", 8), ("apply_vulnerable", 2))
    assert get_card("double_strike").effects.count(("damage", 3)) == 2
    assert get_card("flurry").effects.count(("damage", 2)) == 4
    assert get_card("momentum").effects == (("next_turn_energy", 2),)
    assert get_card("overdraw").effects == (("damage", 12), ("next_turn_energy", -1))
    assert get_card("detonate").effects == (("detonate_poison", 2),)
    assert get_card("rend").cost == 0
    assert get_card("rend").effects == (("damage_per_attack_played", 2, 2),)
    assert get_card("entrench").effects == (("block", 8), ("retain_block",))


def test_get_card_rejects_unknown_id():
    with pytest.raises(KeyError):
        get_card("not_a_card")
