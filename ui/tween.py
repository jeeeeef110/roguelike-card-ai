"""ui/tween.py — 補間(tween)系統(藍圖 U1)

「一切皆緩動」設計語言的引擎:任何屬性變化都經由 Tween 平滑推進。
純數學、零依賴(不 import pygame)——可完整單元測試,也因此
未來換渲染後端(Pygbag/其他)這一層完全不用動。

用法:
    tm = TweenManager()
    tm.add(Tween(card, "y", 600, 480, 0.3, ease_out_cubic,
                 on_done=lambda: print("落定")))
    每幀:tm.update(dt)   # dt 秒
規則:
- 同一物件的同一屬性,新 tween 會取代舊的(後蓋前),避免互相拉扯
- delay 期間不動屬性;時間走完必精確落在 end(浮點誤差不外漏)
"""
from __future__ import annotations

from typing import Callable


# ------------------------------------------------------------------ easing
# 皆為 f: [0,1] -> [0,1],f(0)=0、f(1)=1


def linear(t: float) -> float:
    return t


def ease_out_cubic(t: float) -> float:
    u = 1.0 - t
    return 1.0 - u * u * u


def ease_in_out(t: float) -> float:
    return 3 * t * t - 2 * t * t * t  # smoothstep


def ease_out_back(t: float, s: float = 1.70158) -> float:
    """過衝回彈(意圖彈入、卡牌落定用)。t=1 精確回到 1。"""
    u = t - 1.0
    return 1.0 + u * u * ((s + 1) * u + s)


EASINGS = {"linear": linear, "ease_out_cubic": ease_out_cubic,
           "ease_in_out": ease_in_out, "ease_out_back": ease_out_back}


# ------------------------------------------------------------------ tween


class Tween:
    """把 obj.attr 從 start 平滑推到 end,歷時 duration 秒。"""

    __slots__ = ("obj", "attr", "start", "end", "duration", "easing",
                 "delay", "on_done", "elapsed", "done")

    def __init__(self, obj, attr: str, start: float, end: float,
                 duration: float, easing: Callable[[float], float] = ease_out_cubic,
                 delay: float = 0.0, on_done: Callable[[], None] | None = None):
        if duration <= 0:
            raise ValueError("duration 必須 > 0")
        self.obj = obj
        self.attr = attr
        self.start = float(start)
        self.end = float(end)
        self.duration = float(duration)
        self.easing = easing
        self.delay = float(delay)
        self.on_done = on_done
        self.elapsed = 0.0
        self.done = False

    def update(self, dt: float) -> None:
        if self.done:
            return
        self.elapsed += dt
        t_active = self.elapsed - self.delay
        if t_active < 0:
            return                      # 還在 delay,屬性不動
        if t_active >= self.duration:
            setattr(self.obj, self.attr, self.end)   # 精確落點
            self.done = True
            if self.on_done is not None:
                self.on_done()
            return
        k = self.easing(t_active / self.duration)
        setattr(self.obj, self.attr, self.start + (self.end - self.start) * k)


class TweenManager:
    """持有並推進所有進行中的 tween;同物件同屬性後蓋前。"""

    def __init__(self):
        self._tweens: list[Tween] = []

    def add(self, tw: Tween) -> Tween:
        self._tweens = [t for t in self._tweens
                        if not (t.obj is tw.obj and t.attr == tw.attr)]
        self._tweens.append(tw)
        return tw

    def update(self, dt: float) -> None:
        for t in self._tweens:
            t.update(dt)
        self._tweens = [t for t in self._tweens if not t.done]

    @property
    def active_count(self) -> int:
        return len(self._tweens)

    def clear(self) -> None:
        self._tweens.clear()
