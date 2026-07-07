# roguelike-card-ai

Roguelike 卡牌構築遊戲 + 會思考的玩家 AI。

核心賣點:一套零依賴的規則引擎,同時支撐「人玩的遊戲」與「AI 的訓練場」——
三版代理(規則式 → Expectimax → MCTS)在同一卡池上對戰,用模擬數據驅動數值平衡。

## 快速開始

```bash
# 親自打一場(終端介面,無任何依賴)
python3 -m ui.terminal_play

# 跑測試(需 pytest)
python3 -m pytest tests/ -v
```

## 架構

```
core/     # 純邏輯零依賴:卡牌資料、規則引擎、敵人意圖狀態機。RNG 注入,同 seed 可重播
agents/   # 三版玩家代理(規劃中:rule_based → expectimax → mcts)
ui/       # 終端對戰;Pygame 版規劃中
sim/      # headless 模擬器與 A/B 平衡實驗(規劃中)
tests/    # pytest,每個測試對應一條遊戲規則
```

## 文件

- 設計定稿:《[專案完整資料 v2.2 定稿](專案完整資料_v2.2_定稿.md)》(含 v2.3 試玩後平衡修正)
- 開發紀錄與決策:[PROGRESS.md](PROGRESS.md)
- commit 格式:`[模組] 做了什麼`
