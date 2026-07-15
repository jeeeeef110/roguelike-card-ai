# roguelike-card-ai

Roguelike 卡牌構築遊戲 × 三代理 AI 對照研究(APCS 備審專案)。

## 快速導覽
- 玩法:docs/遊戲玩法總覽.md
- 運作原理(零基礎):docs/專案零基礎完全解說.md
- 現行設計定案:docs/design.md(v2.3)
- 設計演進史:docs/history/(GDD v1→v2→v2.1→v2.2 + 審查報告)
- AI 協作透明說明:docs/專案貢獻與AI協作說明.md
- 開發進度與決策紀錄:PROGRESS.md
- AI 協作規範:CLAUDE.md(Claude Code 自動讀取)
- 數據圖表:docs/charts/

## 開發
- 測試:`python -m pytest tests/ -v`(無 pytest 時 `python run_tests.py`)
- 架構:core(純邏輯,零依賴)/ agents / ui / sim / tests
- 終端試玩:`python -m ui.terminal_play`
