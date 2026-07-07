"""core/enemies.py — 三隻敵人的意圖狀態機 + 被動特性(v2.2 §4)

每隻敵人 = 一個意圖函式 fn(state) -> intent,在回合開始被 engine 呼叫:
被動特性在此結算(如石像兵 +3 甲),回傳的意圖公開給玩家、回合結束執行。
內部狀態(蓄力旗標、循環指標)存在 EnemyState.pattern(dict,clone 安全)。

規則定案(2026-07-07):
- 巨鼠打斷(Jeff 拍板):蓄力期間受到 ≥8 傷害 → 大招取消,改普通攻擊 6。
  計傷窗口 = 蓄力宣告起到下次宣告前,以 HP 差計算(含中毒 tick——毒也能打斷)
- 毒蛛織網:回合數為 3 的倍數必織網(取代該回合行動),其餘回合走 50/30/20
- 石像兵:+3 護甲在宣告意圖時生效(玩家當回合就要面對),護甲永不歸零
"""
from core.models import EnemyState, GameState


def _giant_rat(state: GameState) -> tuple:
    """巨鼠:60% 攻擊 6 / 40% 蓄力→下回合攻擊 12;蓄力可被 ≥8 傷打斷。"""
    e = state.enemy
    if e.pattern.get("charging"):
        e.pattern["charging"] = False
        if e.pattern["hp_at_charge"] - e.hp >= 8:
            return ("attack", 6)  # 打斷:大招取消,改普攻
        return ("attack", 12)
    if state.rng.random() < 0.6:
        return ("attack", 6)
    e.pattern["charging"] = True
    e.pattern["hp_at_charge"] = e.hp
    return ("charge",)


def _poison_spider(state: GameState) -> tuple:
    """毒蛛:每 3 回合織網;其餘 50% 攻4+毒2 / 30% 毒3 / 20% 甲6。"""
    if state.turn % 3 == 0:
        return ("web",)
    r = state.rng.random()
    if r < 0.5:
        return ("attack_poison", 4, 2)
    if r < 0.8:
        return ("poison", 3)
    return ("block", 6)


# Boss 數值(平衡實驗 2 定案:目標=有腦代理用起始牌組勝率 25-40%)
# 原規格 12/(5,3)/每2回合 → 勝率 0%;36 組網格搜尋(各 500 場)後取
# 「保留 HP 90 與二階段 5×3、只軟化重擊與狂暴節奏」的組合 → 27.8%
BOSS_P1_ATTACK = 9        # 一階段:單次重擊(原 12)
BOSS_P2_ATTACK = (5, 3)   # 二階段:(單發, 次數)
BOSS_ENRAGE_EVERY = 3     # 每 N 回合力量 +1(原 2)


def _corrupted_knight(state: GameState) -> tuple:
    """Boss 腐化騎士:狂暴計時(反龜縮)+ 雙階段
    (HP<50%:單次重擊 → 3 連擊;重擊怕高甲、連擊怕易傷/虛弱)。"""
    e = state.enemy
    if state.turn % BOSS_ENRAGE_EVERY == 0:
        e.strength += 1
    if e.hp * 2 < e.max_hp:
        return ("attack", *BOSS_P2_ATTACK)
    return ("attack", BOSS_P1_ATTACK)


def _stone_golem(state: GameState) -> tuple:
    """石像兵:固定循環 甲8 → 攻9 → 攻9;被動每回合 +3 甲、護甲不歸零。"""
    e = state.enemy
    e.block += 3
    step = e.pattern.get("step", 0)
    e.pattern["step"] = (step + 1) % 3
    return (("block", 8), ("attack", 9), ("attack", 9))[step]


# enemy_id → (HP, 護甲不歸零, 意圖函式)
# HP 為 v2.3 平衡值(原 28/22/40,+50%:三代理勝率全 100% 飽和 → 拉長戰鬥)
ENEMIES: dict[str, tuple[int, bool, object]] = {
    "giant_rat": (42, False, _giant_rat),
    "poison_spider": (33, False, _poison_spider),
    "stone_golem": (60, True, _stone_golem),
    "corrupted_knight": (90, False, _corrupted_knight),  # Boss
}


def make_enemy(enemy_id: str) -> EnemyState:
    """依 v2.2 §4 規格建立敵人。未知 id 直接報錯。"""
    if enemy_id not in ENEMIES:
        raise KeyError(f"未知的 enemy_id:{enemy_id!r}(合法值:{sorted(ENEMIES)})")
    hp, block_persists, _ = ENEMIES[enemy_id]
    return EnemyState(enemy_id, hp=hp, block_persists=block_persists)


def enemy_ai(state: GameState) -> tuple:
    """通用分派器:依 state.enemy.enemy_id 呼叫對應的意圖函式。
    直接作為 engine 的 enemy_ai 參數使用。"""
    return ENEMIES[state.enemy.enemy_id][2](state)
