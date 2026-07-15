"""tests/test_scenes.py — 場景管理與導演(A2.3)驗收

無需螢幕(SDL dummy driver)。
U2 驗收門:空場景切換 demo 60fps → clock.get_fps() > 55。
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from ui.scenes import BG, FADE_DURATION, PAN_DURATION, Director, Scene  # noqa: E402

W, H = 320, 180


@pytest.fixture(scope="module", autouse=True)
def _pygame():
    pygame.init()
    pygame.display.set_mode((W, H))
    yield   # quit 統一在 conftest(session 結束);模組內 quit 會讓字體快取懸空


class Probe(Scene):
    """記錄生命週期呼叫的探針場景,draw 時整面填單色。"""

    def __init__(self, color=(200, 0, 0)):
        self.color = color
        self.entered = 0
        self.exited = 0
        self.updated = 0.0
        self.events = []

    def on_enter(self):
        self.entered += 1

    def on_exit(self):
        self.exited += 1

    def handle(self, event):
        self.events.append(event)

    def update(self, dt):
        self.updated += dt

    def draw(self, surface):
        surface.fill(self.color)


def _px(surface, x, y):
    c = surface.get_at((x, y))
    return (c.r, c.g, c.b)


# ------------------------------------------------------------ 基本切換

def test_first_push_is_instant_and_injects_director():
    d = Director(W, H)
    a = Probe()
    d.push(a)                        # 堆疊空 → 無條件直切
    assert d.scene is a and a.entered == 1
    assert a.director is d and not d.transitioning


def test_transition_none_switches_instantly():
    d = Director(W, H)
    a, b = Probe(), Probe()
    d.push(a, transition=None)
    d.replace(b, transition=None)
    assert d.scene is b and a.exited == 1 and d.depth == 1


def test_pop_reenters_previous_scene():
    d = Director(W, H)
    a, b = Probe(), Probe()
    d.push(a, transition=None)
    d.push(b, transition=None)
    assert a.exited == 0             # 被 push 蓋住不算離場
    d.pop(transition=None)
    assert d.scene is a and b.exited == 1 and a.entered == 2


def test_pop_requires_two_scenes():
    d = Director(W, H)
    d.push(Probe(), transition=None)
    with pytest.raises(ValueError):
        d.pop()


def test_unknown_transition_rejected():
    d = Director(W, H)
    d.push(Probe(), transition=None)
    with pytest.raises(ValueError):
        d.replace(Probe(), transition="spin")


# ------------------------------------------------------------ fade 轉場

def test_fade_swaps_stack_at_midpoint_then_finishes():
    d = Director(W, H)
    a, b = Probe(), Probe()
    d.push(a, transition=None)
    d.replace(b, transition="fade")
    d.update(FADE_DURATION * 0.2)            # 前半:還是舊場景
    assert d.scene is a and d.transitioning
    d.update(FADE_DURATION * 0.4)            # 過中點:堆疊已交接
    assert d.scene is b and a.exited == 1 and b.entered == 1
    assert d.transitioning                   # 但淡出還在跑
    d.update(FADE_DURATION)                  # 收尾
    assert not d.transitioning and d.scene is b


def test_fade_screen_is_bg_color_at_midpoint():
    d = Director(W, H)
    d.push(Probe((200, 0, 0)), transition=None)
    d.replace(Probe((0, 0, 200)), transition="fade")
    d.update(FADE_DURATION / 2)              # ease_in_out(0.5)=0.5 → 全暗
    surf = pygame.Surface((W, H))
    d.draw(surf)
    assert _px(surf, W // 2, H // 2) == BG   # 遮罩全蓋 → 純底色


def test_input_blocked_during_transition_forwarded_after():
    d = Director(W, H)
    a, b = Probe(), Probe()
    d.push(a, transition=None)
    d.replace(b, transition="fade")
    d.handle("evt-mid")
    assert a.events == [] and b.events == []
    d.update(FADE_DURATION * 2)
    d.handle("evt-after")
    assert b.events == ["evt-after"]


def test_incoming_scene_updates_during_transition():
    d = Director(W, H)
    a, b = Probe(), Probe()
    d.push(a, transition=None)
    d.replace(b, transition="fade")
    d.update(0.1)
    assert b.updated > 0                     # 進場者動畫先跑


def test_new_transition_settles_previous_one():
    d = Director(W, H)
    a, b, c = Probe(), Probe(), Probe()
    d.push(a, transition=None)
    d.replace(b, transition="fade")
    d.replace(c, transition="fade")          # 前一轉場立即結清
    d.update(FADE_DURATION * 2)
    assert d.scene is c and a.exited == 1 and b.exited == 1 and d.depth == 1


# ------------------------------------------------------------ pan 轉場

def test_pan_shows_both_scenes_midway_then_lands():
    d = Director(W, H)
    a, b = Probe((200, 0, 0)), Probe((0, 0, 200))
    d.push(a, transition=None)
    d.replace(b, transition="pan")
    d.update(PAN_DURATION / 2)               # 進度 0.5:一半舊一半新
    surf = pygame.Surface((W, H))
    d.draw(surf)
    assert _px(surf, 2, H // 2) == (200, 0, 0)        # 左緣仍是舊場景
    assert _px(surf, W - 3, H // 2) == (0, 0, 200)    # 右緣已是新場景
    assert a.updated > 0 and b.updated > 0   # pan 全程雙方都在動
    d.update(PAN_DURATION)
    assert not d.transitioning and d.scene is b and a.exited == 1


def test_pan_pop_slides_reverse_direction():
    d = Director(W, H)
    a, b = Probe((200, 0, 0)), Probe((0, 0, 200))
    d.push(a, transition=None)
    d.push(b, transition=None)
    d.pop(transition="pan")
    d.update(PAN_DURATION / 2)
    surf = pygame.Surface((W, H))
    d.draw(surf)
    assert _px(surf, 2, H // 2) == (200, 0, 0)        # 舊場景 a 從左滑回
    assert _px(surf, W - 3, H // 2) == (0, 0, 200)    # b 往右退場
    d.update(PAN_DURATION)
    assert d.scene is a and a.entered == 2 and b.exited == 1


# ------------------------------------------------------------ U2 驗收門

def test_perf_empty_scene_switching_holds_60fps():
    """空場景 fade/pan 連續切換,斷言 >55 fps(U2 驗收)。"""
    screen = pygame.display.get_surface()
    d = Director(W, H)
    d.push(Probe((20, 30, 50)), transition=None)
    clock = pygame.time.Clock()
    for frame in range(120):
        if frame % 30 == 0:
            d.replace(Probe((20 + frame, 30, 50)),
                      transition="fade" if frame % 60 == 0 else "pan")
        d.update(1 / 60)
        d.draw(screen)
        pygame.display.flip()
        clock.tick()
    fps = clock.get_fps()
    assert fps > 55, f"空場景切換僅 {fps:.1f} fps(驗收門 >55)"
