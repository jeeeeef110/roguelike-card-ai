"""core/models.py — 遊戲狀態資料結構

設計原則(v2.2 定案,勿隨意推翻):
1. GameState 會被 MCTS 複製上百萬次 → __slots__ + 手寫 clone(),全案禁用 deepcopy
2. Card 是不可變的共享定義(NamedTuple),狀態層只持有卡牌 id 字串,複製只是複製字串列表
3. 所有隨機性走注入的 random.Random(seed),同 seed 可完整重播一場戰鬥
4. 零外部依賴:本檔只 import 標準函式庫
5. 本檔只有「資料」,不含任何規則邏輯(規則在 engine.py,尚未建立)
"""
from __future__ import annotations

from random import Random
from typing import NamedTuple


class Card(NamedTuple):
    """卡牌定義。全遊戲共享一份,絕不複製、絕不修改。

    effects 是 (效果種類, *參數) 的 tuple 序列,由 engine 解讀。
    例:重擊 = (("damage", 8), ("apply_vulnerable", 2))
    """

    card_id: str
    name: str
    cost: int
    kind: str      # "attack" | "skill"
    rarity: str    # "starter" | "common" | "rare"
    effects: tuple


class PlayerState:
    """玩家的戰鬥中狀態。手牌/牌庫/棄牌堆只存 card_id 字串。"""

    __slots__ = (
        "hp", "max_hp",
        "energy", "base_energy",
        "block", "block_retain",          # block_retain: 堅守效果,本回合結束護甲不歸零
        "strength", "vulnerable", "poison",
        "hand", "draw_pile", "discard_pile",
        "next_energy_delta",              # 蓄勢 +2 / 透支 -1,下回合開始時結算後歸零
        "attack_cost_delta",              # 織網:本回合攻擊卡費用修正,回合結束歸零
        "attacks_played",                 # 撕裂:本回合已出攻擊卡數,回合結束歸零
        "attack_limit_off",               # 破限:本回合解除攻擊張數上限,回合結束歸零
    )

    def __init__(self, hp: int, max_hp: int, deck: list[str], base_energy: int = 3):
        self.hp = hp
        self.max_hp = max_hp
        self.energy = 0
        self.base_energy = base_energy
        self.block = 0
        self.block_retain = False
        self.strength = 0
        self.vulnerable = 0
        self.poison = 0
        self.hand: list[str] = []
        self.draw_pile: list[str] = list(deck)
        self.discard_pile: list[str] = []
        self.next_energy_delta = 0
        self.attack_cost_delta = 0
        self.attacks_played = 0
        self.attack_limit_off = False

    def clone(self) -> "PlayerState":
        c = PlayerState.__new__(PlayerState)
        c.hp = self.hp
        c.max_hp = self.max_hp
        c.energy = self.energy
        c.base_energy = self.base_energy
        c.block = self.block
        c.block_retain = self.block_retain
        c.strength = self.strength
        c.vulnerable = self.vulnerable
        c.poison = self.poison
        c.hand = list(self.hand)
        c.draw_pile = list(self.draw_pile)
        c.discard_pile = list(self.discard_pile)
        c.next_energy_delta = self.next_energy_delta
        c.attack_cost_delta = self.attack_cost_delta
        c.attacks_played = self.attacks_played
        c.attack_limit_off = self.attack_limit_off
        return c


class EnemyState:
    """敵人的戰鬥中狀態。意圖制:不持有牌組。

    intent: (種類, *參數),例 ("attack", 6)、("charge",)、("block", 8)
    pattern: 意圖狀態機的內部狀態(dict,內容由各敵人的行為函式定義,
             例:石像兵的循環指標、巨鼠的蓄力 flag、毒蛛的織網倒數)
    """

    __slots__ = (
        "enemy_id", "hp", "max_hp", "block",
        "poison", "vulnerable", "strength",
        "weak",                           # 虛弱(v2.3):攻擊傷害 -25%,每回合 -1
        "block_persists",                 # 石像兵:護甲不歸零
        "intent", "pattern",
    )

    def __init__(self, enemy_id: str, hp: int, block_persists: bool = False):
        self.enemy_id = enemy_id
        self.hp = hp
        self.max_hp = hp
        self.block = 0
        self.poison = 0
        self.vulnerable = 0
        self.strength = 0
        self.weak = 0
        self.block_persists = block_persists
        self.intent: tuple = ("none",)
        self.pattern: dict = {}

    def clone(self) -> "EnemyState":
        c = EnemyState.__new__(EnemyState)
        c.enemy_id = self.enemy_id
        c.hp = self.hp
        c.max_hp = self.max_hp
        c.block = self.block
        c.poison = self.poison
        c.vulnerable = self.vulnerable
        c.strength = self.strength
        c.weak = self.weak
        c.block_persists = self.block_persists
        c.intent = self.intent            # tuple 不可變,直接共享
        c.pattern = dict(self.pattern)
        return c


class GameState:
    """單場戰鬥的完整狀態。engine 的所有規則函式都吃這個物件。"""

    __slots__ = ("player", "enemy", "turn", "rng", "battle_over", "player_won")

    def __init__(self, player: PlayerState, enemy: EnemyState, seed: int = 0):
        self.player = player
        self.enemy = enemy
        self.turn = 0
        self.rng = Random(seed)
        self.battle_over = False
        self.player_won = False

    def clone(self, rng: str | int = "share") -> "GameState":
        """複製狀態。rng 參數決定 RNG 處理方式(效能關鍵,勿改回無腦深複製):

        - "share"(預設):複本與原本共用同一個 Random 物件。
          用於 MCTS rollout 等用完即丟的複本——快 30 倍。
          注意:複本消耗亂數會推進原本的 RNG 序列,不可用於需要重播的場景。
        - "replay":完整複製 RNG 內部狀態(慢,約 4.5 萬次/秒)。
          用於需要「從此刻精確重播」的除錯場景。
        - int:以該整數重新播種。用於 determinization(rollout 前洗假想牌庫)。

        實測(Python 3.12):share 模式 >100 萬次/秒,replay 模式 ~4 萬次/秒。
        瓶頸在 Mersenne Twister 的 625-int 狀態複製,故預設繞開它。
        """
        c = GameState.__new__(GameState)
        c.player = self.player.clone()
        c.enemy = self.enemy.clone()
        c.turn = self.turn
        if rng == "share":
            c.rng = self.rng
        elif rng == "replay":
            c.rng = Random()
            c.rng.setstate(self.rng.getstate())
        else:
            c.rng = Random(rng)
        c.battle_over = self.battle_over
        c.player_won = self.player_won
        return c
