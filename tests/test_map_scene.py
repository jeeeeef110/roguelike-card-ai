"""tests/test_map_scene.py — MapScene(A3.1 色塊版)驗收

U3 驗收門:完整走完一輪地圖(戰鬥自動勝 stub),全程 headless 模擬點擊。
"""
import math
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from core.run import RunState, next_choices  # noqa: E402
from ui import glow  # noqa: E402
from ui.map_scene import (BASE_SPACING, PERSPECTIVE, MapScene,  # noqa: E402
                          _layout)
from ui.scenes import Director  # noqa: E402

W, H = 960, 540


def _auto_win(run, node):
    return True, run.hp     # U3 stub:自動勝、不掉血


def _click(scene, node):
    """對節點中心送一個合成滑鼠事件(經鏡頭換算成螢幕座標)。"""
    sx, sy = scene.director.camera.world_to_screen(
        *scene.pos[(node.layer, node.index)])
    scene.director.handle(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"pos": (round(sx), round(sy)), "button": 1}))


@pytest.fixture(scope="module", autouse=True)
def _pygame():
    pygame.init()
    pygame.display.set_mode((W, H))
    yield   # quit 統一在 conftest(session 結束);模組內 quit 會讓字體快取懸空


@pytest.fixture()
def scene():
    glow.clear_cache()
    d = Director(W, H)
    s = MapScene(RunState(seed=7), _auto_win)
    d.push(s, transition=None)
    return s


# ------------------------------------------------------------ 佈局

def test_layout_has_perspective_compression(scene):
    """越深的層,節點 x 間距越窄(近大遠小);y 隨層遞減。"""
    pos = _layout(scene.run.game_map)
    for row in scene.run.game_map.layers:
        li = row[0].layer
        if len(row) >= 2:
            gap = abs(pos[(li, 1)][0] - pos[(li, 0)][0])
            assert gap == pytest.approx(BASE_SPACING * PERSPECTIVE ** (li - 1))
    ys = [pos[(row[0].layer, 0)][1] for row in scene.run.game_map.layers]
    assert ys == sorted(ys, reverse=True)   # 第 1 層在下(y 最大)


# ------------------------------------------------------------ 呼吸與待機

def test_breath_stays_in_spec_range_and_staggers(scene):
    """亮度 0.6↔1.0(A3.1);相鄰可走節點錯相(同時刻亮度不同)。"""
    lo, hi = 2.0, -1.0
    for step in range(200):
        scene.update(0.03)
        b0, b1 = scene._breath(0), scene._breath(1)
        lo, hi = min(lo, b0), max(hi, b0)
        if step == 10:
            assert abs(b0 - b1) > 0.05      # 錯相
    assert lo == pytest.approx(0.6, abs=0.01)
    assert hi == pytest.approx(1.0, abs=0.01)


# ------------------------------------------------------------ 點擊與行走

def test_click_reachable_node_walks_after_camera_animation(scene):
    target = next_choices(scene.run)[0]
    _click(scene, target)
    assert scene.busy and scene.run.position is None    # 推近中,尚未結算
    scene.director.update(0.8)                          # 推近完成 → 結算
    assert scene.run.position == target
    scene.director.update(0.8)                          # 拉回完成
    assert not scene.busy


def test_click_ignored_when_far_or_busy(scene):
    far = pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                             {"pos": (5, 5), "button": 1})
    scene.director.handle(far)
    assert not scene.busy                               # 點空白處沒反應
    target = next_choices(scene.run)[0]
    _click(scene, target)
    other = next_choices(scene.run)[0]
    _click(scene, other)                                # busy 中再點:忽略
    scene.director.update(1.6)
    assert scene.run.floor_log == ["battle"]            # 只走了一步


def test_full_walk_reaches_boss_and_victory(scene):
    """U3 驗收門:一路點到 Boss,自動勝 stub 下必勝。"""
    screen = pygame.display.get_surface()
    for _ in range(20):                                 # 最多 20 步(10 層)
        if scene.run.over:
            break
        _click(scene, next_choices(scene.run)[0])
        for _ in range(50):                             # 推近+結算+拉回
            scene.director.update(0.033)
            scene.director.draw(screen)
    assert scene.run.over and scene.run.victory
    assert scene.outcome == "victory"
    assert len(scene.walked) == len(scene.run.game_map.layers)
    assert scene.run.floor_log[-1] == "boss"
    assert len(scene.run.deck) > 15                     # 獎勵有自動入庫


def test_input_dead_after_run_over(scene):
    scene.outcome = "victory"
    _click(scene, next_choices(scene.run)[0])
    assert not scene.busy


# ------------------------------------------------------------ 效能與快取

def test_glow_cache_stays_bounded_over_full_walk(scene):
    """呼吸亮度 8 階量化 + 半徑步進 2 → 快取鍵有界,不隨幀數膨脹。"""
    screen = pygame.display.get_surface()
    for _ in range(20):
        if scene.run.over:
            break
        _click(scene, next_choices(scene.run)[0])
        for _ in range(50):
            scene.director.update(0.033)
            scene.director.draw(screen)
    assert glow.cache_size() < 600, f"快取 {glow.cache_size()} 張,疑似未量化"


def test_perf_map_scene_holds_60fps(scene):
    screen = pygame.display.get_surface()
    clock = pygame.time.Clock()
    for _ in range(60):
        scene.director.update(1 / 60)
        scene.director.draw(screen)
        pygame.display.flip()
        clock.tick()
    fps = clock.get_fps()
    assert fps > 55, f"MapScene 僅 {fps:.1f} fps(驗收門 >55)"
