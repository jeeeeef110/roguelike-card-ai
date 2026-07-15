"""sim/make_charts.py — 從 results 檔產出備審報告圖表(PNG)

圖 1:MCTS rollout policy × iterations 對 Boss 的勝率(調參結論圖)
圖 2:5 build × 3 代理勝率矩陣熱圖(設計與演算法共同演化的核心圖)
用法:python3 -m sim.make_charts   (讀 sim/results.txt 與 sim/results_matrix.txt)
"""
import re
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

matplotlib.rcParams["font.sans-serif"] = [
    "Noto Sans CJK TC", "Noto Sans CJK SC", "PingFang TC",
    "Microsoft JhengHei", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

OUT = Path("docs/charts")


def _parse(path: str) -> list[dict]:
    rows = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        m = re.findall(r"(\w+)=([\w.%]+)", line)
        d = dict(m)
        d["_head"] = line.split()[0:2]
        rows.append(d)
    return rows


def chart_tuning() -> None:
    rows = [r for r in _parse("sim/results.txt")
            if r.get("enemy") == "corrupted_knight"]
    series: dict[str, list[tuple[int, float]]] = {"random": [], "heuristic": []}
    for r in rows:
        series[r["rollout"]].append(
            (int(r["iters"]), float(r["win"].rstrip("%"))))
    fig, ax = plt.subplots(figsize=(7, 4.5))
    styles = {"random": ("tab:gray", "o", "random rollout"),
              "heuristic": ("tab:red", "s", "heuristic rollout (eps-greedy static score)")}
    for key, pts in series.items():
        pts.sort()
        color, marker, label = styles[key]
        ax.plot([p[0] for p in pts], [p[1] for p in pts],
                marker=marker, color=color, label=label, linewidth=2)
    ax.axhline(98, color="tab:blue", linestyle="--", linewidth=1,
               label="Expectimax (d2s3) = 98%")
    ax.set_xlabel("MCTS iterations")
    ax.set_ylabel("Boss win rate (%)")
    ax.set_title("MCTS tuning: rollout quality vs iterations (Boss, 60 battles/point)")
    ax.set_xticks([100, 200, 500])
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(OUT / "mcts_tuning.png", dpi=150)
    print("寫出", OUT / "mcts_tuning.png")


def chart_matrix() -> None:
    rows = _parse("sim/results_matrix.txt")
    builds = ["poison", "strength", "block", "vulnerable", "tempo"]
    agents = ["rule", "expectimax", "mcts"]
    zh_b = {"poison": "Poison", "strength": "Strength", "block": "Block",
            "vulnerable": "Vulnerable", "tempo": "Tempo"}
    zh_a = {"rule": "Rule-based", "expectimax": "Expectimax", "mcts": "MCTS"}
    grid = [[float("nan")] * len(builds) for _ in agents]
    ns = [[0] * len(builds) for _ in agents]
    for r in rows:
        b, a = r["_head"]
        if b in builds and a in agents:
            grid[agents.index(a)][builds.index(b)] = float(r["win"].rstrip("%"))
            ns[agents.index(a)][builds.index(b)] = int(r["n"])
    fig, ax = plt.subplots(figsize=(8, 4))
    im = ax.imshow(grid, cmap="RdYlGn", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(builds)), [zh_b[b] for b in builds])
    ax.set_yticks(range(len(agents)), [zh_a[a] for a in agents])
    for i in range(len(agents)):
        for j in range(len(builds)):
            v = grid[i][j]
            if v == v:  # not nan
                label = f"{v:.0f}%"
                if ns[i][j] < 30:
                    label += f"\n(n={ns[i][j]}⚠)"
                ax.text(j, i, label, ha="center", va="center",
                        fontsize=10, fontweight="bold")
    ax.set_title("5 builds x 3 agents: Boss win-rate matrix (Corrupted Knight)")
    fig.colorbar(im, label="win rate (%)")
    fig.tight_layout()
    fig.savefig(OUT / "build_matrix.png", dpi=150)
    print("寫出", OUT / "build_matrix.png")


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    chart_tuning()
    chart_matrix()
