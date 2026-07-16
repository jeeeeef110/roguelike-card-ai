"""tests/test_settle_scene.py — SettleScene 養成接線(U6)驗收

結算數字走 meta.settle_run、Boss 解鎖三選一走 meta.unlock_rare、
存檔續玩(save → load 回同一狀態)、MapScene 冒險結束通知。
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from core.meta import MetaState  # noqa: E402
from core.run import RunState, next_choices  # noqa: E402
from ui.choice_panel import ChoicePanel  # noqa: E402
from ui.map_scene import MapScene  # noqa: E402
from ui.scenes import Director, Scene  # noqa: E402
from ui.settle_scene import SettleScene  # noqa: E402

W, H = 960, 540


@pytest.fixture(scope="module", autouse=True)
def _pygame():
    pygame.init()
    pygame.display.set_mode((W, H))
    yield   # quit 統一在 conftest


def _finished_run(victory=True):
    run = RunState(seed=5)
    run.floor_log = ["battle", "elite", "rest", "battle", "boss"]
    run.over = True
    run.victory = victory
    return run


def _setup(victory=True, save_path=None, meta=None):
    d = Director(W, H)
    d.push(Scene(), transition=None)
    meta = meta or MetaState(meta_seed=1)
    done = []
    sc = SettleScene(meta, _finished_run(victory), lambda: done.append(1),
                     save_path=save_path)
    d.push(sc, transition=None)
    return sc, meta, done


def _settle(d, secs, step=0.05):
    screen = pygame.display.get_surface()
    for _ in range(int(secs / step)):
        d.update(step)
        d.draw(screen)


def _click(d, pos=(480, 270)):
    d.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                {"pos": pos, "button": 1}))


def test_settle_rolls_shards_and_updates_meta():
    sc, meta, done = _setup(victory=True)
    # 5 層×2 + 1 菁英×5 + Boss 20 = 35
    assert sc.gained == 35 and meta.shards == 35
    assert meta.runs == 1 and meta.wins == 1 and meta.ascension_best == 1
    assert sc.shown < 35                       # 滾動中
    _settle(sc.director, 1.4)
    assert sc.shown == 35                      # 滾完精確落定


def test_click_fast_forwards_roll():
    sc, _, _ = _setup()
    _settle(sc.director, 0.2)
    _click(sc.director)
    _settle(sc.director, 0.1)
    assert sc.shown == sc.gained


def test_victory_click_opens_unlock_panel_and_unlocks():
    sc, meta, done = _setup(victory=True)
    locked0 = len(meta.locked_rares())
    _settle(sc.director, 1.4)
    _click(sc.director)                        # 滾動已完 → 解鎖面板
    _settle(sc.director, 1.0)
    panel = sc.director.scene
    assert isinstance(panel, ChoicePanel)
    assert panel.skip_label is None            # 不可跳過(收集軸主循環)
    assert 1 <= len(panel.options) <= 3
    _click(sc.director, panel._rect_of(panel.options[0]).center)
    _settle(sc.director, 1.6)
    assert len(meta.locked_rares()) == locked0 - 1
    assert done == [1]


def test_defeat_settles_without_unlock():
    sc, meta, done = _setup(victory=False)
    assert meta.wins == 0 and sc.gained == 15  # 5層×2+菁英5,無 Boss 20
    _settle(sc.director, 1.4)
    _click(sc.director)
    assert done == [1]                         # 直接結束,無面板


def test_all_unlocked_victory_skips_panel():
    meta = MetaState(meta_seed=1)
    for cid in list(meta.locked_rares()):
        meta.unlock_rare(cid)
    sc, meta, done = _setup(victory=True, meta=meta)
    _settle(sc.director, 1.4)
    _click(sc.director)
    assert done == [1]


def test_save_and_reload_persists_progress(tmp_path):
    path = tmp_path / "meta.json"
    sc, meta, done = _setup(victory=True, save_path=path)
    _settle(sc.director, 1.4)
    _click(sc.director)
    _settle(sc.director, 1.0)
    panel = sc.director.scene
    _click(sc.director, panel._rect_of(panel.options[0]).center)
    _settle(sc.director, 1.6)
    loaded = MetaState.load(path)              # 存檔續玩
    assert loaded.shards == meta.shards == 35
    assert loaded.unlocked_rares == meta.unlocked_rares
    assert loaded.ascension_best == 1


def test_map_scene_fires_on_run_over_after_camera_back():
    d = Director(W, H)
    overs = []
    s = MapScene(RunState(seed=7), battle_hook=lambda r, n: (True, r.hp),
                 on_run_over=overs.append)
    d.push(s, transition=None)
    screen = pygame.display.get_surface()
    for _ in range(20):
        if s.run.over:
            break
        target = next_choices(s.run)[0]
        sx, sy = d.camera.world_to_screen(*s.pos[(target.layer, target.index)])
        d.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN,
                                    {"pos": (round(sx), round(sy)),
                                     "button": 1}))
        for _ in range(50):
            d.update(0.033)
            d.draw(screen)
    assert s.run.over and overs == [s.run]     # 鏡頭拉回後通知一次


def test_run_uses_meta_unlocked_rares():
    meta = MetaState(meta_seed=1)
    run = RunState(seed=3, unlocked_rares=list(meta.unlocked_rares))
    assert run.unlocked_rares == meta.unlocked_rares
