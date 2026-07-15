"""ui/choice_scenes.py — 節點抉擇接線(藍圖 A3.3,U5)

把 enter_node 的結果字典翻成 ChoicePanel 序列;效果執行全走 core
公開 API(take_reward/rest_*/shop_*/events.*),本檔不含規則。
入口:open_node_result(map_scene, node, out, done)——
所有面板結束後呼叫 done()(MapScene 用它拉回鏡頭、解鎖輸入)。
"""
from __future__ import annotations

from core.cards import get_card
from core.events import (blacksmith_upgrade, is_poison_card,
                         old_warrior_trade, poison_merchant_commit,
                         poison_merchant_sample)
from core.potions import MAX_POTIONS, POTIONS
from core.run import (REST_HEAL_RATIO, rest_heal, rest_upgrade,
                      shop_buy_card, shop_buy_potion, shop_remove_card,
                      take_reward)
from ui.choice_panel import GOLD, ChoicePanel, Option
from ui.terminal_play import card_text

RED = (255, 77, 77)
BLUE = (77, 166, 255)
GREEN = (61, 255, 158)
PURPLE = (199, 125, 255)


def card_option(cid: str, enabled: bool = True, badge: str = "") -> Option:
    card = get_card(cid)
    accent = RED if card.kind == "attack" else BLUE
    return Option(f"{card.name}({card.cost}費)",
                  card_text(cid).split(";")[:4], accent, enabled, badge)


def _deck_grid(ms, title, enabled_fn, badge_fn, on_pick, skip_label, on_skip):
    """展開牌組網格選一張;i = 牌組索引。skip → on_skip()。"""
    opts = [card_option(cid, enabled_fn(cid), badge_fn(cid))
            for cid in ms.run.deck]

    def choose(i):
        if i is None:
            on_skip()
        else:
            on_pick(i)

    ms.director.push(ChoicePanel(title, opts, choose, skip_label=skip_label))


def open_node_result(ms, node, out: dict, done) -> None:
    if "rewards" in out:
        _open_rewards(ms, node, out["rewards"], done)
    elif "rest_options" in out:
        _open_rest(ms, done)
    elif "shop" in out:
        _open_shop(ms, out["shop"], done)
    elif "event" in out:
        _open_event(ms, out["event"], done)
    else:
        done()          # 勝負/無後續節點


# ------------------------------------------------------------ 獎勵三選一

def _open_rewards(ms, node, rewards: list[str], done) -> None:
    elite = node.node_type == "elite"

    def choose(i):
        take_reward(ms.run, rewards, rewards[i] if i is not None else None)
        done()

    ms.director.push(ChoicePanel(
        "菁英戰利品(全稀有)" if elite else "戰利品:選一張卡",
        [card_option(c) for c in rewards], choose, skip_label="跳過",
        sweep_color=GOLD if elite else None))


# ------------------------------------------------------------ 休息二選一

def _open_rest(ms, done) -> None:
    run = ms.run
    heal_amt = min(run.max_hp - run.hp, int(run.max_hp * REST_HEAL_RATIO))

    def upgrade_pick(pos):
        rest_upgrade(run, pos)
        done()

    def fallback_heal():
        rest_heal(run)
        done()

    def choose(i):
        if i == 0:
            fallback_heal()
        else:
            _deck_grid(ms, "鍛造:選一張卡(費用 -1)",
                       lambda cid: get_card(cid).cost > 0,
                       lambda cid: "", upgrade_pick,
                       "改成回血", fallback_heal)

    ms.director.push(ChoicePanel("休息:保命或變強?", [
        Option("回血", [f"回復 {heal_amt} HP", f"({run.hp}/{run.max_hp})"],
               GREEN),
        Option("鍛造", ["永久升級一張卡", "費用 -1(最低 0)"], BLUE),
    ], choose))


# ------------------------------------------------------------ 商店

def _open_shop(ms, shop: dict, done) -> None:
    run = ms.run
    state = {"card": False, "potion": False}      # 各限購一次

    def reopen():
        opts, acts = [], []
        if not state["card"]:
            cid = shop["card"]
            opts.append(card_option(cid, run.gold >= shop["card_price"],
                                    f'{shop["card_price"]}金'))
            acts.append("card")
        opts.append(Option("刪一張卡", ["精簡牌組"], PURPLE,
                           run.gold >= shop["remove_price"] and bool(run.deck),
                           f'{shop["remove_price"]}金'))
        acts.append("remove")
        if not state["potion"]:
            p = POTIONS[shop["potion"]]
            opts.append(Option(p.name, ["戰鬥中免費動作"], GREEN,
                               (run.gold >= shop["potion_price"]
                                and len(run.potions) < MAX_POTIONS),
                               f'{shop["potion_price"]}金'))
            acts.append("potion")

        def choose(i):
            if i is None:
                done()
                return
            act = acts[i]
            if act == "card":
                shop_buy_card(run, shop["card"])
                state["card"] = True
                reopen()
            elif act == "potion":
                shop_buy_potion(run, shop["potion"])
                state["potion"] = True
                reopen()
            else:
                _deck_grid(ms, "刪卡:選一張移除",
                           lambda cid: True, lambda cid: "",
                           lambda pos: (shop_remove_card(run, pos), reopen()),
                           "取消", reopen)

        ms.director.push(ChoicePanel(f"商店(金幣 {run.gold})", opts,
                                     choose, skip_label="離開"))

    reopen()


# ------------------------------------------------------------ 三個事件

def _open_event(ms, event_id: str, done) -> None:
    run = ms.run
    if event_id == "blacksmith":
        def smith_pick(pos):
            run.deck[:] = blacksmith_upgrade(run.deck, pos)
            done()

        def choose(i):
            if i is None:
                done()
                return
            _deck_grid(ms, "鐵匠:選一張卡鍛造(費用 -1)",
                       lambda cid: get_card(cid).cost > 0,
                       lambda cid: "", smith_pick, "離開", done)
        ms.director.push(ChoicePanel("事件:鐵匠", [
            Option("免費鍛造", ["一張卡費用 -1", "(最低 0)"], BLUE),
        ], choose, skip_label="離開"))

    elif event_id == "poison_merchant":
        can_commit = any(get_card(c).kind == "attack" and not is_poison_card(c)
                         for c in run.deck)

        def commit_pick(pos):
            run.deck[:] = poison_merchant_commit(run.deck, pos)
            done()

        def choose(i):
            if i is None:
                done()
            elif i == 0:
                _deck_grid(ms, "淬毒的代價:失去一張非毒攻擊卡",
                           lambda cid: (get_card(cid).kind == "attack"
                                        and not is_poison_card(cid)),
                           lambda cid: "", commit_pick, "反悔離開", done)
            else:
                run.deck[:] = poison_merchant_sample(run.deck)
                done()
        ms.director.push(ChoicePanel("事件:毒藥商", [
            Option("淬毒", ["全部毒卡中毒 +1", "代價:失去一張非毒攻擊卡"],
                   PURPLE, can_commit),
            Option("試用品", ["獲得一張毒刃"], GREEN),
        ], choose, skip_label="離開"))

    else:  # old_warrior
        def choose(i):
            if i is None:
                done()
                return
            new_deck, gained = old_warrior_trade(run.deck, run.rng)
            run.deck[:] = new_deck
            ms.director.push(ChoicePanel(
                "老戰士把卡塞給你", [card_option(gained)],
                lambda _i: done(), skip_label="收下"))
        ms.director.push(ChoicePanel("事件:老戰士", [
            Option("以防禦換攻擊", ["移除一張防禦", "換一張隨機攻擊卡"],
                   RED, "defend" in run.deck),
        ], choose, skip_label="離開"))
