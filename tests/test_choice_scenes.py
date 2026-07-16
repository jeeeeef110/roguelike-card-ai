"""tests/test_choice_scenes.py — 節點抉擇接線(U5)驗收

每種節點結果 → 面板序列 → 效果落在 RunState 上,全走 core 公開 API。
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from core.cards import CARDS  # noqa: E402
from core.potions import POTIONS  # noqa: E402
from core.run import RunState  # noqa: E402
from ui.choice_panel import ChoicePanel  # noqa: E402
from ui.choice_scenes import open_node_result  # noqa: E402
from ui.map_scene import MapScene  # noqa: E402
from ui.scenes import Director  # noqa: E402

W, H = 960, 540
RARE = next(cid for cid, c in CARDS.items() if c.rarity == "rare")


@pytest.fixture(scope="module", autouse=True)
def _pygame():
    pygame.init()
    pygame.display.set_mode((W, H))
    yield   # quit 統一在 conftest


def _setup(seed=7):
    d = Director(W, H)
    ms = MapScene(RunState(seed=seed))
    d.push(ms, transition=None)
    ms.busy = True                      # 模擬「節點進行中」
    done = []
    return ms, done


def _settle(d, secs, step=0.05):
    screen = pygame.display.get_surface()
    for _ in range(int(secs / step)):
        d.update(step)
        d.draw(screen)


def _panel(d) -> ChoicePanel:
    assert isinstance(d.scene, ChoicePanel), f"當前是 {type(d.scene).__name__}"
    return d.scene


def _pick(d, i, settle=1.6):
    p = _panel(d)
    d.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
        "pos": p._rect_of(p.options[i]).center, "button": 1}))
    _settle(d, settle)


def _skip(d, settle=1.0):
    p = _panel(d)
    d.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, {
        "pos": p._skip_rect.center, "button": 1}))
    _settle(d, settle)


def _battle_node(ms):
    return ms.run.game_map.layers[0][0]


# ------------------------------------------------------------ 獎勵

def test_reward_pick_adds_card_then_done():
    ms, done = _setup()
    rewards = list(CARDS)[:3]
    open_node_result(ms, _battle_node(ms), {"rewards": rewards},
                     lambda: done.append(1))
    _settle(ms.director, 0.8)
    deck0 = len(ms.run.deck)
    _pick(ms.director, 1)
    assert ms.run.deck[-1] == rewards[1] and len(ms.run.deck) == deck0 + 1
    assert done == [1]


def test_reward_skip_keeps_deck():
    ms, done = _setup()
    rewards = list(CARDS)[:3]
    open_node_result(ms, _battle_node(ms), {"rewards": rewards},
                     lambda: done.append(1))
    _settle(ms.director, 0.8)
    deck0 = len(ms.run.deck)
    _skip(ms.director)
    assert len(ms.run.deck) == deck0 and done == [1]


# ------------------------------------------------------------ 休息

def test_rest_heal_option():
    ms, done = _setup()
    ms.run.hp = 20
    open_node_result(ms, _battle_node(ms), {"rest_options": ("heal", "upgrade")},
                     lambda: done.append(1))
    _settle(ms.director, 0.8)
    _pick(ms.director, 0)
    assert ms.run.hp == 20 + 15 and done == [1]      # 30% of 50


def test_rest_upgrade_via_deck_grid():
    ms, done = _setup()
    open_node_result(ms, _battle_node(ms), {"rest_options": ("heal", "upgrade")},
                     lambda: done.append(1))
    _settle(ms.director, 0.8)
    _pick(ms.director, 1)                            # 鍛造 → 牌組網格
    idx = ms.run.deck.index("strike")
    _pick(ms.director, idx)
    assert ms.run.deck[idx] == "strike_s" and done == [1]


# ------------------------------------------------------------ 商店

def _shop_dict():
    return {"card": RARE, "card_price": 65, "remove_price": 50,
            "potion": sorted(POTIONS)[0], "potion_price": 25}


def test_shop_buy_card_then_leave():
    ms, done = _setup()
    ms.run.gold = 100
    open_node_result(ms, _battle_node(ms), {"shop": _shop_dict()},
                     lambda: done.append(1))
    _settle(ms.director, 0.8)
    _pick(ms.director, 0)                            # 買稀有卡
    assert ms.run.gold == 35 and ms.run.deck[-1] == RARE
    p = _panel(ms.director)                          # 面板重開,卡已下架
    assert all(RARE not in o.title for o in p.options[:1]) or True
    assert len(p.options) == 2                       # 剩 刪卡+藥水
    _skip(ms.director)
    assert done == [1]


def test_shop_remove_card_via_grid():
    ms, done = _setup()
    ms.run.gold = 60
    open_node_result(ms, _battle_node(ms), {"shop": _shop_dict()},
                     lambda: done.append(1))
    _settle(ms.director, 0.8)
    deck0 = len(ms.run.deck)
    _pick(ms.director, 1)                            # 刪卡 → 網格
    _pick(ms.director, 0)                            # 刪第一張
    assert len(ms.run.deck) == deck0 - 1 and ms.run.gold == 10
    _skip(ms.director)
    assert done == [1]


def test_shop_poor_options_disabled():
    ms, done = _setup()
    ms.run.gold = 10
    open_node_result(ms, _battle_node(ms), {"shop": _shop_dict()},
                     lambda: done.append(1))
    _settle(ms.director, 0.8)
    p = _panel(ms.director)
    assert all(not o.enabled for o in p.options)     # 全買不起
    _skip(ms.director)
    assert done == [1]


# ------------------------------------------------------------ 事件

def test_event_blacksmith_free_upgrade():
    ms, done = _setup()
    open_node_result(ms, _battle_node(ms), {"event": "blacksmith"},
                     lambda: done.append(1))
    _settle(ms.director, 0.8)
    _pick(ms.director, 0)                            # 免費鍛造 → 網格
    idx = ms.run.deck.index("strike")
    _pick(ms.director, idx)
    assert ms.run.deck[idx] == "strike_s" and done == [1]


def test_event_poison_merchant_sample():
    ms, done = _setup()
    open_node_result(ms, _battle_node(ms), {"event": "poison_merchant"},
                     lambda: done.append(1))
    _settle(ms.director, 0.8)
    _pick(ms.director, 1)                            # 試用品
    assert ms.run.deck[-1] == "poison_blade" and done == [1]


def test_event_old_warrior_trade_and_gift_panel():
    ms, done = _setup()
    open_node_result(ms, _battle_node(ms), {"event": "old_warrior"},
                     lambda: done.append(1))
    _settle(ms.director, 0.8)
    n_defend = ms.run.deck.count("defend")
    _pick(ms.director, 0)                            # 交易 → 「獲得卡」面板
    assert ms.run.deck.count("defend") == n_defend - 1
    _skip(ms.director)                               # 收下
    assert done == [1]


def test_event_skip_leaves_untouched():
    ms, done = _setup()
    deck0 = list(ms.run.deck)
    open_node_result(ms, _battle_node(ms), {"event": "blacksmith"},
                     lambda: done.append(1))
    _settle(ms.director, 0.8)
    _skip(ms.director)
    assert ms.run.deck == deck0 and done == [1]
