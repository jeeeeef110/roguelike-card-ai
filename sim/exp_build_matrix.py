"""sim/exp_build_matrix.py — 實驗 4:5 build × 代理勝率矩陣(design.md §6.2)

戰場:Boss 腐化騎士(唯一能拉開勝率差的敵人,PROGRESS 實驗 1 結論)。
每格 = 一個 (build, agent) 組合,結果附加到 sim/results_matrix.txt。
用法:python3 -m sim.exp_build_matrix <build> <agent> [n]
"""
import sys
import time

from agents.expectimax import ExpectimaxAgent
from agents.mcts import MCTSAgent
from agents.rule_based import RuleBasedAgent
from sim.decks import BUILD_DECKS
from sim.runner import run_many

AGENTS = {
    "rule": lambda i: RuleBasedAgent(),
    "expectimax": lambda i: ExpectimaxAgent(depth=2, samples=3, seed=i),
    "mcts": lambda i: MCTSAgent(iterations=200, seed=i, rollout="heuristic"),
}
DEFAULT_N = {"rule": 500, "expectimax": 100, "mcts": 60}


def main() -> None:
    build, agent = sys.argv[1], sys.argv[2]
    n = int(sys.argv[3]) if len(sys.argv) > 3 else DEFAULT_N[agent]
    t0 = time.perf_counter()
    s = run_many(AGENTS[agent], "corrupted_knight", n,
                 deck=BUILD_DECKS[build])
    dt = (time.perf_counter() - t0) / n
    line = (f"{build:<12}{agent:<12} n={n:<4} win={s['win_rate']:.1%} "
            f"turns={s['avg_turns']:.1f} hp_left={s['avg_hp_left_on_win']:.1f} "
            f"{dt:.2f}s/場")
    print(line)
    with open("sim/results_matrix.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")


if __name__ == "__main__":
    main()
