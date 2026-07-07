# PROGRESS
更新日期:2026-07-07

## 已完成
- [repo] 骨架建立:core/agents/ui/sim/tests 五層
- [core/models.py] Card / PlayerState / EnemyState / GameState 資料結構,含手寫 clone()。測試 8/8 通過
- [tests/test_models.py] clone 獨立性、RNG 三模式、效能基準(門檻 10 萬次/秒)
- [core/cards.py] 25 張卡資料定義(照 v2.2 §3.3)+ CARDS 註冊表 + STARTING_DECK +
  RARITY_WEIGHTS。效果指令集(opcodes)完整列在檔頭 docstring,供 engine.py 實作依據
- [tests/test_cards.py] 25 張/id 一致、起始牌組、稀有度分佈、effects 結構、
  kind 分類規則、關鍵卡逐格抽查
- [core/engine.py] 規則引擎:傷害管線(力量→易傷×1.5 取整→護甲)、全部 opcodes、
  回合流程、敵人意圖執行、代理接口 legal_actions/apply_action(enemy_ai 注入式)
- [tests/test_engine.py] 33 個規則測試(傷害管線/回合資源/特殊卡/接口與勝負,
  含 200 步隨機冒煙測試)。全套 48/48 通過

## 進行中
- 無(本階段完整結束)

## 待辦(依優先序)
1. core/enemies.py:三隻敵人意圖狀態機 + 被動特性(engine 的 enemy_ai 接口已留好)
2. 終端手動對戰迴圈(驗收 W1:能打完一整場)

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
- 2026-07-07(Jeff 拍板):中毒不吃易傷 ×1.5——毒流與易傷流獨立平衡,
  避免必選組合;中毒在玩家回合開始結算雙方(回饋直觀、引爆基準單純)
- 2026-07-07:引爆定為純轉換——不吃力量、不吃易傷、可被護甲抵擋。
  取捨:毒 tick 穿甲、引爆不穿,保留「持續 vs 爆發」的決策張力
- 2026-07-07:engine 細部結算——破甲先打 5(過管線)再移除剩餘護甲追加等量直傷;
  撕裂不計自己(attacks_played 結算後才 +1);背水自傷不經護甲、可陣亡;
  織網歸零在敵人行動前,故敵人本回合織網 → 效果自然落在玩家下回合
- 2026-07-07:敵人的「腦」不進 engine——enemy_ai(state)->intent 由呼叫端注入,
  enemies.py 只要提供各敵人的意圖函式,engine 不用改

## 已知問題
- 無
