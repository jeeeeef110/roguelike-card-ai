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
  含 200 步隨機冒煙測試)
- [core/enemies.py] 巨鼠/毒蛛/石像兵意圖狀態機 + 被動(打斷、織網、疊甲),
  enemy_ai(state) 分派器直接插進 engine
- [tests/test_enemies.py] 規格數值、打斷閾值邊界(7/8 傷)、織網回合、石像兵循環、
  意圖機率分佈(2000 抽 ±5%)、三隻整場冒煙。全套 61/61 通過
- [ui/terminal_play.py] 終端手動對戰:python3 -m ui.terminal_play [敵人] [seed]
  → W1 驗收達成:能完整打一場

## 進行中
- 無(W1 完成)

## 待辦(依優先序)
1. agents/rule_based.py:規則式代理(W2:優先擋致死、再最大化即時輸出)
2. sim/ 模擬器雛形(W2:headless 跑 N 場、輸出勝率)

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
- 2026-07-07(Jeff 拍板):巨鼠蓄力被打斷 → 大招取消、改普通攻擊 6
  (打斷有報酬但不白賺一回合,疊甲硬吃路線保有競爭力)。
  打斷計傷窗口 = 蓄力宣告到下次宣告,以 HP 差計——毒 tick 也能打斷
- 2026-07-07:毒蛛織網固定在回合數 3 的倍數(可預測 → 玩家能提前規劃,
  符合「干擾不讓玩家沒事做」);石像兵 +3 甲在宣告意圖時生效
- 2026-07-07(v2.3,Jeff 首次試玩後拍板):玩家 HP=50、攻擊卡每回合上限 3 張、
  新增第 26 張卡「破限」(1 費技能・稀有,本回合解除上限)。
  修改了 v2.2 §3.1「出牌不限張數」定案,已在設計文件加 v2.3 修正區塊。
  ★報告素材:試玩 → 發現數值失衡 → 改規則並新增 payoff 卡的迭代循環

## 已知問題
- 無
