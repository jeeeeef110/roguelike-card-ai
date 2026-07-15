"""tests/test_ui_math.py — UI 純數學層(tween + camera):藍圖 U1 驗收門"""
import pytest
from ui.camera import Camera
from ui.tween import (EASINGS, Tween, TweenManager, ease_in_out,
                      ease_out_back, ease_out_cubic, linear)


class Obj:
    def __init__(self):
        self.y = 0.0
        self.zoom = 1.0


# ------------------------------------------------------------------ easing


def test_all_easings_hit_endpoints():
    for name, f in EASINGS.items():
        assert abs(f(0.0)) < 1e-9, name
        assert abs(f(1.0) - 1.0) < 1e-9, name


def test_easings_monotone_enough_midpoint():
    assert linear(0.5) == 0.5
    assert ease_out_cubic(0.5) == 0.875
    assert ease_in_out(0.5) == 0.5
    assert ease_out_back(0.9) > 1.0      # 過衝存在
    assert abs(ease_out_back(1.0) - 1.0) < 1e-9  # 但精確回 1


# ------------------------------------------------------------------ tween


def test_tween_reaches_exact_end():
    o = Obj()
    tw = Tween(o, "y", 0, 480, duration=0.3)
    for _ in range(100):
        tw.update(0.016)
    assert o.y == 480.0 and tw.done


def test_tween_midway_value_matches_easing():
    o = Obj()
    tw = Tween(o, "y", 0, 100, duration=1.0, easing=linear)
    tw.update(0.5)
    assert abs(o.y - 50.0) < 1e-9


def test_delay_holds_value_then_runs():
    o = Obj()
    o.y = 7.0
    tw = Tween(o, "y", 0, 100, duration=1.0, delay=0.5, easing=linear)
    tw.update(0.4)
    assert o.y == 7.0                    # delay 中不動
    tw.update(0.6)                       # 進入第 0.5 秒的活動期
    assert abs(o.y - 50.0) < 1e-9


def test_on_done_fires_exactly_once():
    o = Obj()
    calls = []
    tw = Tween(o, "y", 0, 1, duration=0.1, on_done=lambda: calls.append(1))
    for _ in range(20):
        tw.update(0.05)
    assert calls == [1]


def test_zero_duration_rejected():
    with pytest.raises(ValueError):
        Tween(Obj(), "y", 0, 1, duration=0)


def test_manager_same_attr_replaces_old():
    o = Obj()
    tm = TweenManager()
    tm.add(Tween(o, "y", 0, 100, duration=1.0, easing=linear))
    tm.add(Tween(o, "y", 0, -100, duration=1.0, easing=linear))  # 後蓋前
    assert tm.active_count == 1
    tm.update(1.1)
    assert o.y == -100.0 and tm.active_count == 0


def test_manager_parallel_different_attrs():
    o = Obj()
    tm = TweenManager()
    tm.add(Tween(o, "y", 0, 10, duration=0.2))
    tm.add(Tween(o, "zoom", 1, 2, duration=0.2))
    assert tm.active_count == 2
    tm.update(0.3)
    assert o.y == 10.0 and o.zoom == 2.0


# ------------------------------------------------------------------ camera


def test_camera_center_maps_to_screen_center():
    cam = Camera(1280, 720, x=100, y=50, zoom=2.0)
    assert cam.world_to_screen(100, 50) == (640, 360)


def test_camera_roundtrip():
    cam = Camera(1280, 720, x=-30, y=200, zoom=1.6)
    for wx, wy in [(0, 0), (123.4, -56.7), (-500, 999)]:
        sx, sy = cam.world_to_screen(wx, wy)
        bx, by = cam.screen_to_world(sx, sy)
        assert abs(bx - wx) < 1e-6 and abs(by - wy) < 1e-6


def test_camera_zoom_scales_distances():
    cam = Camera(800, 600, zoom=3.0)
    (ax, _), (bx, _) = cam.world_to_screen(0, 0), cam.world_to_screen(10, 0)
    assert abs((bx - ax) - 30.0) < 1e-9


def test_visible_rect_shrinks_with_zoom():
    cam = Camera(800, 600, zoom=2.0)
    left, top, w, h = cam.visible_rect()
    assert (w, h) == (400, 300) and (left, top) == (-200, -150)


def test_camera_tweenable_by_manager():
    """整合:鏡頭推近=三個 tween 併行(場景層的實際用法)。"""
    cam = Camera(1280, 720)
    tm = TweenManager()
    for attr, end in cam.pan_zoom_targets(300, -120, 1.6).items():
        tm.add(Tween(cam, attr, getattr(cam, attr), end, duration=0.7))
    tm.update(1.0)
    assert (cam.x, cam.y, cam.zoom) == (300.0, -120.0, 1.6)
    assert cam.world_to_screen(300, -120) == (640, 360)


def test_camera_invalid_args_rejected():
    with pytest.raises(ValueError):
        Camera(0, 600)
    with pytest.raises(ValueError):
        Camera(800, 600, zoom=0)
    with pytest.raises(ValueError):
        Camera(800, 600).pan_zoom_targets(0, 0, 0)
