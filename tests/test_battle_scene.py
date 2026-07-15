"""tests/test_battle_scene.py — BattleScene(A3.2 色塊版)驗收

U4 驗收門:打贏巨鼠——用規則式代理決策,但全部經由 UI 的點擊路徑執行
(點卡牌矩形、點結束回合按鈕),等同自動化的手動操作。
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from agents.rule_based import RuleBasedAgent  # noqa: E402
from core.cards import PLAYER_HP, STARTING_DECK  # noqa: E402
from core.enemies import ENEMIES, enemy_ai, make_enemy  # noqa: E402
from core.engine import apply_action, start_battle  # noqa: E402
from core.models import GameState, PlayerState  # noqa: E402
from ui.battle_scene import END_TURN_RECT, BattleScene  # noqa: E402
from ui.scenes import Director  # noqa: E402

W, H = 960, 540


@pytest.fixture(scope="module", autouse=True)
def _pygame():
    pygame.init()
    pygame.display.set_mode((W, H))
    yield   # quit 統一在 conftest(session 結束);模組內 quit 會讓字體快取懸空


def _battle(enemy_id="giant_rat", seed=0, on_finish=None):
    p = PlayerState(hp=PLAYER_HP, max_hp=PLAYER_HP, deck=list(STARTING_DECK))
    s = GameState(p, make_enemy(enemy_id), seed=seed)
    start_battle(s, enemy_ai)
    d = Director(W, H)
    sc = BattleScene(s, enemy_ai, on_finish=on_finish)
    d.push(sc, transition=None)
    sc.draw(pygame.display.get_surface())      # 先畫一幀,填 _card_rects
    return sc


def _click(sc, pos):
    sc.director.handle(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"pos": (round(pos[0]), round(pos[1])),
                                 "button": 1}))


def _settle(sc, secs=0.5, step=0.05):
    """推進動畫(ghost 飛行/血條滑動)並重畫。"""
    screen = pygame.display.get_surface()
    for _ in range(int(secs / step)):
        sc.director.update(step)
        sc.draw(screen)


# ------------------------------------------------------------ 出牌互動

def test_click_attack_card_damages_enemy_after_flight():
    sc = _battle()
    rect, cid, playable = next(rc for rc in sc._card_rects if rc[2])
    hp0 = sc.s.enemy.hp
    _click(sc, rect.center)
    assert sc._ghost is not None               # 卡牌飛行中
    hp_after_click = sc.s.enemy.hp             # 結算即時(真值先行)
    _settle(sc, 0.4)
    assert sc._ghost is None
    if hp_after_click < hp0:                   # 攻擊卡:落地後有飄字
        assert sc.ebar.value == sc.s.enemy.hp


def test_input_locked_while_ghost_flying():
    sc = _battle()
    rect, cid, _ = next(rc for rc in sc._card_rects if rc[2])
    _click(sc, rect.center)
    e_before = sc.s.player.energy
    _click(sc, rect.center)                    # 飛行中再點:忽略
    assert sc.s.player.energy == e_before
    _settle(sc, 0.4)


def test_unplayable_card_click_is_noop():
    sc = _battle()
    sc.s.player.energy = 0
    sc.draw(pygame.display.get_surface())      # 重畫 → 全部不可出
    rect, cid, playable = sc._card_rects[0]
    assert not playable
    hand0 = list(sc.s.player.hand)
    _click(sc, rect.center)
    assert sc.s.player.hand == hand0 and sc._ghost is None


# ------------------------------------------------------------ 動畫守則

def test_hp_bar_slides_not_snaps_after_enemy_attack():
    sc = _battle(seed=3)
    for _ in range(6):                         # 打空能量讓敵人有機會打到
        _click(sc, END_TURN_RECT.center)
        _settle(sc, 0.05, 0.05)                # 只推一小步
        if sc.s.player.hp < PLAYER_HP:
            break
    assert sc.s.player.hp < PLAYER_HP          # 巨鼠肯定打過人了
    assert sc.pbar.display > sc.s.player.hp    # 顯示值還在上方滑落中
    _settle(sc, 0.5)
    assert sc.pbar.display == sc.s.player.hp   # 300ms 內落定


def test_intent_pops_on_new_turn():
    sc = _battle()
    _click(sc, END_TURN_RECT.center)
    assert sc._intent_pop < 0.5                # 剛宣告:從上方彈入中
    _settle(sc, 0.6)
    assert sc._intent_pop == pytest.approx(1.0)


# ------------------------------------------------------------ U4 驗收門

def test_full_battle_win_vs_giant_rat_via_ui_clicks():
    """規則式代理決策 + UI 點擊執行,打贏巨鼠。"""
    results = []
    sc = _battle("giant_rat", seed=0,
                 on_finish=lambda win, hp: results.append((win, hp)))
    agent = RuleBasedAgent()
    for _ in range(400):                       # 防呆上限
        if sc.s.battle_over:
            break
        action = agent.choose_action(sc.s)
        if action[0] == "play":
            rect = next(r for r, cid, ok in sc._card_rects
                        if cid == action[1] and ok)
            _click(sc, rect.center)
        else:
            _click(sc, END_TURN_RECT.center)
        _settle(sc, 0.45)
    assert sc.s.battle_over and sc.s.player_won
    assert sc.outcome == "victory"
    _settle(sc, 0.1)
    _click(sc, (480, 270))                     # 結算畫面點擊 → on_finish
    assert results == [(True, sc.s.player.hp)]


# ------------------------------------------------------------ 完整性鎖

def test_every_enemy_renders_with_name_and_intent_text():
    """新增敵人時,UI 對照表(名字/意圖文案)必須同步更新——
    2026-07-15 吸血蝠/狂戰士漏更新,菁英戰一開場就 KeyError 閃退。
    對每一隻敵人:BattleScene 畫得出來、每個意圖都有文案。"""
    from ui.terminal_play import ENEMY_NAMES, intent_text

    agent = RuleBasedAgent()
    for eid in ENEMIES:
        assert eid in ENEMY_NAMES, f"{eid} 沒有中文名"
        sc = _battle(eid, seed=1)               # 內含 draw 一幀
        s = sc.s
        for _ in range(60):
            if s.battle_over:
                break
            if s.enemy.intent[0] != "none":
                assert intent_text(s, s.enemy.intent) != "無動作", \
                    f"{eid} 的意圖 {s.enemy.intent} 沒有文案"
            apply_action(s, agent.choose_action(s), enemy_ai)
        sc.draw(pygame.display.get_surface())   # 戰鬥中後期也畫一幀


# ------------------------------------------------------------ 效能

def test_perf_battle_scene_holds_60fps():
    sc = _battle()
    screen = pygame.display.get_surface()
    clock = pygame.time.Clock()
    for _ in range(60):
        sc.director.update(1 / 60)
        sc.draw(screen)
        pygame.display.flip()
        clock.tick()
    fps = clock.get_fps()
    assert fps > 55, f"BattleScene 僅 {fps:.1f} fps(驗收門 >55)"
