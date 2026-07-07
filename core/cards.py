"""core/cards.py — 27 張卡的資料定義(v2.2 §3.3 定稿 + v2.3 平衡修正)

本檔只有「資料」:每張卡是一個不可變的 Card(NamedTuple),effects 由
engine.py 解讀執行。新增卡=新增一筆資料,不改引擎(效果=資料 + 事件鉤子)。

效果指令集(engine W1 需實作的 opcodes):

  對敵傷害(每個 damage 類 opcode = 一次獨立攻擊,力量逐次加成、易傷結算在 engine)
  ("damage", n)                        對敵造成 n 點傷害
  ("damage_bonus_vs_vulnerable", n, b) 傷害 n;敵有易傷再 +b(順勢斬,單次攻擊)
  ("damage_per_vulnerable", n, b)      傷害 n + 敵每層易傷 b(制裁,單次攻擊)
  ("damage_per_attack_played", n, b)   傷害 n + 本回合每張已出攻擊卡 b(撕裂)
  ("damage_equal_block",)              傷害 = 玩家目前護甲值(反甲擊)
  ("damage_shatter", n)                傷害 n;敵有護甲則全移除並追加等量傷害(破甲)
  ("detonate_poison", m)               造成敵中毒層數 ×m 傷害,清空中毒(引爆)

  防禦與狀態
  ("block", n)                         獲得護甲 n
  ("retain_block",)                    本回合結束護甲不歸零(堅守)
  ("lift_attack_limit",)               本回合解除攻擊牌張數上限(破限,v2.3)
  ("apply_vulnerable", n)              敵易傷 +n
  ("apply_poison", n)                  敵中毒 +n
  ("apply_weak", n)                    敵虛弱 +n:攻擊傷害 -25% 取整(痺擊,v2.3)
  ("gain_strength", n)                 力量 +n(該場戰鬥永久)

  資源
  ("draw", n)                          抽 n 張
  ("gain_energy", n)                   本回合能量 +n
  ("next_turn_energy", d)              下回合開始能量修正 d(蓄勢 +2 / 透支 -1)
  ("heal", n)                          回復 n HP(不超過 max_hp)
  ("self_damage", n)                   自身直接扣 n HP(不經護甲——代價自選,背水)

  需玩家選擇的效果(engine 出牌時需帶選擇參數)
  ("discard_choose", n)                從手牌選 n 張棄掉(充能)
  ("retrieve_choose", n)               從棄牌堆選 n 張置入手牌(回收)

kind 分類規則(定案):會對敵造成傷害的卡一律 "attack",其餘 "skill"。
attack 標記影響:毒蛛織網的費用 +1、撕裂的出牌計數。
"""
from core.models import Card

# v2.2 §3.3:25 張,依表格編號排列
_CARD_DEFS: tuple[Card, ...] = (
    # 1 起始:基礎輸出
    Card("strike", "打擊", 1, "attack", "starter",
         (("damage", 6),)),
    # 2 起始:基礎防禦
    Card("defend", "防禦", 1, "skill", "starter",
         (("block", 5),)),
    # 3 易傷 engine
    Card("bash", "重擊", 2, "attack", "common",
         (("damage", 8), ("apply_vulnerable", 2))),
    # 4 易傷 piece:傷害 4,敵有易傷再 +4(單次攻擊,非兩發)
    Card("follow_slash", "順勢斬", 1, "attack", "common",
         (("damage_bonus_vs_vulnerable", 4, 4),)),
    # 5 毒 engine
    Card("poison_blade", "毒刃", 1, "attack", "common",
         (("damage", 3), ("apply_poison", 2))),
    # 6 毒 engine:本回合零輸出
    Card("deadly_poison", "猛毒", 1, "skill", "common",
         (("apply_poison", 4),)),
    # 7 反甲 engine
    Card("iron_wall", "鐵壁", 2, "skill", "common",
         (("block", 11),)),
    # 8 反甲 payoff:先疊甲再打
    Card("armor_strike", "反甲擊", 1, "attack", "rare",
         (("damage_equal_block",),)),
    # 9 力量 engine:延遲收益
    Card("empower", "蓄力", 1, "skill", "common",
         (("gain_strength", 2),)),
    # 10 起始:潤滑
    Card("rampage", "狂暴", 0, "attack", "starter",
         (("damage", 3), ("draw", 1))),
    # 11 手牌引擎
    Card("tactics", "兵法", 1, "skill", "rare",
         (("draw", 2),)),
    # 12 資源交換:棄 1 換 1 能量
    Card("recharge", "充能", 0, "skill", "common",
         (("discard_choose", 1), ("gain_energy", 1))),
    # 13 力量 piece:3 傷 ×2 次(兩次獨立攻擊,力量各加成)
    Card("double_strike", "連擊", 1, "attack", "common",
         (("damage", 3), ("damage", 3))),
    # 14 針對卡(石像兵剋星)
    Card("armor_break", "破甲", 1, "attack", "common",
         (("damage_shatter", 5),)),
    # 15 自選代價爆發:血量換輸出
    Card("last_stand", "背水", 2, "attack", "common",
         (("damage", 14), ("self_damage", 3))),
    # 16 毒 payoff:轉換清空,自帶煞車
    Card("detonate", "引爆", 2, "attack", "rare",
         (("detonate_poison", 2),)),
    # 17 力量 payoff:2 傷 ×4 次(四次獨立攻擊,力量各加成)
    Card("flurry", "亂舞", 2, "attack", "rare",
         (("damage", 2), ("damage", 2), ("damage", 2), ("damage", 2))),
    # 18 反甲 engine:跨回合疊甲
    Card("entrench", "堅守", 2, "skill", "common",
         (("block", 8), ("retain_block",))),
    # 19 反甲 piece
    Card("shield_bash", "盾擊", 1, "attack", "common",
         (("block", 3), ("damage", 3))),
    # 20 延遲收益:這回合虧 1 費,下回合爆發
    Card("momentum", "蓄勢", 1, "skill", "common",
         (("next_turn_energy", 2),)),
    # 21 自選代價:延遲成本(取代原賭命一擊)
    Card("overdraw", "透支", 1, "attack", "common",
         (("damage", 12), ("next_turn_energy", -1))),
    # 22 手牌管理:牌庫知識
    Card("salvage", "回收", 1, "skill", "rare",
         (("retrieve_choose", 1),)),
    # 23 條件收尾(取代原終結):易傷 build 的 payoff
    Card("judgment", "制裁", 2, "attack", "rare",
         (("damage_per_vulnerable", 6, 4),)),
    # 24 順序敏感:留到最後一張出
    Card("rend", "撕裂", 0, "attack", "common",
         (("damage_per_attack_played", 2, 2),)),
    # 25 續戰:搶血 vs 換血
    Card("bloodthirst", "飲血", 2, "attack", "common",
         (("damage", 8), ("heal", 3))),
    # 26 攻擊上限 payoff(v2.3 新增,Jeff 拍板):爆發回合前先付 1 費一張牌
    Card("limit_break", "破限", 1, "skill", "rare",
         (("lift_attack_limit",),)),
    # 27 防禦向攻擊(v2.3 新增,Jeff 拍板):用輸出換減傷,對抗大招回合
    Card("numbing_strike", "痺擊", 1, "attack", "common",
         (("damage", 4), ("apply_weak", 2))),
)

# 全遊戲唯一的卡牌註冊表:card_id → Card(共享、不可變)
CARDS: dict[str, Card] = {c.card_id: c for c in _CARD_DEFS}

# v2.2 §3.3:起始牌組 打擊 ×5、防禦 ×4、狂暴 ×1
STARTING_DECK: list[str] = ["strike"] * 5 + ["defend"] * 4 + ["rampage"]

# v2.3 平衡修正:玩家起始 HP(遠低於 Boss 90,一般戰失誤 2-3 次即有壓力)
PLAYER_HP: int = 50

# v2.2 §3.5:獎勵抽卡權重(起始卡不進獎勵池)
RARITY_WEIGHTS: dict[str, int] = {"common": 3, "rare": 1}


def get_card(card_id: str) -> Card:
    """以 card_id 取得共享的卡牌定義。未知 id 直接報錯(在邊界驗證輸入)。"""
    try:
        return CARDS[card_id]
    except KeyError:
        raise KeyError(f"未知的 card_id:{card_id!r}(合法值見 core/cards.py CARDS)") from None
