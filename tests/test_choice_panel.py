"""tests/test_choice_panel.py — 共用抉擇面板(A3.3)單元驗收"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from ui.choice_panel import ChoicePanel, Option  # noqa: E402
from ui.scenes import Director, Scene  # noqa: E402

W, H = 960, 540


@pytest.fixture(scope="module", autouse=True)
def _pygame():
    pygame.init()
    pygame.display.set_mode((W, H))
    yield   # quit 統一在 conftest


def _setup(options, **kw):
    d = Director(W, H)
    d.push(Scene(), transition=None)         # 底層場景(pop 的落點)
    chosen = []
    panel = ChoicePanel("測試", options, chosen.append, **kw)
    d.push(panel, transition=None)
    return d, panel, chosen


def _settle(d, secs, step=0.05):
    screen = pygame.display.get_surface()
    for _ in range(int(secs / step)):
        d.update(step)
        d.draw(screen)


def _click(d, pos):
    d.handle(pygame.event.Event(
        pygame.MOUSEBUTTONDOWN, {"pos": (round(pos[0]), round(pos[1])),
                                 "button": 1}))


def test_options_slide_in_staggered():
    d, panel, _ = _setup([Option("甲"), Option("乙"), Option("丙")])
    _settle(d, 0.2)
    o = panel.options
    assert o[0].y < o[1].y < o[2].y          # 錯相:先進場的先落定
    _settle(d, 1.0)
    assert o[0].y == o[1].y == o[2].y        # 全部落定同一列


def test_choose_flies_fades_pops_and_calls_back():
    d, panel, chosen = _setup([Option("甲"), Option("乙")])
    _settle(d, 0.8)
    _click(d, panel._rect_of(panel.options[1]).center)
    assert panel.locked and chosen == []      # 飛行中,回呼未觸發
    _settle(d, 1.4)
    assert chosen == [1]
    assert panel.options[0].k < 0.2           # 未選者已淡出
    assert d.scene is not panel               # 面板已 pop


def test_skip_returns_none():
    d, panel, chosen = _setup([Option("甲")], skip_label="跳過")
    _settle(d, 0.8)
    _click(d, panel._skip_rect.center)
    _settle(d, 0.8)
    assert chosen == [None] and d.scene is not panel


def test_disabled_option_not_clickable():
    d, panel, chosen = _setup([Option("甲", enabled=False)])
    _settle(d, 0.8)
    _click(d, panel._rect_of(panel.options[0]).center)
    _settle(d, 1.0)
    assert chosen == [] and d.scene is panel


def test_locked_ignores_second_click():
    d, panel, chosen = _setup([Option("甲"), Option("乙")])
    _settle(d, 0.8)
    _click(d, panel._rect_of(panel.options[0]).center)
    _click(d, panel._rect_of(panel.options[1]).center)   # 已鎖:忽略
    _settle(d, 1.4)
    assert chosen == [0]


def test_grid_layout_for_many_options_stays_on_screen():
    opts = [Option(f"卡{i}") for i in range(25)]
    d, panel, _ = _setup(opts)
    assert panel.grid
    _settle(d, 1.5)
    xs = [o.x for o in opts]
    ys = [o.y for o in opts]
    assert len(set(round(y) for y in ys)) >= 3       # 多列
    assert min(xs) > 40 and max(xs) < W - 40         # 不出界
    assert max(ys) < H - 60


def test_sweep_draws_without_crash():
    d, panel, _ = _setup([Option("甲")], sweep_color=(255, 184, 77))
    _settle(d, 0.6)                                  # 橫掃期間含結束後
