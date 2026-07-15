"""tests/conftest.py — pygame 生命週期統一管理

pygame.quit() 只能在整個測試 session 結束時呼叫一次:
UI 模組(ui.text/ui.glow)快取的 Font 與 Surface 綁定當時的 pygame
執行期,若某個測試模組先 quit、下一個模組再 init,快取物件變成
懸空指標,一觸即 segfault。因此各測試檔的 fixture 只 init 不 quit
(init 是冪等的),quit 收斂到這裡。
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _pygame_session():
    yield
    pygame.quit()
