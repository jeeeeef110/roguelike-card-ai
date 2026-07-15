"""core/meta.py — 局外養成(第三階段核心,設計討論定案 2026-07-08)

設計鐵律:**養成解鎖的是「變化」,不是「變強」**——永久數值加成會污染
平衡數據(模擬器測的「玩家強度」變浮動),所以收集軸只動卡池組成。

收集軸主循環(Jeff 拍板):
    擊殺 Boss → 從「尚未解鎖的稀有卡」抽 3 張 → 三選一永久解鎖
    → 之後所有冒險的獎勵/菁英/商店卡池都包含它
起始:7 張稀有卡解鎖 3 張(依 meta seed 決定,每個玩家的起點不同——
      第一輪就有 build 可玩,但不是全部),其餘 4 張靠 Boss 擊殺解鎖。
普通卡全數常駐(卡池太小會讓三選一縮水)。

存檔:單一 JSON,含版本號(未來格式遷移用)。零外部依賴。
"""
from __future__ import annotations

import json
from pathlib import Path
from random import Random

from core.cards import CARDS

SAVE_VERSION = 1
STARTING_RARE_COUNT = 3


def _all_rares() -> list[str]:
    return sorted(c.card_id for c in CARDS.values() if c.rarity == "rare")


class MetaState:
    """局外進度。與 RunState(單輪)分離:一個是存摺,一個是這趟旅程。"""

    __slots__ = ("version", "unlocked_rares", "shards", "ascension_best",
                 "runs", "wins")

    def __init__(self, meta_seed: int = 0):
        self.version = SAVE_VERSION
        rng = Random(meta_seed)
        self.unlocked_rares: list[str] = sorted(
            rng.sample(_all_rares(), STARTING_RARE_COUNT))
        self.shards = 0
        self.ascension_best = 0   # 已通關的最高進階(可開 0..best+1)
        self.runs = 0
        self.wins = 0

    # ------------------------------------------------------------ 收集軸

    def locked_rares(self) -> list[str]:
        return [c for c in _all_rares() if c not in self.unlocked_rares]

    def boss_unlock_choices(self, rng: Random) -> list[str]:
        """Boss 擊殺獎勵:從未解鎖稀有卡抽最多 3 張供三選一。
        全解鎖後回傳空列表(UI 可改發碎片)。"""
        pool = self.locked_rares()
        return sorted(rng.sample(pool, min(3, len(pool))))

    def unlock_rare(self, card_id: str) -> None:
        if card_id not in self.locked_rares():
            raise ValueError(f"{card_id!r} 不在可解鎖清單")
        self.unlocked_rares.append(card_id)
        self.unlocked_rares.sort()

    # ------------------------------------------------------------ 結算

    def settle_run(self, floors: int, elites: int, boss_killed: bool,
                   ascension: int) -> int:
        """一輪結束的結算(勝敗皆有——「雖敗猶得」是再開一局的動力)。
        回傳本輪獲得碎片。碎片用途(解鎖角色等)屬第三階段後續。"""
        gained = floors * 2 + elites * 5 + (20 if boss_killed else 0)
        self.shards += gained
        self.runs += 1
        if boss_killed:
            self.wins += 1
            self.ascension_best = max(self.ascension_best, ascension + 1)
        return gained

    # ------------------------------------------------------------ 存檔

    def save(self, path: str | Path) -> None:
        data = {k: getattr(self, k) for k in self.__slots__}
        Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=1),
                              encoding="utf-8")

    @classmethod
    def load(cls, path: str | Path) -> "MetaState":
        data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data.get("version") != SAVE_VERSION:
            raise ValueError(f"存檔版本 {data.get('version')} 不支援"
                             f"(目前 {SAVE_VERSION};未來版本在此做遷移)")
        m = cls.__new__(cls)
        for k in cls.__slots__:
            setattr(m, k, data[k])
        # 防呆:存檔裡的卡 id 必須仍存在(卡池改版後的孤兒 id 直接剔除)
        m.unlocked_rares = [c for c in m.unlocked_rares if c in CARDS]
        return m
