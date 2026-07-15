# UI 視覺規格 × 格子戰鬥提案:完整執行藍圖

> 給接手的 AI 模型與 Jeff:本文件是可直接執行的規格書,不是願景散文。
> A 部(視覺)= 已定案,PC 恢復後照做;B 部(格子戰鬥)= **未拍板提案,
> 沒有 Jeff 明確同意前禁止實作**。
> 執行時遵守 CLAUDE.md 全部紀律:單次一模組、無佔位符、先測後進、更新 PROGRESS.md。

---

# A 部:視覺規格「暗夜光網」(定案)

## A1. 設計語言(每個畫面都要遵守的四原則)

參考基準:Unseen Studio 的 Hubtown 網站(深藍夜景 + 發光節點路網)。
我們的地圖資料結構(分層 DAG)天生就是節點網路——這個風格是把遊戲的內在畫出來。

1. **色彩極簡**:全遊戲一個深底色 + 每流派一個霓虹強調色。
   - 底:`#050A14`(近黑深藍);面板:`#0B1424`;線稿:`#1C2C44`
   - 強調色:毒 `#3DFF9E` / 力量 `#FF4D4D` / 反甲 `#4DA6FF` / 易傷 `#FFB84D` / 節奏 `#C77DFF` / 中性光 `#7FD4FF`
   - 文字:主 `#E8F0FF`、次 `#8FA3C0`。**禁止**在同畫面用超過「底色+2 個強調色」。
2. **一切皆緩動**:任何元素不得瞬間出現/消失/位移。統一走 tween(見 A2),預設 easing = ease-out cubic,時長 200–450ms;鏡頭類 600–900ms。
3. **鏡頭會呼吸**:場景切換用鏡頭推拉平移,不硬切;待機時全畫面有 ±1px 的極慢漂浮(sin 波,週期 6–8 秒)。
4. **大字少資訊**:每畫面同時最多一個焦點資訊。字體:思源黑體(Noto Sans TC),標題粗、字距加寬(模仿 Hubtown 的 H U B T O W N 式字距)。

## A2. 技術基座(先做這三樣,任何場景都蓋在上面)

### A2.1 Tween 管理器 `ui/tween.py`(~120 行,可單元測試、無需螢幕)
```
class Tween: (obj屬性名, start, end, duration, easing, delay=0, on_done=None)
class TweenManager: add(...), update(dt) -> 內部推進所有 tween
easing 至少四種:linear / ease_out_cubic / ease_in_out / ease_out_back(過衝彈跳)
```
驗收(pytest,不開視窗):數學正確性(t=0/0.5/1 的值)、delay、on_done 觸發、
多 tween 併行、同物件同屬性後蓋前。**這是第一個要寫的檔案。**

### A2.2 發光渲染 `ui/glow.py`
Pygame 沒有內建 bloom,用「多層放大模糊 + BLEND_RGB_ADD」近似:
```
def glow_circle(surface, pos, radius, color, layers=4):
    由外而內畫 layers 層半徑遞減、alpha 遞增的圓,flags=BLEND_RGB_ADD
def glow_line(surface, a, b, color, width): 同理三層線
```
效能守則:發光元素每幀重畫成本高 → 靜態光暈**預先烘焙**成 Surface 快取
(dict key = (radius, color)),每幀只 blit。驗收:200 節點地圖 60fps(用 clock.get_fps() 斷言 >55)。

### A2.3 場景管理與鏡頭 `ui/scenes.py`
```
class Scene: handle(event) / update(dt) / draw(surface)
class Camera: x, y, zoom(全部可被 tween 驅動);world_to_screen()
class Director: push/replace(scene, transition="pan"|"fade"),持有 TweenManager 與 Camera
```
場景清單:Title / MapScene / BattleScene / RewardScene / ShopScene / EventScene / RestScene / SettleScene。
全部只呼叫 core 公開 API(run.py 三段式、engine 的 legal_actions/apply_action),**UI 內不得出現任何遊戲規則**。

## A3. 各場景規格(依實作順序)

### A3.1 MapScene(招牌畫面,最先做——它就是 Hubtown 那張圖)
- 佈局:節點網路以「近大遠小」透視感排布(每層 y 遞減、x 壓縮 5–8%,製造深度);背景兩三條慢速漂移的稜線剪影(多邊形,比底色亮 8%)
- 節點:發光方塊/圓;**可走的下一批節點呼吸閃爍**(alpha 0.6↔1.0,週期 1.8s,錯相);已走過的路徑線亮起(中性光),未走的暗線
- 節點圖示:戰鬥=劍、菁英=角、休息=火、商店=袋、事件=?(game-icons.net 白色 icon 染色)
- 進入節點:鏡頭 tween 推近該節點(zoom 1→1.6, 700ms)→ transition 到對應場景
- 稀有時刻:菁英節點用金色光、Boss 節點紅光且光暈更大

### A3.2 BattleScene
- 佈局:敵人置中偏上(立繪用色塊剪影+發光描邊即可,美術後換);玩家手牌扇形排底部;左上玩家 HP/能量、右上敵人 HP/意圖
- **意圖永遠醒目**:敵人頭頂 icon+數字,宣告時 ease_out_back 彈入
- 手牌互動:hover 上浮 20px + 微放大;出牌 = 卡牌 tween 飛向目標 + 目標受擊閃白 2 幀 + 傷害數字上飄淡出(數字大、粗、流派色)
- 血條:永不瞬降,總是 300ms 滑到新值;護甲=血條外的藍色描邊環
- 藥水:右下三個圓槽,使用時炸出對應色光環
- 出牌建議(MCTS):可開關的柔光高亮建議卡 + 小字勝率;預設關(面試 demo 再開)
- Boss 二階段切換:全畫面 0.5s 暗化 + 鏡頭輕震 + Boss 描邊變色

### A3.3 Reward/Shop/Event/Rest/Settle(共用「抉擇面板」元件)
- 三選一:卡牌從中央錯相依序滑入(delay 80ms 遞增);選中者放大飛向牌堆角落,未選者淡出
- 菁英獎勵:三張全稀有 → 進場前金光橫掃一次(0.4s)
- 休息:兩個大按鈕(回血/鍛造),icon+一行字,選鍛造展開牌組網格
- 結算:碎片數字滾動累加;Boss 解鎖三選一用最隆重的進場(黑幕+單卡聚光)

### A3.4 音效(最後加,但必加)
Kenney.nl 免費包:出牌、受擊、勝利、敗北、購買、解鎖、環境低鳴 BGM 一首循環。
音量預設 60%,設定可關。

## A4. 實作排程與驗收門(接手模型照此推進)
| 步驟 | 內容 | 驗收 |
|---|---|---|
| U1 | tween.py + 測試 | pytest 全綠(無需螢幕) |
| U2 | scenes.py 骨架 + glow.py | 空場景切換 demo 60fps |
| U3 | MapScene(色塊版) | 完整走完一輪地圖(戰鬥先用自動勝 stub) |
| U4 | BattleScene 互動 | 手動打贏巨鼠;所有數值變化皆有動畫 |
| U5 | 五個抉擇場景 | 完整一輪冒險含藥水/休息/商店/事件 |
| U6 | 養成接線(MetaState) | Boss 解鎖三選一、進階選擇、存檔續玩 |
| U7 | 音效+打磨+錄 demo | 3 分鐘 demo 影片 |
每步結束:更新 PROGRESS.md、commit。**U4 完成前禁止碰任何美術素材**(色塊佔位)。

## A5. 已知坑
- Pygame 文字每幀重 render 很慢 → 文字 Surface 快取(key=(str,size,color))
- BLEND_RGB_ADD 疊太多層會白爆 → 每元素上限 4 層
- Pygbag(網頁版)不支援部分 mixer 格式 → 音效統一 OGG;主迴圈須 async(await asyncio.sleep(0)),**一開始就照 Pygbag 相容寫法寫**,不要事後改

---

# B 部:格子戰鬥 v2 提案(未拍板・禁止擅自實作)

## B1. 一句話
把戰鬥從「抽象對峙」搬到 5×5 格盤:攻擊卡有射程與形狀,Boss 的攻擊預告顯示在格子上,站位本身成為決策。參考系:《Into the Breach》(格上攻擊預告)、《Fights in Tight Spaces》(卡牌+站位)。

## B2. 設計規格(草案)
- 盤面 5×5;玩家 1 格,敵人 1–3 格(格子戰讓多敵人變自然)
- 卡牌新增欄位:`range`(1=近戰/2–3/全場)與 `shape`(單格/十字/直線/3×3)
  - 例:打擊=射程1單格;亂舞=自身周圍8格;引爆=毒目標為中心十字
- 新卡型:移動卡(位移 1–2 格,0–1 費);部分攻擊帶位移(衝鋒=直線移動+傷害)
- 敵人意圖=**格子預告**:下回合的攻擊範圍直接亮紅在盤面上(Into the Breach 核心樂趣);Boss 二階段=大範圍圖形(整排/十字/外圈)
- 能量/抽牌/狀態/藥水/冒險層:**全部不變**——只換戰鬥的空間表達

## B3. 衝擊誠實清單(為什麼現在不做)
1. GameState 加座標系,clone 效能重新驗證
2. 27 張卡全部重設計射程形狀 + 新增移動卡 → 卡池重平衡
3. 敵人 AI 要會走位(新問題:位置評估)
4. 三代理全部要理解空間:動作空間爆增(出牌×目標格),Expectimax 必炸,MCTS 要重調
5. 152 測試大半重寫;**全部勝率矩陣與平衡數據作廢重跑**
6. UI 的 BattleScene 全部重做
估計 4–6 週(不含平衡)。等於吃掉 UI+打磨+緩衝的全部預算。

## B4. 決策條件與路線
- **做的前提(全部成立才做)**:現行版已完成 U1–U7 且備審材料齊 → 時間點實際上=2027 年 2–3 月備審提交後
- 若做:開 `grid-battle` 分支,順序=core 座標系 → 5 張卡原型 → 一隻敵人 → 規則式代理 → 好玩再擴
- 若不做:本提案原文放進備審「未來展望」——展示設計視野,比半成品有價值
- **AI 研究紅利**(做的最大誘因):空間推理讓三代理差距更戲劇化,「動作空間爆炸下的 MCTS」是更高階的研究題目

---

# 附:接手模型的開工儀式(每次會話)
1. 讀 CLAUDE.md、PROGRESS.md、本文件相關章節
2. 向 Jeff 確認本次任務(預設=A4 表的下一個未完成步驟)
3. 完成 → 跑測試 → 更新 PROGRESS.md → 給 commit 訊息
4. B 部相關請求一律先問:「格子戰鬥提案 Jeff 已拍板了嗎?」
