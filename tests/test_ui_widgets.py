"""tests/test_ui_widgets.py — 文字快取(text.py)與戰鬥元件(widgets.py)"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from ui import text as uitext  # noqa: E402
from ui.tween import TweenManager  # noqa: E402
from ui.widgets import BAR_SLIDE_SECS, FloatTextLayer, SmoothBar  # noqa: E402

WHITE = (232, 240, 255)


@pytest.fixture(scope="module", autouse=True)
def _pygame():
    pygame.init()
    pygame.display.set_mode((320, 180))
    yield   # quit 統一在 conftest(session 結束);模組內 quit 會讓字體快取懸空


@pytest.fixture(autouse=True)
def _fresh_text_cache():
    uitext.clear_cache()


# ------------------------------------------------------------ text.py

def test_text_cached_same_object():
    a = uitext.text("HP 50", 20, WHITE)
    b = uitext.text("HP 50", 20, WHITE)
    assert a is b and uitext.cache_size() == 1


def test_cjk_renders_nonzero_width():
    img = uitext.text("結束回合", 20, WHITE)
    assert img.get_width() > 0 and img.get_height() > 0


def test_draw_text_align_and_rect():
    surf = pygame.Surface((320, 180))
    r = uitext.draw_text(surf, "42", (160, 90), 24, WHITE, align="center")
    assert r.center == (160, 90)


def test_cache_cap_clears_not_grows():
    for i in range(600):
        uitext.text(str(i), 12, WHITE)
    assert uitext.cache_size() <= 512


# ------------------------------------------------------------ SmoothBar

def test_bar_never_snaps_slides_in_300ms():
    tm = TweenManager()
    bar = SmoothBar((10, 10, 200, 16), (61, 255, 158), 50, tm)
    assert bar.display == 50.0
    bar.set(30)
    assert bar.display == 50.0                  # set 當下不瞬跳
    tm.update(BAR_SLIDE_SECS / 2)
    assert 30 < bar.display < 50                # 滑動中
    tm.update(BAR_SLIDE_SECS)
    assert bar.display == 30.0                  # 300ms 內精確落定


def test_bar_set_same_value_no_tween():
    tm = TweenManager()
    bar = SmoothBar((0, 0, 100, 10), (61, 255, 158), 50, tm)
    bar.set(50)
    assert tm.active_count == 0


def test_bar_draw_with_armor_ring():
    tm = TweenManager()
    bar = SmoothBar((20, 20, 100, 12), (61, 255, 158), 50, tm)
    surf = pygame.Surface((320, 180))
    bar.draw(surf, armor=5)                     # 藍描邊在條外
    c = surf.get_at((20 - 3, 26))
    assert (c.r, c.g, c.b) == (77, 166, 255)
    bar.draw(surf, armor=0)                     # 無護甲不畫環,不炸即可


# ------------------------------------------------------------ FloatText

def test_float_text_rises_then_dies():
    layer = FloatTextLayer()
    layer.spawn("-8", (100, 100))
    f = layer._floats[0]
    y0 = f.y
    layer.update(0.3)
    assert f.y < y0                             # 上飄
    layer.update(1.0)                           # 超過壽命
    assert layer.active_count == 0


def test_float_text_fades_out_late_life():
    layer = FloatTextLayer()
    layer.spawn("-8", (100, 100))
    surf = pygame.Surface((320, 180))
    layer.update(0.8)                           # 已進入淡出段
    layer.draw(surf)
    assert layer._floats[0].surf.get_alpha() < 255


def test_float_surfaces_are_copies_not_shared_cache():
    layer = FloatTextLayer()
    layer.spawn("-8", (100, 100), size=34)
    cached = uitext.text("-8", 34, WHITE, bold=True)
    assert layer._floats[0].surf is not cached  # 動 alpha 不污染共享快取
