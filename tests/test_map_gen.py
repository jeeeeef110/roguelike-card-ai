"""tests/test_map_gen.py — 地圖生成:性質測試為主

生成器最容易出「特定 seed 才踩到」的 bug,所以不挑個別案例,
直接 1000 個 seed 全部過 validate_map(生成器與驗證器分開寫,互相檢查)。
"""
from core.map_gen import N_LAYERS, generate_map, validate_map


def test_thousand_seeds_all_valid():
    for seed in range(1000):
        problems = validate_map(generate_map(seed))
        assert not problems, f"seed={seed}: {problems}"


def test_same_seed_same_map():
    assert generate_map(42) == generate_map(42)


def test_different_seeds_differ():
    # 不要求全不同,但 50 個 seed 至少 45 張不同(生成器沒退化成常數)
    maps = {repr(generate_map(s)) for s in range(50)}
    assert len(maps) >= 45


def test_battle_nodes_have_enemies_others_none():
    m = generate_map(7)
    for row in m.layers:
        for n in row:
            if n.node_type in ("battle", "elite", "boss"):
                assert n.enemy_id is not None
            else:
                assert n.enemy_id is None


def test_boss_is_corrupted_knight():
    for seed in range(20):
        m = generate_map(seed)
        assert m.layers[-1][0].enemy_id == "corrupted_knight"


def test_node_type_distribution_sane():
    """中段層的型別分佈:戰鬥為主(>40%),商店存在但稀少(1%–20%)。"""
    counts: dict[str, int] = {}
    total = 0
    for seed in range(300):
        m = generate_map(seed)
        for row in m.layers[1:8]:
            for n in row:
                counts[n.node_type] = counts.get(n.node_type, 0) + 1
                total += 1
    assert counts["battle"] / total > 0.40
    assert 0.01 < counts.get("shop", 0) / total < 0.20
    assert counts.get("rest", 0) > 0 and counts.get("event", 0) > 0


def test_children_helper_matches_edges():
    m = generate_map(3)
    n = m.layers[0][0]
    kids = m.children(n)
    assert all(k.layer == 2 for k in kids) and len(kids) >= 1
