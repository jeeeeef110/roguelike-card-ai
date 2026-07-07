# PROGRESS
更新日期:2026-07-07

## 已完成
- [repo] 骨架建立:core/agents/ui/sim/tests 五層
- [core/models.py] Card / PlayerState / EnemyState / GameState 資料結構,含手寫 clone()。測試 8/8 通過
- [tests/test_models.py] clone 獨立性、RNG 三模式、效能基準(門檻 10 萬次/秒)
- [core/cards.py] 25 張卡資料定義(照 v2.2 §3.3)+ CARDS 註冊表 + STARTING_DECK +
  RARITY_WEIGHTS。效果指令集(opcodes)完整列在檔頭 docstring,供 engine.py 實作依據
- [tests/test_cards.py] 25 張/id 一致、起始牌組、稀有度分佈、effects 結構、
  kind 分類規則、關鍵卡逐格抽查。測試 15/15 通過(含 models)

## 進行中
- 無(本階段完整結束)

## 待辦(依優先序)
1. core/engine.py:出牌結算、效果解讀、回合流程(W1 主體;opcodes 見 cards.py 檔頭)
2. core/enemies.py:三隻敵人意圖狀態機 + 被動特性
3. 終端手動對戰迴圈(驗收 W1:能打完一整場)

## 重要決策紀錄
- 2026-07-07:GameState.clone() 的 RNG 預設為 share 模式(共用 Random 物件)。
  理由:效能測量發現 Mersenne Twister 狀態複製(625-int)是瓶頸——
  完整複製 RNG 時 clone 僅 4.2 萬次/秒,繞開後達 113 萬次/秒(快 27 倍)。
  MCTS rollout 複本用完即丟不需精確 RNG;需要重播時用 rng="replay",
  determinization 用 rng=<seed>。★報告素材:效能剖析 → 定位瓶頸 → API 設計取捨
- 2026-07-07:狀態層只存 card_id 字串,Card 定義為不可變共享資料(NamedTuple)。
  理由:複製狀態時只複製字串列表,不複製卡牌物件
- 2026-07-07:kind 分類規則定案——會對敵造成傷害的卡一律 "attack"(16 張),
  其餘 "skill"(9 張)。影響:織網費用 +1、撕裂計數。含 v2.2 未明說的邊界案例:
  盾擊、引爆、透支、飲血都算 attack(有測試 test_kind_rule_damage_means_attack 鎖定)
- 2026-07-07:多段攻擊(連擊 3×2、亂舞 2×4)表示為多個獨立 ("damage", n) 效果,
  每發力量各自加成(v2.2 §3.2「逐次攻擊各加成」);順勢斬/制裁/撕裂是單次攻擊,
  用專屬 opcode 帶條件加成參數。背水 self_damage 定案為直接扣 HP、不經護甲
- 2026-07-07:充能/回收需玩家選擇 → opcode 帶 _choose 後綴
  (discard_choose / retrieve_choose),engine 出牌介面需支援附帶選擇參數

## 已知問題
- 無
