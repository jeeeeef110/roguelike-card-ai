"""core/potions.py — 藥水(消耗品)系統

《殺戮尖塔》驗證過的樂趣公式:藥水是「口袋裡的後悔藥」——
平常捨不得用,危急關頭砸下去翻盤,用掉的瞬間就是遊戲的記憶點。

規則(定案):
- 攜帶上限 3 瓶;戰鬥中使用是**免費動作**(不耗能量、不計攻擊卡上限)
- 戰後 35% 掉落、商店固定販售一瓶(25 金)
- 效果直接複用卡牌的效果指令集——藥水 = 不進牌庫的一次性卡,引擎零新指令
- 掉落與商店進貨吃 RunState.rng(同 seed 同冒險)
"""
from __future__ import annotations

from typing import NamedTuple


class Potion(NamedTuple):
    potion_id: str
    name: str
    effects: tuple   # 與 Card.effects 同一套指令集


POTIONS: dict[str, Potion] = {p.potion_id: p for p in (
    Potion("fire_flask",    "火焰瓶",   (("damage", 10),)),
    Potion("healing_vial",  "治療藥水", (("heal", 12),)),
    Potion("strength_brew", "力量藥劑", (("gain_strength", 2),)),
    Potion("iron_draught",  "鐵壁藥水", (("block", 12),)),
    Potion("venom_vial",    "劇毒瓶",   (("apply_poison", 5),)),
)}

POTION_DROP_RATE = 0.35
POTION_PRICE = 25
MAX_POTIONS = 3


def get_potion(potion_id: str) -> Potion:
    try:
        return POTIONS[potion_id]
    except KeyError:
        raise KeyError(f"未知的 potion_id:{potion_id!r}"
                       f"(合法值:{sorted(POTIONS)})") from None
