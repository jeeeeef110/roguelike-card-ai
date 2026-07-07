"""tests/test_enemies.py — 三隻敵人:規格數值、狀態機行為、被動特性、機率分佈。"""
import pytest

from core.cards import STARTING_DECK
from core.enemies import enemy_ai, make_enemy
from core.engine import end_turn, play_card, start_battle
from core.models import GameState, PlayerState


def battle_vs(enemy_id: str, seed: int = 42) -> GameState:
    p = PlayerState(hp=70, max_hp=70, deck=list(STARTING_DECK))
    s = GameState(p, make_enemy(enemy_id), seed=seed)
    start_battle(s, enemy_ai)
    return s


# ---------------------------------------------------------------- 規格數值


def test_stats_match_spec():
    rat, spider, golem = map(make_enemy, ["giant_rat", "poison_spider", "stone_golem"])
    assert (rat.hp, rat.block_persists) == (28, False)
    assert (spider.hp, spider.block_persists) == (22, False)
    assert (golem.hp, golem.block_persists) == (40, True)
    with pytest.raises(KeyError):
        make_enemy("slime")


# ---------------------------------------------------------------- 巨鼠


def _charging_rat(hp_at_charge: int, hp_now: int) -> GameState:
    s = battle_vs("giant_rat")
    s.enemy.pattern = {"charging": True, "hp_at_charge": hp_at_charge}
    s.enemy.hp = hp_now
    return s


def test_rat_charge_leads_to_attack_12():
    s = _charging_rat(hp_at_charge=28, hp_now=28)  # 蓄力期間沒受傷
    assert enemy_ai(s) == ("attack", 12)


def test_rat_interrupted_by_8_damage_falls_back_to_attack_6():
    s = _charging_rat(hp_at_charge=28, hp_now=20)  # 剛好 8 傷 → 打斷
    assert enemy_ai(s) == ("attack", 6)
    s = _charging_rat(hp_at_charge=28, hp_now=21)  # 7 傷 → 不打斷
    assert enemy_ai(s) == ("attack", 12)


def test_rat_intent_distribution_60_40():
    hits = {"attack": 0, "charge": 0}
    s = battle_vs("giant_rat", seed=1)
    for _ in range(2000):
        s.enemy.pattern = {}  # 每次都從未蓄力狀態抽
        hits[enemy_ai(s)[0]] += 1
    assert 0.55 < hits["attack"] / 2000 < 0.65


def test_rat_charge_then_hit_full_flow_through_engine():
    """整合:透過 engine 打一次完整的蓄力→轟 12。"""
    s = battle_vs("giant_rat", seed=0)
    s.enemy.intent = ("charge",)
    s.enemy.pattern = {"charging": True, "hp_at_charge": s.enemy.hp}
    hp = s.player.hp
    end_turn(s, enemy_ai)              # 蓄力執行=空過;新意圖=攻 12
    assert s.enemy.intent == ("attack", 12)
    end_turn(s, enemy_ai)
    assert s.player.hp == hp - 12


# ---------------------------------------------------------------- 毒蛛


def test_spider_webs_every_third_turn():
    s = battle_vs("poison_spider")
    for turn, must_web in [(3, True), (4, False), (6, True)]:
        s.turn = turn
        intent = enemy_ai(s)
        assert (intent == ("web",)) is must_web


def test_spider_intent_distribution_50_30_20():
    s = battle_vs("poison_spider", seed=2)
    s.turn = 1
    hits = {"attack_poison": 0, "poison": 0, "block": 0}
    for _ in range(2000):
        hits[enemy_ai(s)[0]] += 1
    assert 0.45 < hits["attack_poison"] / 2000 < 0.55
    assert 0.25 < hits["poison"] / 2000 < 0.35
    assert 0.15 < hits["block"] / 2000 < 0.25


def test_spider_web_taxes_player_attacks_via_engine():
    s = battle_vs("poison_spider")
    s.enemy.intent = ("web",)
    s.turn = 1                       # 避開回合 3 再織一次干擾斷言
    end_turn(s, enemy_ai)
    from core.engine import card_cost
    assert card_cost(s, "strike") == 2


# ---------------------------------------------------------------- 石像兵


def test_golem_cycle_and_passive_armor():
    s = battle_vs("stone_golem")
    # start_battle 已宣告第 1 手:甲 8 循環開頭,被動先 +3
    assert s.enemy.intent == ("block", 8)
    assert s.enemy.block == 3
    end_turn(s, enemy_ai)            # 執行甲 8 → 宣告攻 9,被動再 +3
    assert s.enemy.intent == ("attack", 9)
    assert s.enemy.block == 3 + 8 + 3
    end_turn(s, enemy_ai)
    assert s.enemy.intent == ("attack", 9)
    end_turn(s, enemy_ai)            # 循環回到甲 8
    assert s.enemy.intent == ("block", 8)


def test_golem_block_never_resets_and_poison_bypasses():
    s = battle_vs("stone_golem")
    end_turn(s, enemy_ai)
    assert s.enemy.block > 0         # 一般敵人這裡已歸零
    hp = s.enemy.hp
    s.enemy.poison = 5
    end_turn(s, enemy_ai)
    assert s.enemy.hp == hp - 5      # 毒無視護甲:破解石像兵的路線成立


# ---------------------------------------------------------------- 整場冒煙


@pytest.mark.parametrize("enemy_id", ["giant_rat", "poison_spider", "stone_golem"])
def test_full_battle_reaches_an_ending(enemy_id):
    """簡單策略(能出攻擊就出)+ 真敵人,100 回合內必分勝負。"""
    s = battle_vs(enemy_id, seed=9)
    for _ in range(100):
        if s.battle_over:
            break
        from core.engine import legal_actions, apply_action
        plays = [a for a in legal_actions(s) if a[0] == "play"]
        apply_action(s, plays[0] if plays else ("end_turn",), enemy_ai)
    assert s.battle_over
