"""sim/exp_mcts_tuning.py — 實驗 3:MCTS 調參對照(PROGRESS 待辦 #2)

因素:rollout policy(random/heuristic)× iterations(100/200/500)
戰場:石像兵(一般戰代表,MCTS 已知墊底)+ Boss 腐化騎士
用法:python3 -m sim.exp_mcts_tuning <cell名稱>   # 一次跑一格,結果附加到 results.txt
"""
import sys
import time

from agents.mcts import MCTSAgent
from sim.runner import run_many

CELLS = {
    # 名稱: (enemy, n, iterations, rollout)
    "golem_rand_200":  ("stone_golem", 100, 200, "random"),
    "golem_heur_200":  ("stone_golem", 100, 200, "heuristic"),
    "golem_heur_100":  ("stone_golem", 100, 100, "heuristic"),
    "boss_rand_200":   ("corrupted_knight", 60, 200, "random"),
    "boss_heur_200":   ("corrupted_knight", 60, 200, "heuristic"),
    "boss_heur_100":   ("corrupted_knight", 60, 100, "heuristic"),
    "boss_heur_500":   ("corrupted_knight", 60, 500, "heuristic"),
    "boss_rand_500":   ("corrupted_knight", 60, 500, "random"),
}


def main() -> None:
    name = sys.argv[1]
    enemy, n, iters, rollout = CELLS[name]
    t0 = time.perf_counter()
    s = run_many(lambda i: MCTSAgent(iterations=iters, seed=i, rollout=rollout),
                 enemy, n)
    dt = (time.perf_counter() - t0) / n
    line = (f"{name:<16} enemy={enemy:<17} n={n} iters={iters} rollout={rollout:<9} "
            f"win={s['win_rate']:.1%} turns={s['avg_turns']:.1f} "
            f"hp_left={s['avg_hp_left_on_win']:.1f} {dt:.2f}s/場")
    print(line)
    with open("sim/results.txt", "a", encoding="utf-8") as f:
        f.write(line + "\n")


if __name__ == "__main__":
    main()
