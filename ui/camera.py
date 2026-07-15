"""ui/camera.py — 鏡頭系統(藍圖 U2 的純數學部分)

「鏡頭會呼吸」設計語言的基座:x / y / zoom 三個屬性都是普通 float,
可以直接被 Tween 驅動(推近節點=對 zoom 與 x,y 各下一個 tween)。
純數學、零依賴——場景繪製時用 world_to_screen 把世界座標換成螢幕座標。

慣例:鏡頭盯著世界座標 (x, y),該點永遠落在螢幕中心;zoom>1 = 放大。
"""
from __future__ import annotations


class Camera:
    __slots__ = ("x", "y", "zoom", "screen_w", "screen_h")

    def __init__(self, screen_w: int, screen_h: int,
                 x: float = 0.0, y: float = 0.0, zoom: float = 1.0):
        if screen_w <= 0 or screen_h <= 0 or zoom <= 0:
            raise ValueError("螢幕尺寸與 zoom 必須為正")
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.x = float(x)
        self.y = float(y)
        self.zoom = float(zoom)

    # ------------------------------------------------------------ 座標轉換

    def world_to_screen(self, wx: float, wy: float) -> tuple[float, float]:
        return ((wx - self.x) * self.zoom + self.screen_w / 2,
                (wy - self.y) * self.zoom + self.screen_h / 2)

    def screen_to_world(self, sx: float, sy: float) -> tuple[float, float]:
        return ((sx - self.screen_w / 2) / self.zoom + self.x,
                (sy - self.screen_h / 2) / self.zoom + self.y)

    def visible_rect(self) -> tuple[float, float, float, float]:
        """目前可見的世界範圍 (left, top, w, h)——繪製剔除用。"""
        w = self.screen_w / self.zoom
        h = self.screen_h / self.zoom
        return (self.x - w / 2, self.y - h / 2, w, h)

    # ------------------------------------------------------------ 便利工具

    def pan_zoom_targets(self, wx: float, wy: float,
                         zoom: float) -> dict[str, float]:
        """回傳「推近到某世界點」所需的三個 tween 終點值。
        場景層用法:for attr, end in cam.pan_zoom_targets(...).items():
                      tm.add(Tween(cam, attr, getattr(cam, attr), end, 0.7))"""
        if zoom <= 0:
            raise ValueError("zoom 必須為正")
        return {"x": float(wx), "y": float(wy), "zoom": float(zoom)}
