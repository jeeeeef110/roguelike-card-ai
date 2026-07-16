"""ui/scenes.py — 場景管理與導演(藍圖 A2.3)

Director 持有場景堆疊、TweenManager 與 Camera(camera.py 的既有實作)。
場景切換不硬切(A1「一切皆緩動」):
- "fade":先淡入底色遮罩、中點換場景、再淡出(0.5s)
- "pan" :新舊場景各畫到緩衝面,水平滑動交接(0.7s;pop 反向)
- None  :直接切(開場第一個場景、測試用)

轉場期間輸入事件不轉發(避免半途點擊打進舊場景)。
場景只呼叫 core 公開 API,UI 內不得出現任何遊戲規則(鐵律)。
"""
from __future__ import annotations

import pygame

from ui.camera import Camera
from ui.tween import Tween, TweenManager, ease_in_out

BG = (5, 10, 20)        # 底色 #050A14(A1)
FADE_DURATION = 0.5
PAN_DURATION = 0.7


class Scene:
    """場景基類。director 由 Director 在切換時注入。"""

    director: "Director | None" = None

    def on_enter(self) -> None:
        """成為當前場景時呼叫(pop 露出的舊場景也會再次觸發)。"""

    def on_exit(self) -> None:
        """被 replace/pop 移出堆疊時呼叫(被 push 蓋住不算離場)。"""

    def handle(self, event) -> None:
        pass

    def update(self, dt: float) -> None:
        pass

    def draw(self, surface: pygame.Surface) -> None:
        pass


class _Transition:
    __slots__ = ("mode", "action", "old", "new", "direction", "t", "swapped")

    def __init__(self, mode: str, action: str, old: Scene, new: Scene,
                 direction: int):
        self.mode = mode          # "fade" | "pan"
        self.action = action      # "push" | "replace" | "pop"
        self.old = old
        self.new = new            # pop 時 = 被露出的下層場景
        self.direction = direction
        self.t = 0.0              # 進度 0→1,由 Tween 驅動
        self.swapped = False      # 堆疊是否已完成交接


class Director:
    """場景導演:堆疊管理 + 轉場 + 共用 TweenManager / Camera。

    主迴圈每幀:handle(event)* → update(dt) → draw(screen)。
    """

    def __init__(self, screen_w: int, screen_h: int):
        self.screen_w = screen_w
        self.screen_h = screen_h
        self.tweens = TweenManager()
        self.camera = Camera(screen_w, screen_h)
        self._stack: list[Scene] = []
        self._transition: _Transition | None = None
        self._overlay: pygame.Surface | None = None   # fade 遮罩(懶建)
        self._pan_buf: pygame.Surface | None = None   # pan 緩衝面(懶建)

    # ------------------------------------------------------------ 查詢

    @property
    def scene(self) -> Scene | None:
        return self._stack[-1] if self._stack else None

    @property
    def transitioning(self) -> bool:
        return self._transition is not None

    @property
    def depth(self) -> int:
        return len(self._stack)

    # ------------------------------------------------------------ 切換

    def push(self, scene: Scene, transition: str | None = "fade") -> None:
        self._start("push", scene, transition, direction=1)

    def replace(self, scene: Scene, transition: str | None = "fade") -> None:
        self._start("replace", scene, transition, direction=1)

    def pop(self, transition: str | None = "fade") -> None:
        if len(self._stack) < 2:
            raise ValueError("pop 需要堆疊至少 2 個場景")
        self._start("pop", self._stack[-2], transition, direction=-1)

    def _start(self, action: str, scene: Scene, transition: str | None,
               direction: int) -> None:
        if transition not in (None, "fade", "pan"):
            raise ValueError(f"未知轉場:{transition!r}")
        if self._transition is not None:      # 前一轉場立即結清,不排隊
            self._end(self._transition)
        scene.director = self
        old = self.scene
        if old is None or transition is None:
            self._commit(action, scene)
            return
        tr = _Transition(transition, action, old, scene, direction)
        self._transition = tr
        dur = FADE_DURATION if transition == "fade" else PAN_DURATION
        self.tweens.add(Tween(tr, "t", 0.0, 1.0, dur, ease_in_out,
                              on_done=lambda: self._end(tr)))

    def _commit(self, action: str, scene: Scene) -> None:
        """實際改動堆疊(fade 在中點、pan 在終點呼叫)。"""
        if action == "replace" and self._stack:
            self._stack.pop().on_exit()
        elif action == "pop":
            self._stack.pop().on_exit()
            self.scene.on_enter()             # 露出的舊場景重新進場
            return
        self._stack.append(scene)
        scene.on_enter()

    def _end(self, tr: _Transition) -> None:
        if self._transition is not tr:        # 已被 _start 提前結清
            return
        if not tr.swapped:
            tr.swapped = True
            self._commit(tr.action, tr.new)
        self._transition = None

    # ------------------------------------------------------------ 每幀

    def handle(self, event) -> None:
        if self._transition is None and self.scene is not None:
            self.scene.handle(event)

    def update(self, dt: float) -> None:
        self.tweens.update(dt)                # 可能在此觸發 _end
        tr = self._transition
        if tr is not None:
            if tr.mode == "fade" and not tr.swapped and tr.t >= 0.5:
                tr.swapped = True             # fade 中點:畫面全暗時換場景
                self._commit(tr.action, tr.new)
            tr.new.update(dt)                 # 進場者的待機動畫先跑起來
            if tr.mode == "pan":
                tr.old.update(dt)             # pan 全程雙方可見
        elif self.scene is not None:
            self.scene.update(dt)

    def draw(self, surface: pygame.Surface) -> None:
        tr = self._transition
        if tr is None:
            if self.scene is not None:
                self.scene.draw(surface)
            return
        if tr.mode == "fade":
            (tr.new if tr.swapped else tr.old).draw(surface)
            k = tr.t * 2 if tr.t < 0.5 else (1.0 - tr.t) * 2
            overlay = self._get_overlay()
            overlay.set_alpha(round(255 * max(0.0, min(1.0, k))))
            surface.blit(overlay, (0, 0))
        else:                                 # pan:雙場景滑動交接
            off = round(tr.t * self.screen_w) * tr.direction
            buf = self._get_pan_buf()
            buf.fill(BG)
            tr.old.draw(buf)
            surface.blit(buf, (-off, 0))
            buf.fill(BG)
            tr.new.draw(buf)
            surface.blit(buf, (self.screen_w * tr.direction - off, 0))

    # ------------------------------------------------------------ 懶建面

    def _get_overlay(self) -> pygame.Surface:
        if self._overlay is None:
            self._overlay = pygame.Surface((self.screen_w, self.screen_h))
            self._overlay.fill(BG)
        return self._overlay

    def _get_pan_buf(self) -> pygame.Surface:
        if self._pan_buf is None:
            self._pan_buf = pygame.Surface((self.screen_w, self.screen_h))
        return self._pan_buf
