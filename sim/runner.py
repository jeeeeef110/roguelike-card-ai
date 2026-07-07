"""sim/runner.py — headless 模擬器(W2 雛形)

跑 N 場「代理 vs 敵人」,輸出勝率/平均回合/平均剩餘 HP。
之後的 A/B 平衡實驗與三版代理勝率矩陣都建立在這上面。

用法:
    python3 -m sim.runner                          # 兩個代理 × 三隻敵人 × 500 場
    python3 -m sim.runner --agent rule --n 1000
    python3 -m sim.runner --enemy giant_rat --seed 7

公平性:第 i 場戰鬥用 seed = base_seed + i。同一組 seed 下換代理,
抽牌序完全相同(代理自帶 RNG,不碰 state.rng),差異全歸因於決策。
"""
import argparse
import time

from agents.base import Agent, RandomAgent
from agents.expectimax import ExpectimaxAgent
from agents.mcts import MCTSAgent
from agents.rule_based import RuleBasedAgent
from core.cards import PLAYER_HP, STARTING_DECK
from core.enemies import ENEMIES, enemy_ai, make_enemy
from core.engine import apply_action, start_battle
from core.models import GameState, PlayerState

MAX_TURNS = 100  # 超過視為敗(防呆:雙方都打不死對方的殭局)


def run_battle(agent: Agent, enemy_id: str, seed: int,
               deck: list[str] | None = None) -> dict:
    """跑一場,回傳 {win, turns, hp_left}。"""
    p = PlayerState(hp=PLAYER_HP, max_hp=PLAYER_HP,
                    deck=list(deck or STARTING_DECK))
    state = GameState(p, make_enemy(enemy_id), seed=seed)
    start_battle(state, enemy_ai)
    while not state.battle_over and state.turn <= MAX_TURNS:
        apply_action(state, agent.choose_action(state), enemy_ai)
    return {
        "win": state.battle_over and state.player_won,
        "turns": state.turn,
        "hp_left": max(0, state.player.hp),
    }


def run_many(make_agent, enemy_id: str, n: int, base_seed: int = 0,
             deck: list[str] | None = None) -> dict:
    """跑 n 場(每場新代理、遞增 seed),回傳彙總統計。"""
    results = [run_battle(make_agent(i), enemy_id, base_seed + i, deck)
               for i in range(n)]
    wins = [r for r in results if r["win"]]
    return {
        "n": n,
        "win_rate": len(wins) / n,
        "avg_turns": sum(r["turns"] for r in results) / n,
        "avg_hp_left_on_win": (sum(r["hp_left"] for r in wins) / len(wins)
                               if wins else 0.0),
    }


AGENTS = {
    "random": lambda i: RandomAgent(seed=i),
    "rule": lambda i: RuleBasedAgent(),
    "expectimax": lambda i: ExpectimaxAgent(depth=2, samples=3, seed=i),
    "mcts": lambda i: MCTSAgent(iterations=200, seed=i),
}


def main() -> None:
    ap = argparse.ArgumentParser(description="headless 對戰模擬")
    ap.add_argument("--agent", choices=[*AGENTS, "all"], default="all")
    ap.add_argument("--enemy", choices=[*ENEMIES, "all"], default="all")
    ap.add_argument("--n", type=int, default=500)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    agent_names = list(AGENTS) if args.agent == "all" else [args.agent]
    enemy_ids = list(ENEMIES) if args.enemy == "all" else [args.enemy]

    print(f"{'代理':<12}{'敵人':<16}{'勝率':>8}{'平均回合':>10}{'勝場剩HP':>10}")
    print("-" * 56)
    for name in agent_names:
        for enemy_id in enemy_ids:
            t0 = time.perf_counter()
            s = run_many(AGENTS[name], enemy_id, args.n, args.seed)
            dt = time.perf_counter() - t0
            print(f"{name:<12}{enemy_id:<16}{s['win_rate']:>7.1%}"
                  f"{s['avg_turns']:>10.1f}{s['avg_hp_left_on_win']:>10.1f}"
                  f"   ({args.n} 場 {dt:.1f}s)")


if __name__ == "__main__":
    main()
