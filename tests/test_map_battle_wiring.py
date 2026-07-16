"""tests/test_map_battle_wiring.py — 地圖 ↔ 戰鬥接線(U4 收尾)

MapScene 不給 battle_hook 時,戰鬥節點應推入 BattleScene 互動對戰,
打完把 (win, hp_left) 餵回 enter_node,獎勵/金幣/藥水照 core 規則走。
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from core.potions import POTIONS  # noqa: E402
from core.run import GOLD_PER_WIN, RunState, next_choices  # noqa: E402
from ui.battle_scene import BattleScene  # noqa: E402
from ui.choice_panel import ChoicePanel  # noqa: E402
from ui.map_scene import MapScene  # noqa: E402
from ui.scenes import Director  # noqa: E402

W, H = 960, 540


@pytest.fixture(scope="module", autouse=True)
def _pygame():
    pygame.init()
    pygame.display.set_mode((W, H))
    yield   # quit 統一在 conftest(session 結束);模組內 quit 會讓字體快取懸空


def _scene(seed=7):
    d = Director(W, H)
    s = MapScene(RunState(seed=seed))       # 無 hook → 互動戰鬥
    d.push(s, transition=None)
    return s


def _settle(s, secs, step=0.05):
    screen = pygame.display.get_surface()
    for _ in range(int(secs / step)):
        s.director.update(step)
        s.director.draw(screen)


def _enter_first_battle(s):
    """點第 1 層節點(必為 battle),推近+fade 完成後回到 BattleScene。"""
    target = next_choices(s.run)[0]
    assert target.node_type == "battle"
    sx, sy = s.director.camera.world_to_screen(
        *s.pos[(target.layer, target.index)])
    s.director.handle(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"pos": (round(sx), round(sy)), "button": 1}))
    _settle(s, 1.6)                          # 鏡頭推近 0.7s + fade 0.5s
    return target


def _drain_panels(s, pick_first=False):
    """收掉 U5 抉擇面板:預設點跳過/離開,無跳過鈕則點第一個可選項。
    pick_first=True 時獎勵面板也拿第一張(對齊舊的 headless 佔位策略)。"""
    d = s.director
    for _ in range(6):
        if not isinstance(d.scene, ChoicePanel):
            return
        p = d.scene
        if p.skip_label and not pick_first:
            pos = p._skip_rect.center
        else:
            enabled = [o for o in p.options if o.enabled]
            pos = p._rect_of(enabled[0]).center if enabled \
                else p._skip_rect.center
        d.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                    {"pos": pos, "button": 1}))
        _settle(s, 1.8)


def test_battle_node_pushes_battle_scene_with_spawned_enemy():
    s = _scene()
    target = _enter_first_battle(s)
    bs = s.director.scene
    assert isinstance(bs, BattleScene)
    assert bs.s.enemy.enemy_id == target.enemy_id
    assert bs.s.player.hp == s.run.hp        # run 狀態帶進戰鬥
    assert s.run.position is None            # enter_node 等戰後才呼叫


def test_win_flows_back_to_map_with_rewards_and_gold():
    s = _scene()
    target = _enter_first_battle(s)
    bs = s.director.scene
    deck0 = len(s.run.deck)
    bs.on_finish(True, 37)                   # 模擬打贏(戰鬥本體另有測試)
    assert s.run.position == target
    assert s.run.hp == 37                    # hp_left 寫回 run
    assert s.run.gold == GOLD_PER_WIN
    _settle(s, 1.0)                          # 獎勵面板(U5)滑入
    assert isinstance(s.director.scene, ChoicePanel)
    _drain_panels(s, pick_first=True)        # 拿第一張
    assert len(s.run.deck) == deck0 + 1
    _settle(s, 1.0)                          # 鏡頭拉回
    assert s.director.scene is s and not s.busy
    assert s.walked == [(target.layer, target.index)]


def test_defeat_marks_run_over_and_overlay():
    s = _scene()
    _enter_first_battle(s)
    s.director.scene.on_finish(False, 0)
    assert s.run.over and not s.run.victory
    assert s.outcome == "defeated"
    _settle(s, 1.6)
    surf = pygame.display.get_surface()
    s.director.draw(surf)                    # 覆蓋文字不炸即可(勝負另測)


def test_potions_ride_into_battle_and_back():
    s = _scene()
    pid = sorted(POTIONS)[0]
    s.run.potions = [pid]
    _enter_first_battle(s)
    bs = s.director.scene
    assert bs.s.player.potions == [pid]      # 藥水進場
    bs.s.player.potions.clear()              # 模擬戰鬥中喝掉
    bs.on_finish(True, 40)
    assert s.run.potions == []               # 戰後寫回剩餘(先於獎勵面板)
    _settle(s, 1.0)
    _drain_panels(s)


def test_full_interactive_run_via_ui_clicks():
    """整合驗收:完整一輪冒險——地圖點節點、戰鬥由規則式代理經 UI
    點擊打完,直到勝利或倒下(兩者都算接線正確)。"""
    from agents.rule_based import RuleBasedAgent
    from ui.battle_scene import END_TURN_RECT

    s = _scene(seed=3)
    agent = RuleBasedAgent()
    d = s.director
    for _ in range(40):                      # 上限:節點數 + 餘裕
        if s.run.over:
            break
        target = next_choices(s.run)[0]
        sx, sy = d.camera.world_to_screen(
            *s.pos[(target.layer, target.index)])
        d.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                    {"pos": (round(sx), round(sy)),
                                     "button": 1}))
        _settle(s, 1.6)                      # 推近(+fade 進戰鬥)
        if isinstance(d.scene, BattleScene):
            bs = d.scene
            for _ in range(300):
                if bs.s.battle_over:
                    break
                a = agent.choose_action(bs.s)
                if a[0] == "play":
                    rect = next(r for r, cid, ok in bs._card_rects
                                if cid == a[1] and ok)
                    pos = rect.center
                else:
                    pos = END_TURN_RECT.center
                d.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                            {"pos": pos, "button": 1}))
                _settle(s, 0.45)
            d.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                        {"pos": (480, 270), "button": 1}))
            _settle(s, 1.6)                  # pop fade + 獎勵面板/鏡頭拉回
        _drain_panels(s)                     # 收掉 U5 面板(獎勵/休息/商店/事件)
        _settle(s, 1.0)
    assert s.run.over                        # 勝敗皆可,流程必須走得完
    assert s.outcome in ("victory", "defeated")
    assert len(s.run.floor_log) == len(s.walked)


def test_explicit_hook_still_synchronous_no_scene_push():
    d = Director(W, H)
    s = MapScene(RunState(seed=7), battle_hook=lambda r, n: (True, r.hp))
    d.push(s, transition=None)
    target = next_choices(s.run)[0]
    sx, sy = d.camera.world_to_screen(*s.pos[(target.layer, target.index)])
    d.handle(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"pos": (round(sx), round(sy)), "button": 1}))
    _settle(s, 0.8)
    assert d.scene is s                      # 沒推 BattleScene
    assert s.run.position == target          # 同步結算完成
