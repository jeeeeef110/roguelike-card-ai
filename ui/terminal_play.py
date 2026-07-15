"""ui/terminal_play.py — 終端手動對戰(W1 驗收:能完整打一場)

用法:python3 -m ui.terminal_play [giant_rat|poison_spider|stone_golem] [seed]
操作:輸入編號出牌 / e 結束回合 / q 放棄戰鬥
"""
import sys

from core.cards import PLAYER_HP, STARTING_DECK, get_card
from core.enemies import ENEMIES, enemy_ai, make_enemy
from core.engine import (
    ATTACK_LIMIT, apply_action, card_cost, enemy_attack_value, start_battle,
)
from core.models import GameState, PlayerState

ENEMY_NAMES = {"giant_rat": "巨鼠", "poison_spider": "毒蛛",
               "stone_golem": "石像兵", "blood_bat": "吸血蝠",
               "berserker": "狂戰士",
               "corrupted_knight": "腐化騎士(Boss)"}

_EFFECT_TEXT = {
    "damage": "傷害 {0}",
    "damage_bonus_vs_vulnerable": "傷害 {0},敵有易傷再 +{1}",
    "damage_per_vulnerable": "傷害 {0},敵每層易傷 +{1}",
    "damage_per_attack_played": "傷害 {0},本回合每出過一張攻擊卡 +{1}",
    "damage_equal_block": "傷害 = 目前護甲值",
    "damage_shatter": "傷害 {0};敵有護甲則全移除並追加等量傷害",
    "detonate_poison": "造成中毒層數 ×{0} 傷害,清空中毒",
    "block": "護甲 {0}",
    "retain_block": "本回合結束護甲不歸零",
    "lift_attack_limit": "本回合解除攻擊牌張數上限",
    "apply_vulnerable": "敵易傷 {0}",
    "apply_poison": "敵中毒 {0}",
    "apply_weak": "敵虛弱 {0}(攻擊 -25%)",
    "gain_strength": "力量 +{0}",
    "draw": "抽 {0} 張",
    "gain_energy": "能量 +{0}",
    "next_turn_energy": "下回合能量 {0:+d}",
    "heal": "回復 {0} HP",
    "self_damage": "自受 {0} 傷(不經護甲)",
    "discard_choose": "棄 1 張手牌",
    "retrieve_choose": "從棄牌堆選 1 張入手",
}


def card_text(card_id: str) -> str:
    card = get_card(card_id)
    return ";".join(_EFFECT_TEXT[e[0]].format(*e[1:]) for e in card.effects)


def intent_text(s, intent: tuple) -> str:
    def dmg(base):  # 顯示實際會痛多少(含力量/虛弱/易傷),跟結算同一條公式
        real = enemy_attack_value(s, base)
        return f"{base}" if real == base else f"{base}(實際 {real})"

    kind = intent[0]
    if kind == "attack":
        times = intent[2] if len(intent) > 2 else 1
        return f"攻擊 {dmg(intent[1])}" + (f" ×{times}" if times > 1 else "")
    if kind == "attack_poison":
        return f"攻擊 {dmg(intent[1])} + 中毒 {intent[2]}"
    if kind == "attack_lifesteal":
        return f"攻擊 {dmg(intent[1])}(造成多少實傷就回多少血)"
    if kind == "block":
        return f"護甲 {intent[1]}"
    if kind == "poison":
        return f"中毒 {intent[1]}"
    if kind == "web":
        return "織網(你下回合攻擊卡費用 +1)"
    if kind == "charge":
        return "蓄力(下回合攻擊 12;本回合對它造成 ≥8 傷可打斷)"
    return "無動作"


def _statuses(unit) -> str:
    parts = []
    if unit.strength:
        parts.append(f"力量{unit.strength}")
    if unit.vulnerable:
        parts.append(f"易傷{unit.vulnerable}")
    if unit.poison:
        parts.append(f"中毒{unit.poison}")
    if getattr(unit, "weak", 0):
        parts.append(f"虛弱{unit.weak}")
    return " ".join(parts) or "—"


def render(s: GameState) -> None:
    p, e = s.player, s.enemy
    name = ENEMY_NAMES[e.enemy_id]
    atk = ("∞(已破限)" if p.attack_limit_off
           else f"{p.attacks_played}/{ATTACK_LIMIT}")
    print(f"\n════ 回合 {s.turn} ════")
    print(f"  你     HP {p.hp}/{p.max_hp}  護甲 {p.block}  能量 {p.energy}  "
          f"攻擊 {atk}  狀態:{_statuses(p)}")
    print(f"  {name}   HP {e.hp}/{e.max_hp}  護甲 {e.block}  狀態:{_statuses(e)}")
    print(f"  敵人意圖:{intent_text(s, e.intent)}")
    print(f"  牌庫 {len(p.draw_pile)} 張|棄牌堆 {len(p.discard_pile)} 張")
    print("  手牌:")
    for i, cid in enumerate(p.hand, 1):
        card = get_card(cid)
        cost = card_cost(s, cid)
        afford = " " if p.energy >= cost else "✗"
        print(f"   {afford}{i}. {card.name}({cost}費)— {card_text(cid)}")


def _pick_choice(s: GameState, card_id: str) -> str | None:
    """充能/回收的選擇子選單。無對象回 None(效果落空)。"""
    card = get_card(card_id)
    retrieving = any(e[0] == "retrieve_choose" for e in card.effects)
    pool = (s.player.discard_pile if retrieving
            else [c for c in s.player.hand if c != card_id])
    pool = list(dict.fromkeys(pool))
    if not pool:
        print("  (沒有可選對象,效果將落空)")
        return None
    verb = "撿回" if retrieving else "棄掉"
    for i, cid in enumerate(pool, 1):
        print(f"    {i}. {get_card(cid).name}")
    while True:
        raw = input(f"  要{verb}哪張?> ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(pool):
            return pool[int(raw) - 1]
        print("  看不懂,輸入編號。")


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] in ENEMIES:
        enemy_id = args[0]
    else:
        ids = list(ENEMIES)
        for i, eid in enumerate(ids, 1):
            print(f"  {i}. {ENEMY_NAMES[eid]}(HP {make_enemy(eid).max_hp})")
        raw = input("挑一隻對手 > ").strip()
        enemy_id = (ids[int(raw) - 1]
                    if raw.isdigit() and 1 <= int(raw) <= len(ids) else ids[0])
    seed = int(args[1]) if len(args) > 1 else 0

    p = PlayerState(hp=PLAYER_HP, max_hp=PLAYER_HP, deck=list(STARTING_DECK))
    s = GameState(p, make_enemy(enemy_id), seed=seed)
    start_battle(s, enemy_ai)
    print(f"\n⚔  遭遇 {ENEMY_NAMES[enemy_id]}!(seed={seed})"
          f"  [編號=出牌  e=結束回合  q=放棄]")

    while not s.battle_over:
        render(s)
        raw = input("> ").strip().lower()
        if raw == "q":
            print("你逃跑了。")
            return
        if raw == "e":
            apply_action(s, ("end_turn",), enemy_ai)
            continue
        if not (raw.isdigit() and 1 <= int(raw) <= len(s.player.hand)):
            print("  看不懂。輸入手牌編號、e 或 q。")
            continue
        card_id = s.player.hand[int(raw) - 1]
        cost = card_cost(s, card_id)
        if s.player.energy < cost:
            print(f"  能量不足:{get_card(card_id).name} 要 {cost} 費。")
            continue
        needs_choice = any(e[0].endswith("_choose")
                           for e in get_card(card_id).effects)
        choice = _pick_choice(s, card_id) if needs_choice else None
        try:
            apply_action(s, ("play", card_id, choice))
        except ValueError as err:  # 攻擊上限等規則擋下
            print(f"  {err}")

    print("\n" + ("🎉 勝利!" if s.player_won else "💀 你倒下了…") +
          f"  (你 HP {max(s.player.hp, 0)} / {ENEMY_NAMES[enemy_id]} "
          f"HP {max(s.enemy.hp, 0)},共 {s.turn} 回合)")


if __name__ == "__main__":
    main()
