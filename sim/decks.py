"""sim/decks.py — 5 條 build 牌組(v2.2 §3.4 + v2.3 卡池)

模擬「一輪冒險走到中後期」的牌組:起始 10 張為底,刪 2-3 張基礎卡、
加 5-6 張路線卡(含 1-2 張 build 定義稀有卡)。張數統一 13,
控制「牌組大小」這個混淆變數,差異全歸因於路線構成。

用途:三版代理 × 5 build 勝率矩陣(design.md §6.2 承諾的核心圖表)。
命題:MCTS 的長程優勢要在長線牌組(毒/力量)才顯現——
起始牌組的對照(PROGRESS 三版對照第一批)顯示它在短線戰輸貪婪。
"""

_BASE = ["strike"] * 4 + ["defend"] * 3 + ["rampage"]  # 起始 10 張刪 1 打 1 防

BUILD_DECKS: dict[str, list[str]] = {
    # 毒流:疊毒 → 鐵壁拖 → 引爆收(MCTS 主場命題:引爆時機)
    "poison": _BASE + ["poison_blade", "poison_blade", "deadly_poison",
                       "iron_wall", "detonate"],
    # 力量連擊流:蓄力 → 連擊/撕裂 → 亂舞收(延遲收益)
    "strength": _BASE + ["empower", "empower", "double_strike",
                         "rend", "flurry"],
    # 反甲流:鐵壁/堅守疊甲 → 反甲擊轉傷(順序敏感)
    "block": _BASE + ["iron_wall", "entrench", "shield_bash",
                      "shield_bash", "armor_strike"],
    # 易傷爆發流:重擊上易傷 → 順勢斬 → 制裁收(條件收尾)
    "vulnerable": _BASE + ["bash", "bash", "follow_slash",
                           "follow_slash", "judgment"],
    # 節奏流:蓄勢/充能換資源 → 透支/背水爆發(資源交換)
    "tempo": _BASE + ["momentum", "recharge", "overdraw",
                      "last_stand", "tactics"],
}
