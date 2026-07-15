"""core/map_gen.py — 地圖生成(v2.2 §5.1,M2)

分層 DAG:10 層,每層 2–4 節點(第 1、10 層各 1 節點)。
約束(全部定案於 design.md §5.1):
- 第 1 層必為一般敵人、第 9 層必為休息點、第 10 層 Boss
- 商店不連續:任何一條路徑上不會出現相鄰兩層都走到商店
  (實作為:若某節點是商店,其所有子節點不是商店——比「路徑檢查」更強、
   更好測,且生成時零回溯)
- 連通性:每個節點至少一個父節點與一個子節點;從起點可達所有節點,
  所有節點可達 Boss

隨機性:注入 random.Random(seed),同 seed 同地圖(可重播/可測試)。
零外部依賴,不 import pygame、不 print。

資料表示:
    MapNode = (layer, index) 座標的節點,type 為 NODE_TYPES 之一
    GameMap.layers: list[list[MapNode]],GameMap.edges: {(座標): [子座標]}
"""
from __future__ import annotations

from random import Random
from typing import NamedTuple

NODE_TYPES = ("battle", "elite", "rest", "shop", "event")
N_LAYERS = 10          # 預設層數(generate_map 可指定 10–15)
ELITE_MIN_LAYER = 4    # 菁英不出現在前段

# 中段層的節點型別權重:戰鬥為主,其餘點綴;菁英僅深度 ≥ ELITE_MIN_LAYER
_TYPE_WEIGHTS = [("battle", 5), ("event", 2), ("shop", 1),
                 ("rest", 1), ("elite", 1)]

# 深度分池:前段只出入門怪,後段全池——同一輪冒險的前後段手感不同,
# 也讓「後面才學到的解法」(破甲、單發重擊)有登場舞台
_POOL_EARLY = ("giant_rat", "poison_spider")                       # 第 2–4 層
_POOL_LATE = ("giant_rat", "poison_spider", "stone_golem",
              "blood_bat", "berserker")                            # 第 5 層起
_POOL_ELITE = ("stone_golem", "blood_bat", "berserker")            # 菁英池


class MapNode(NamedTuple):
    layer: int          # 1..10
    index: int          # 該層內的序號 0..
    node_type: str      # NODE_TYPES 之一
    enemy_id: str | None  # battle/boss 節點的敵人,其餘 None


class GameMap(NamedTuple):
    layers: tuple            # tuple[tuple[MapNode, ...], ...],layers[0] 是第 1 層
    edges: dict              # {(layer, index): tuple[(layer+1, index), ...]}

    def node(self, layer: int, index: int) -> MapNode:
        return self.layers[layer - 1][index]

    def children(self, node: MapNode) -> tuple:
        return tuple(self.node(l, i) for l, i in self.edges[(node.layer, node.index)])


def _pick_type(rng: Random, parent_types: set[str], layer: int) -> str:
    """抽節點型別;父層有商店時排除商店(商店不連續);
    菁英僅在 ELITE_MIN_LAYER 之後出現。"""
    pool = [(t, w) for t, w in _TYPE_WEIGHTS
            if not (t == "shop" and "shop" in parent_types)
            and not (t == "elite" and layer < ELITE_MIN_LAYER)]
    total = sum(w for _, w in pool)
    r = rng.randrange(total)
    for t, w in pool:
        r -= w
        if r < 0:
            return t
    raise AssertionError("unreachable")


def _connect(rng: Random, n_from: int, n_to: int) -> list[list[int]]:
    """生成相鄰兩層的邊(from 每節點的子節點 index 列表),保證:
    每個 from 節點 ≥1 子、每個 to 節點 ≥1 父、邊不交叉(視覺整潔,
    也讓連通性檢查簡單:非遞減的 index 區間)。

    作法:把 to 的 index 切成 n_from 段有重疊的連續區間。"""
    # 每個 from 節點分到一個 [lo, hi] 區間;相鄰區間至少共享端點或相接
    cuts = sorted(rng.randint(0, n_to - 1) for _ in range(n_from - 1))
    edges = []
    lo = 0
    for i in range(n_from):
        hi = cuts[i] if i < n_from - 1 else n_to - 1
        hi = max(hi, lo)  # 區間至少含一個節點
        edges.append(list(range(lo, hi + 1)))
        lo = hi if rng.random() < 0.5 else min(hi + 1, n_to - 1)  # 重疊或相接
    return edges


def generate_map(seed: int, n_layers: int = N_LAYERS) -> GameMap:
    if not 10 <= n_layers <= 15:
        raise ValueError("n_layers 須在 10–15(MVP 10,完整版 15)")
    rng = Random(seed)
    sizes = [1] + [rng.randint(2, 4) for _ in range(n_layers - 2)] + [1]

    # 先鋪型別:固定約束層直接指定
    layers: list[list[MapNode]] = []
    edges: dict = {}
    parent_types_of: list[set[str]] = [set() for _ in range(n_layers + 1)]

    for li, size in enumerate(sizes, start=1):
        row: list[MapNode] = []
        for idx in range(size):
            if li == 1:
                t = "battle"
            elif li == n_layers - 1:
                t = "rest"          # Boss 前必有休息點
            elif li == n_layers:
                t = "boss"  # 特例:不在 NODE_TYPES,戰鬥的一種
            else:
                t = _pick_type(rng, parent_types_of[li], li)
            enemy = None
            if t == "battle":
                enemy = rng.choice(_POOL_EARLY if li <= 4 else _POOL_LATE)
            elif t == "elite":
                enemy = rng.choice(_POOL_ELITE)
            elif t == "boss":
                enemy = "corrupted_knight"
            row.append(MapNode(li, idx, t, enemy))
        layers.append(row)
        if li < n_layers:
            conn = _connect(rng, size, sizes[li])
            for idx, kids in enumerate(conn):
                edges[(li, idx)] = tuple((li + 1, k) for k in kids)
                # 商店不連續:把父型別傳給下一層(在型別決定前需要——
                # 但下一層型別還沒定,所以改為:先記父座標,下一層抽型別時查)
            # 記錄「下一層每個節點的父型別集合」
            for idx, kids in enumerate(conn):
                for k in kids:
                    parent_types_of[li + 1].add(row[idx].node_type)
    # 注意:parent_types_of 以「層」為粒度(整層的父型別聯集)。
    # 這比逐節點更保守:只要上一層存在商店,下一層整層都不出商店。
    # 換取的是生成零回溯;MVP 商店權重低,實測不影響商店出現率太多。
    edges[(n_layers, 0)] = ()
    return GameMap(tuple(tuple(r) for r in layers), edges)


def validate_map(m: GameMap) -> list[str]:
    """回傳違規清單(空 = 合法)。生成器的性質測試與防呆共用。"""
    problems = []
    n_layers = len(m.layers)
    if not 10 <= n_layers <= 15:
        problems.append(f"層數 {n_layers} 不在 10–15")
    if [n.node_type for n in m.layers[0]] != ["battle"]:
        problems.append("第 1 層必須是單一 battle")
    if any(n.node_type != "rest" for n in m.layers[-2]):
        problems.append("Boss 前一層必須全為 rest")
    if [n.node_type for n in m.layers[-1]] != ["boss"]:
        problems.append("最後一層必須是單一 boss")
    for row in m.layers:
        for n in row:
            if n.node_type == "elite" and n.layer < ELITE_MIN_LAYER:
                problems.append(f"{(n.layer, n.index)} 菁英過早出現")
    for row in m.layers[1:-1]:
        if not 2 <= len(row) <= 4:
            problems.append(f"第 {row[0].layer} 層節點數 {len(row)} 不在 2-4")
    # 連通性:每節點 ≥1 子(最後層除外);每節點 ≥1 父(第一層除外)
    has_parent = {(1, 0)}
    for row in m.layers[:-1]:
        for n in row:
            kids = m.edges.get((n.layer, n.index), ())
            if not kids:
                problems.append(f"{(n.layer, n.index)} 沒有子節點")
            for coord in kids:
                has_parent.add(coord)
            # 商店不連續(逐節點檢查,比生成用的層粒度更精確)
            if n.node_type == "shop":
                for l, i in kids:
                    if m.node(l, i).node_type == "shop":
                        problems.append(f"{(n.layer, n.index)} 商店連續")
    for row in m.layers[1:]:
        for n in row:
            if (n.layer, n.index) not in has_parent:
                problems.append(f"{(n.layer, n.index)} 沒有父節點")
    return problems
