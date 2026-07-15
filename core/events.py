"""core/events.py — 問號事件(v2.2 §5.2,M2)

三個事件,每個的核心問題:「我要不要正式轉流派?」
| 鐵匠   | 永久將一張卡費用 -1(最低 0)/ 離開 |
| 毒藥商 | 全部毒卡中毒值 +1 但失去一張非毒攻擊卡 / 獲得一張毒刃 / 離開 |
| 老戰士 | 移除一張防禦,換一張隨機攻擊卡 / 離開 |

設計:
- 事件是「對牌組(list[card_id])的純函式」:吃舊牌組回傳新牌組,
  不改輸入(冒險層之後好做 undo/重播,測試也乾淨)。
- 「升級卡」不修改共享的 Card 定義(那是全域不可變資料),而是
  衍生新 id 註冊進 UPGRADES 覆蓋表:鍛造版 = `id+"_s"`(cost-1)、
  淬毒版 = `id+"_p"`(apply_poison+1)。牌組換 id 就完成升級——
  「效果=資料」的延伸:升級=資料替換,引擎零改動(get_card 查覆蓋表)。
- 隨機性(老戰士抽卡)注入 Random;選擇類參數(升哪張、棄哪張)
  由呼叫端(UI/代理)決定,事件函式只驗證合法性。
"""
from __future__ import annotations

from random import Random

from core.cards import CARDS, RARITY_WEIGHTS, UPGRADES, get_card
from core.models import Card

EVENT_IDS = ("blacksmith", "poison_merchant", "old_warrior")


# ------------------------------------------------------------- 升級卡衍生


def _smith_id(card_id: str) -> str:
    base = get_card(card_id)
    if base.cost <= 0:
        raise ValueError(f"{card_id} 費用已是 0,不能再鍛造")
    new_id = card_id + "_s"
    if new_id not in UPGRADES:
        UPGRADES[new_id] = Card(new_id, base.name + "+", base.cost - 1,
                                base.kind, base.rarity, base.effects)
    return new_id


def _poison_upgrade_id(card_id: str) -> str:
    base = get_card(card_id)
    effects = tuple(("apply_poison", e[1] + 1) if e[0] == "apply_poison" else e
                    for e in base.effects)
    if effects == base.effects:
        raise ValueError(f"{card_id} 不是毒卡")
    new_id = card_id + "_p"
    if new_id not in UPGRADES:
        UPGRADES[new_id] = Card(new_id, base.name + "毒", base.cost,
                                base.kind, base.rarity, effects)
    return new_id


def is_poison_card(card_id: str) -> bool:
    return any(e[0] == "apply_poison" for e in get_card(card_id).effects)


# ------------------------------------------------------------- 三個事件


def blacksmith_upgrade(deck: list[str], position: int) -> list[str]:
    """鐵匠:把 deck[position] 那張換成鍛造版(費用 -1)。"""
    new = list(deck)
    new[position] = _smith_id(new[position])
    return new


def poison_merchant_commit(deck: list[str], discard_position: int) -> list[str]:
    """毒藥商選項 A:全部毒卡淬毒(+1),代價:失去一張非毒攻擊卡。"""
    victim = deck[discard_position]
    if get_card(victim).kind != "attack" or is_poison_card(victim):
        raise ValueError(f"代價必須是非毒攻擊卡,{victim} 不合法")
    new = [(_poison_upgrade_id(c) if is_poison_card(c) else c)
           for c in deck]
    del new[discard_position]
    return new


def poison_merchant_sample(deck: list[str]) -> list[str]:
    """毒藥商選項 B:試用品——獲得一張毒刃。"""
    return list(deck) + ["poison_blade"]


def old_warrior_trade(deck: list[str], rng: Random) -> tuple[list[str], str]:
    """老戰士:移除一張防禦,換一張隨機攻擊卡(稀有度加權,起始卡不入池)。
    回傳 (新牌組, 得到的卡)。牌組沒有防禦時報錯(UI 端應先擋掉選項)。"""
    if "defend" not in deck:
        raise ValueError("牌組沒有防禦,不能交易")
    pool: list[str] = []
    for cid, card in CARDS.items():
        if card.kind == "attack" and card.rarity in RARITY_WEIGHTS:
            pool.extend([cid] * RARITY_WEIGHTS[card.rarity])
    gained = rng.choice(pool)
    new = list(deck)
    new.remove("defend")
    new.append(gained)
    return new, gained
