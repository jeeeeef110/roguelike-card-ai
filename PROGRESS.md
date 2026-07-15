# PROGRESS
更新日期:2026-07-15(PC 恢復:U2–U4 完成含接線——地圖↔戰鬥完整循環可玩)

## 已完成
### 第一階段(core + 三版代理 + 模擬器)— 2026-07-07 完成
- [repo] core/agents/ui/sim/tests 五層;models/cards/engine/enemies + 全套測試
- [agents] random / rule_based / expectimax / mcts(細節見 git log 與舊版 PROGRESS)
- [ui/terminal_play] 終端手動對戰;[sim/runner] headless 模擬器
- [Boss] 腐化騎士網格搜尋調校,拉開代差(random 0 / rule 27.8 / mcts 89 / expectimax 98%)

### 沙盒衝刺(2026-07-08,手機遠端;電腦 7/14 前不可用)
- [agents/mcts.py] rollout policy 選項:random(預設,歷史基線)/ heuristic
  (ε-greedy 靜態評分,零複本試打;含狀態相依傷害:反甲擊看當下護甲、引爆看毒層)
- [sim/exp_mcts_tuning.py] 實驗 3:rollout × iterations 全格完成(見下)
- [sim/decks.py] 5 條 build 牌組(13 張制,控制牌組大小混淆變數)
- [sim/exp_build_matrix.py] 實驗 4:5 build × 3 代理 Boss 勝率矩陣(見下)
- [core/map_gen.py + tests] 分層 DAG 地圖生成:全約束 + 連通性,
  1000 seeds 性質測試(生成器與驗證器分開寫互相檢查)
- [core/events.py + tests] 三事件(鐵匠/毒藥商/老戰士)純函式;
  升級卡走 UPGRADES 覆蓋表(衍生 id,CARDS 基礎卡池不受污染,引擎零改動)
- [core/run.py + tests] 完整一輪冒險:地圖行走/戰鬥委派 hook/獎勵三選一/
  休息/商店/事件;經濟初始值(勝+25 金、稀有卡 65、刪卡 50、休息回 30%)
- [sim/make_charts.py] 產出 docs/charts/mcts_tuning.png、build_matrix.png
- [run_tests.py + tools_offline/] 無 pytest 環境的測試執行器(沙盒/離線用)
- 測試:121/121 全綠(map 7 + events 11 + run 9 新增)
- **M2 headless 部分完成:專案只剩 Pygame UI 需要電腦**

### 趣味性擴充(2026-07-08 第三波:參考殺戮尖塔的樂趣公式)
- [core/potions.py + engine] 藥水系統:5 種、上限 3 瓶、戰鬥中**免費動作**
  (不耗能量不計攻擊上限);效果複用卡牌指令集=不進牌庫的一次性卡,
  引擎只加一個動作型別。戰後 35% 掉落、商店販售(25 金)
- [core/run.py] 休息點改**二選一:回血 30% or 鍛造一張卡**(複用鐵匠的
  _smith_id)——類型核心抉擇「保命 vs 變強」,每個休息點都是一題
- 測試 142/142(新增 test_potions 11 項);冒煙測試同步更新
- 注意:battle_hook 負責把 run.potions 帶進戰鬥、戰後把剩餘寫回
  (tests/test_run._agent_battle 為範例,UI 接線時照做)

### 養成系統(2026-07-08 第四波,Jeff 拍板「Boss 三選一解鎖」)
- [core/meta.py + tests] 局外進度 MetaState:**擊殺 Boss → 未解鎖稀有卡
  抽 3 選 1 永久入池**(收集軸主循環);起始解鎖 3/7 張(依 meta seed,
  每個玩家起點不同);碎片結算(層×2+菁英×5+Boss+20,雖敗猶得);
  進階最高紀錄;JSON 存檔含版本號與孤兒 id 防呆
- [core/run.py] RunState 接受 unlocked_rares,獎勵/菁英/商店卡池過濾;
  小卡池防呆(不重複卡種 <3 時發多少算多少,不卡死)
- 設計鐵律(記入 design):養成解鎖「變化」不解鎖「變強」——
  永久數值加成會污染平衡數據,原 GDD 的「永久小幅加成」廢除
- 測試 152/152(新增 test_meta 10 項)
- 剩餘接線(UI 階段):結算畫面呼叫 settle_run、勝利畫面呈現
  boss_unlock_choices 三選一、開局讀 MetaState 傳 unlocked_rares 給 RunState

### 待拍板提案(不實作,需 Jeff 明確同意)
- **格子戰鬥 v2**(5×5 盤面、卡牌射程形狀、Boss 格上攻擊預告):完整規格與
  衝擊評估見 docs/UI視覺規格與格子戰鬥提案.md B 部。決策條件:現行版
  U1–U7 完成且備審材料齊(實際=2027 年 2–3 月後)。未拍板前禁止實作
- 「紋章」輕量遺物:每輪冒險最多 3 個被動(如「每回合第一張攻擊卡免費」
  「連鎖:單回合第 3 張攻擊卡起傷害+2」)。Balatro/殺戮尖塔的 build 樂趣
  核心來源;效果掛既有鉤子,估 2-3 天。若同意,列入 PC 恢復後排程

### 變化性擴充(2026-07-08 第二波)
- [core/enemies.py] 新敵人 ×2,各含謎題:吸血蝠(吸實際傷害,全擋=吸不到
  →反甲剋星)、狂戰士(每受擊力量+1,毒 tick 不計→反連擊、毒是解法);
  engine 加 attack_lifesteal 意圖 + 通用受擊計數器(pattern["hits_taken"])
- [core/map_gen.py] 菁英節點(第 4 層起,權重 1)、深度分池(2–4 層只出
  入門怪,5 層起全池)、層數參數化 generate_map(seed, n_layers=10..15)
- [core/run.py] 菁英戰:金 45 + 三選一全稀有(build 定義時刻);
  spawn_enemy 統一倍率(菁英 HP×1.35+力量1);進階等級 ascension
  (每級敵 HP+10%,通關解鎖下一級=重玩軸)
- 測試 132/132(新增 test_variety 11 項);新敵人平衡快照:起始牌組下
  三代理全 100% 勝(剩 HP 31–46,偏易)——謎題設計本來就是對 build 觸發,
  數值標待平衡

### UI 基座(2026-07-08 第五波:藍圖 U1 + U2 純數學部分)
- [ui/tween.py] 補間系統:4 種 easing、delay、on_done、同物件同屬性後蓋前、
  精確落點(浮點誤差不外漏)。零依賴,不 import pygame
- [ui/camera.py] 鏡頭:x/y/zoom 皆可被 tween 直接驅動;world↔screen 轉換、
  visible_rect 剔除、pan_zoom_targets 便利工具
- 測試 167/167(新增 test_ui_math 15 項:easing 端點性質、tween 行為全覆蓋、
  鏡頭往返精度、tween 驅動鏡頭整合)
- **U1 驗收門通過**;U2 剩餘(glow.py、scenes.py 繪製層)需 pygame → PC 首日:
  `pip install pygame`,寫 glow/scenes 時 tween 與 camera 直接可用

### UI U2 繪製層(2026-07-15,PC 恢復首日;pygame 2.6.1)
- [ui/glow.py] 發光渲染:同心多層遞增亮度烘焙成黑底 Surface,
  BLEND_RGB_ADD 整張 blit(黑=加零,光源疊加自然累加=bloom 視覺);
  圓與線段皆走快取(地圖邊靜態 → 位移量當 key 反覆命中);
  層數上限 4(A5 白爆守則)硬夾在 bake 端
- **A2.2 效能驗收門通過**:200 節點 + 220 邊滿載,dummy driver 軟體 blit
  實測 556 fps(門檻 55,約 9 倍餘裕);快取 186 張烘焙面
- 測試 177/177(新增 test_glow 10 項:快取同一性、層數上限、加法疊亮、
  光暈亮度梯度、出界安全、60fps 驗收)
- [ui/scenes.py] Scene 基類(on_enter/on_exit/handle/update/draw)+
  Director(場景堆疊、共用 TweenManager 與 Camera):fade 轉場
  (淡入底色遮罩→中點交接堆疊→淡出,0.5s)、pan 轉場(雙場景水平
  滑動交接,0.7s,pop 反向)、transition=None 直切;轉場期間輸入阻擋、
  進場者 update 先跑(待機動畫不等轉場結束);連續轉場=前一發立即結清
- **U2 驗收門通過**:空場景 fade/pan 連續切換 fps>55(dummy driver 實測遠超)
- 測試 190/190(新增 test_scenes 13 項:生命週期、中點交接語義、
  輸入阻擋、pan 雙場景可見性、pop 反向、60fps 驗收)
- 命名對照:規格 A2.3 的 Camera 即既有 ui/camera.py(U1 已完成),
  scenes.py 直接 import,不重複實作

### UI U3 MapScene(2026-07-15,同日)
- [ui/map_scene.py] 地圖場景色塊版(A3.1):分層 DAG 透視佈局(每層 x 間距
  壓縮 7%、y 遞減)、可走節點呼吸閃爍(亮度 0.6↔1.0/1.8s/錯相)、
  走過路徑亮中性光、待機 ±1px 漂浮;點擊 → 鏡頭推近(zoom 1.6/0.7s)→
  core 三段式結算 → 拉回;戰鬥由注入的 battle_hook 決定
- 效能設計:呼吸亮度 8 階量化 + 半徑步進 2 → glow 快取鍵有界
  (測試鎖定 <600 張);邊用普通線(glow_line 鍵含位移量,縮放會撐爆快取)
- U3 佔位(U4/U5 換掉):獎勵自動拿第一張、休息自動回血、商店/事件路過、
  節點用流派色色塊(icon U4 才上)
- [ui/demo_map.py] 互動 demo:`python3 -m ui.demo_map [seed]`,
  Pygbag 相容 async 主迴圈(A5:一開始就這樣寫)
- **U3 驗收門通過**:headless 模擬點擊完整走完一輪地圖到 Boss 勝利
  (test_full_walk_reaches_boss_and_victory);MapScene 繪製 >55fps
- 測試 198/198(新增 test_map_scene 8 項:透視佈局、呼吸範圍與錯相、
  點擊行走、busy 忽略輸入、完整走圖、快取有界、60fps)

### UI U4 BattleScene 主體(2026-07-15,同日)
- [ui/text.py] 文字快取渲染(A5 守則):key=(字串,字級,顏色,粗體),
  上限 512 條超過整批清空;SysFont 找思源黑體/蘋方,CJK 正常
- [ui/widgets.py] SmoothBar(「血條永不瞬降」:set() 下 300ms tween,
  護甲=條外藍描邊)+ FloatTextLayer(傷害數字上飄淡出;持有 Surface
  複本,動 alpha 不污染共享文字快取)
- [ui/battle_scene.py] 戰鬥場景色塊版(A3.2):規則零重複——合法性/
  費用/結算全問 engine(legal_actions/apply_action/card_cost),文案
  複用 terminal_play 的 intent_text/card_text(同一套翻譯兩個前端)。
  意圖 ease_out_back 彈入、出牌色塊卡飛向目標 0.25s(飛行中鎖輸入)、
  受擊閃白 2 幀、傷害/護甲飄字、hover 上浮 20px、不可出牌灰框、
  結算 overlay 點擊 → on_finish(win, hp_left)(U5 給 MapScene 接)
- [ui/demo_battle.py] 手動對戰 demo:`python3 -m ui.demo_battle [敵人] [seed]`
- **U4 驗收門通過**:規則式代理決策+UI 點擊路徑打贏巨鼠
  (test_full_battle_win_vs_giant_rat_via_ui_clicks);>55fps
- U4 佔位待補(記在待辦):藥水槽、MCTS 建議開關、Boss 二階段演出
  (暗化+鏡頭震)、_choose 卡的選擇面板(現自動選第一個合法對象)
- 測試 215/215(新增 test_ui_widgets 10 + test_battle_scene 7)

### UI U4 收尾:地圖↔戰鬥接線(2026-07-15,同日)
- [ui/map_scene.py] battle_hook=None(預設)時戰鬥節點推 BattleScene
  互動對戰:spawn_enemy 帶菁英/進階倍率、run 的 HP/牌組/藥水進場、
  戰後藥水寫回;結果以「重播 hook」餵回 enter_node——core 三段式介面
  零改動。給定 battle_hook 則維持同步結算(headless 測試/模擬不變)。
  地圖加冒險勝敗覆蓋文字
- [ui/demo_map.py] 升級為完整一輪冒險 demo:地圖 ↔ 手動戰鬥循環
- **修 bug:全套測試 segfault**——各測試檔 module fixture 各自
  pygame.quit(),ui.text 快取的 Font 綁定舊執行期,下個模組再用即
  原生層崩潰。修法:tests/conftest.py 統一 session 結束才 quit,
  text.clear_cache 連字體一起清。教訓:跨模組快取 + 生命週期成對
  的 C 資源(init/quit)必須單一擁有者
- 整合驗收:test_full_interactive_run_via_ui_clicks——完整一輪冒險,
  地圖點節點+戰鬥由規則式代理經 UI 點擊執行,直到勝負
- 測試 221/221(新增 test_map_battle_wiring 6 項;連跑兩次確認穩定)

## A/B 對照紀錄(新增)
### 實驗 3(2026-07-08):MCTS rollout policy × iterations
石像兵(100 場):random@200 剩HP 23.5 → heuristic@200 **30.7**(追平代差:
rule 28.8 / expectimax 31.9);heuristic@100 也有 29.0。
Boss(60 場/格):
| rollout | 100 iters | 200 iters | 500 iters |
|---------|----------|-----------|-----------|
| random | — | 91.7%(剩2.9) | 90.0%(剩4.3) |
| heuristic | 95.0%(剩6.3) | 95.0%(剩8.5) | **98.3%(剩8.8)** |
結論:**rollout 品質 >> 迭代數**——random 加到 500 iters 仍輸 heuristic@100;
heuristic@500 追平 Expectimax(98%)。待辦 #2 歸因確定:主因是
「隨機 rollout 低估防禦」(歸因2),不是 iterations(歸因1)。★報告素材

### 實驗 4(2026-07-08):5 build × 3 代理 Boss 勝率矩陣(圖:docs/charts/build_matrix.png)
| build | rule(500場) | expectimax(50場) | mcts@200 heur(50場) |
|-------|------|-----------|------|
| 毒流 | 15.6% | 100% | 96–100% |
| 力量流 | 38.4% | 100% | 100% |
| 反甲流 | 13.4% | 98% | **56→64%** |
| 易傷流 | **92.2%** | 98% | 100% |
| 節奏流 | 33.8% | 爆炸(見下) | 94% |
發現:
1. 長線 build(毒/力量)代差最大(15.6/38.4% → 100%)——設計命題成立 ★核心圖表
2. **Expectimax × 節奏流組合爆炸實測**:充能(棄牌分支)×回收(撿牌分支)×兵法
   (抽牌)把回合內窮舉炸開,單場 22.6s、部分 seed >130s,50 場矩陣格不可行。
   design.md §6.2「出牌順序:Expectimax 組合爆炸吃力」預言命中;
   MCTS 同牌組 0.46s/場 94%(iterations 有界)——兩種搜尋的本質差異一張表講完 ★報告素材
3. **MCTS × 反甲流弱點**:56%(rollout 評分漏了 damage_equal_block/detonate_poison
   → 修正後 64%)仍遠低於 expectimax 98%。殘差歸因:反甲流需跨回合疊甲再 payoff,
   貪婪 rollout 低估「等待價值」+ 狂暴計時懲罰慢節奏。→ 待辦(誠實的未竟之處)
4. 平衡旗標:易傷流對 rule 都有 92.2%(其他 build 13–38%)——易傷流疑似過強,
   下次平衡迭代的 A/B 對象
5. 樣本數注意:expectimax/mcts 格僅 50 場(±7%),PC 端應以 n≥200 重跑定稿

## A/B 對照紀錄(第一階段)
### 實驗 1(2026-07-07):敵人 HP +50%(28/22/40 → 42/33/60),其餘不動
| 代理 | 巨鼠勝率 | 毒蛛勝率 | 石像兵勝率 | 石像兵勝場剩HP |
|------|---------|---------|-----------|---------------|
| random 前→後 | 96%→88.5% | 96.5%→90.5% | 1%→0% | 10.5→— |
| rule 前→後 | 100%→100% | 100%→100% | 100%→100% | 37.3→28.8 |
| expectimax 前→後 | 100%→100% | 100%→100% | 100%→100% | 40.4→32.2 |
結論:HP 只拉長戰鬥、砍隨機勝率,砍不動有腦代理的勝率(威脅不足)。
「勝場剩 HP」才是一般戰的區別度指標:expectimax 對石像兵多留 3.4 滴
(防禦時機更準),HP 越高差距越大。勝率要拉開差距得靠傷害面或 Boss。

### 三版代理對照・第一批(2026-07-07,200 場/組,起始牌組,敵 HP 42/33/60)
| 代理 | 巨鼠 | 毒蛛 | 石像兵 | 石像兵剩HP | 石像兵耗時 |
|------|------|------|--------|-----------|-----------|
| random | 88.5% | 90.5% | 0% | — | 0.0s/場 |
| rule | 100% | 100% | 100% | 28.8 | 0.0002s/場 |
| expectimax(d2s3) | 100% | 100% | 100% | **31.9** | 0.52s/場 |
| mcts(200 iters) | 100% | 100% | 100% | 23.8 | 0.39s/場 |
發現:**MCTS 在一般戰輸給貪婪**(剩 HP 墊底、戰鬥拖最長)。歸因:
(1) 200 iterations 的統計雜訊 (2) 隨機 rollout 低估防禦價值
(3) 起始牌組沒有長線卡,MCTS 的長程優勢無用武之地。
這是誠實且重要的數據——「搜尋更深 ≠ 處處更強」,MCTS 的主場
(毒疊層、引爆時機、build 牌組、Boss)還沒進場。★報告素材

### 實驗 2(2026-07-07):Boss 難度調校(目標:規則式勝率 25-40%)
原規格(重擊 12、狂暴每 2 回合、HP 90)→ 起始牌組全代理勝率 ≈0%。
36 組網格搜尋(HP×重擊×連擊×狂暴節奏,各 500 場,規則式為基準):
- 觀察到懸崖效應:hp=90/p1=9/p2=(4,3)/enr=3 → 76%,p2 改 (5,3) → 27.8%
  (擊殺所需回合數的量化跳變)★報告素材
- 定案:HP 90、重擊 12→9、二階段 5×3 保留、狂暴每 2→3 回合
- 驗證(同數值):random 0% / rule 27.8%(500 場)/ mcts 89%(100 場)
  / expectimax 98%(150 場)→ **Boss 拉開代差,W1 埋的設計命題成立**★報告素材

## 待辦(依優先序,PC 恢復後)
1. W5-6:Pygame UI——照 docs/UI視覺規格與格子戰鬥提案.md 的 A 部執行
   (「暗夜光網」;U4 前禁用美術素材;一開始就用 Pygbag 相容寫法)。
   **U1–U4 完成含接線(demo_map 已是完整可玩循環)**:下一步 U5
   五個抉擇場景(Reward/Shop/Event/Rest/Settle 共用「抉擇面板」元件,
   A3.3:三選一錯相滑入、選中放大飛牌堆、菁英金光橫掃),
   換掉現在的自動拿獎勵/自動回血/商店事件路過三個佔位
2. 矩陣定稿:expectimax/mcts 各格 n≥200 重跑(沙盒僅 50 場,±7%);
   節奏流×expectimax 需先做搜尋剪枝(見 4)才可能量得完
3. MCTS 反甲流殘差:rollout 加入「等待/疊甲節奏」規則或 payoff 先驗,
   把 64% 拉近 expectimax 的 98%
4. Expectimax 組合爆炸對策(選做,好素材):回合內序列剪枝 / beam width 上限
5. 平衡:易傷流過強旗標(rule 92.2% vs 其他 13-38%)——A/B:制裁 6+4 → 5+3?
6. 新敵人平衡:對 build 牌組(連擊 vs 狂戰士、低甲速攻 vs 吸血蝠)跑矩陣,
   驗證謎題真的咬人;初始 HP 38/52 視結果調
7. 養成系統、存檔(第三階段);進階等級已就緒可直接當養成的解鎖軸

## 重要決策紀錄
- 2026-07-08:MCTSAgent 增 rollout="heuristic"(ε=0.2 保留探索;靜態評分含
  狀態相依傷害:反甲擊看當下護甲、引爆看毒層)。建構子預設仍 random
  保留「三版對照」歷史基線,sim/runner 的 mcts 改用 heuristic(實驗 3 全面較優)
- 2026-07-08:升級卡(鐵匠/毒藥商)= 衍生新 id 註冊進 UPGRADES 覆蓋表,
  get_card 查 CARDS→UPGRADES。理由:Card 共享不可變原則不破、
  基礎卡池測試不受污染、「效果=資料」延伸為「升級=資料替換」,引擎零改動
- 2026-07-08:冒險層(run.py)所有玩家選擇走「查選項→呼叫端決定→執行」三段式,
  戰鬥以 battle_hook 委派——同一套 run.py 服務 headless 測試與之後的 Pygame
- 2026-07-08:經濟初始值(勝+25/稀有卡65/刪卡50/休息30%)標記為待調非定案

### 第一階段決策(2026-07-07,保留)
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
- 2026-07-07(v2.3,Jeff 拍板):新增第 5 種狀態「虛弱」(敵攻 -25% 取整,
  每回合 -1,與易傷對稱)+ 第 27 張卡「痺擊」(1 費攻擊,傷害 4 + 虛弱 2)。
  回血/增傷需求盤點後確認已有(飲血/蓄力/易傷線),只補「降敵傷」真空缺。
  engine 新公開函式 enemy_attack_value():UI 意圖顯示與代理擋致死共用同一公式
- 2026-07-07:規則式代理「即時輸出」定義 = 敵方(HP+護甲)總削減。
  第一版只算掉血,對石像兵勝率 0%(打進護甲 Δ血=0 → 判定攻擊無價值 →
  發呆到 100 回合判負),連隨機亂打(3%)都不如;改定義後 100%。
  ★報告素材:heuristic 的定義縫隙被模擬立刻抓出來——測試驅動的代理開發
- 2026-07-07:代理不碰 state.rng(自帶獨立 Random)——同 seed 換代理,
  抽牌序完全相同,勝率差異可完全歸因於決策品質(A/B 對照的前提)

## 已知問題
- shop_buy_card 不驗證 card_id 是否為本次商店提供的那張(信任呼叫端)——
  UI 接上時記得只把商店 offer 的卡傳進來
- 升級卡的「二次升級」(如 bash_s_s)走 events 的延遲註冊:同行程可用,
  但存檔跨行程讀回不保證存在。MVP 建議限制每張卡只能鍛造一次,
  或存檔系統上線時把二階 id 一併預註冊
- 沙盒實驗樣本數:expectimax/mcts 矩陣格僅 50 場(±7%),結論方向可信、
  數字非定稿(見待辦 2)
- 無
