"""tests/test_glow.py — 發光渲染(A2.2)驗收

無需螢幕:SDL dummy driver 下 Surface 運算全在軟體端執行,
效能測試量到的正是每幀 blit 的真實 CPU 成本。
驗收門(A2.2):200 節點地圖 60fps → clock.get_fps() > 55。
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from ui import glow  # noqa: E402

BG = (5, 10, 20)          # 底色 #050A14
NEON = (61, 255, 158)     # 毒 #3DFF9E


@pytest.fixture(scope="module")
def screen():
    pygame.init()
    yield pygame.display.set_mode((960, 540))
    # quit 統一在 conftest(session 結束);模組內 quit 會讓字體快取懸空


@pytest.fixture(autouse=True)
def fresh_cache():
    glow.clear_cache()
    yield
    glow.clear_cache()


# ------------------------------------------------------------------ 快取

def test_bake_circle_cached_same_object(screen):
    a = glow.bake_glow_circle(12, NEON)
    b = glow.bake_glow_circle(12, NEON)
    assert a is b
    assert glow.cache_size() == 1


def test_bake_line_cached_same_object(screen):
    a = glow.bake_glow_line(80, -40, NEON, 2)
    b = glow.bake_glow_line(80, -40, NEON, 2)
    assert a is b


def test_different_params_different_bakes(screen):
    glow.bake_glow_circle(12, NEON)
    glow.bake_glow_circle(16, NEON)
    glow.bake_glow_circle(12, (255, 77, 77))
    assert glow.cache_size() == 3


def test_layers_capped_at_max(screen):
    a = glow.bake_glow_circle(10, NEON, layers=9)
    b = glow.bake_glow_circle(10, NEON, layers=glow.MAX_LAYERS)
    assert a is b   # 超過上限被夾到 MAX_LAYERS → 命中同一快取鍵


def test_invalid_radius_rejected(screen):
    with pytest.raises(ValueError):
        glow.bake_glow_circle(0, NEON)


# ------------------------------------------------------------------ 視覺性質

def test_glow_circle_core_brighter_than_halo_edge(screen):
    surf = pygame.Surface((100, 100))
    surf.fill(BG)
    glow.glow_circle(surf, (50, 50), 10, NEON)
    core = surf.get_at((50, 50))
    halo = surf.get_at((50, 50 - 17))     # 半徑 10 的外暈(<20)內
    outside = surf.get_at((50, 5))        # 光暈外 → 保持底色
    assert core.g > halo.g > BG[1]
    assert (outside.r, outside.g, outside.b) == BG


def test_glow_is_additive_when_stacked(screen):
    surf = pygame.Surface((100, 100))
    surf.fill(BG)
    glow.glow_circle(surf, (50, 50), 10, (40, 40, 40))
    once = surf.get_at((50, 50)).g
    glow.glow_circle(surf, (50, 50), 10, (40, 40, 40))
    twice = surf.get_at((50, 50)).g
    assert twice > once                   # 疊光更亮(加法混合)


def test_glow_line_lights_midpoint_only_near_segment(screen):
    surf = pygame.Surface((200, 100))
    surf.fill(BG)
    glow.glow_line(surf, (20, 50), (180, 50), NEON, 2)
    mid = surf.get_at((100, 50))
    far = surf.get_at((100, 10))          # 離線 40px → 不受影響
    assert mid.g > BG[1]
    assert (far.r, far.g, far.b) == BG


def test_glow_offscreen_blit_is_safe(screen):
    surf = pygame.Surface((100, 100))
    glow.glow_circle(surf, (-30, -30), 12, NEON)      # 部分/全部出界
    glow.glow_line(surf, (-50, 50), (150, 50), NEON, 2)


# ------------------------------------------------------------------ 效能驗收門(A2.2)

def test_perf_200_node_map_holds_60fps(screen):
    """模擬 MapScene 滿載:200 發光節點 + 220 發光邊,斷言 >55 fps。"""
    rng_nodes = [((i * 37) % 900 + 30, (i * 53) % 480 + 30, 8 + i % 5)
                 for i in range(200)]
    edges = [(rng_nodes[i % 200][:2], rng_nodes[(i * 7 + 1) % 200][:2])
             for i in range(220)]
    colors = [NEON, (255, 77, 77), (77, 166, 255), (255, 184, 77),
              (199, 125, 255), (127, 212, 255)]

    clock = pygame.time.Clock()
    for frame in range(40):
        screen.fill(BG)
        for i, (a, b) in enumerate(edges):
            glow.glow_line(screen, a, b, (127, 212, 255), 2)
        for i, (x, y, r) in enumerate(rng_nodes):
            glow.glow_circle(screen, (x, y), r, colors[i % len(colors)])
        pygame.display.flip()
        clock.tick()
    fps = clock.get_fps()
    assert fps > 55, f"200 節點地圖僅 {fps:.1f} fps(驗收門 >55)"
