"""run_tests.py — 無網路環境的測試執行器

有 pytest 就用 pytest(python -m pytest tests/ -v);沒有時本腳本用
tools_offline/ 裡的最小替身跑同一批測試(替身放子資料夾,避免遮蔽真 pytest)。"""
import importlib
import sys
import traceback

try:
    import pytest  # noqa: F401  # 真 pytest 存在就不動 path
except ModuleNotFoundError:
    sys.path.append("tools_offline")

MODULES = [
    "tests.test_models", "tests.test_cards", "tests.test_engine",
    "tests.test_enemies", "tests.test_boss", "tests.test_agents",
    "tests.test_expectimax", "tests.test_mcts", "tests.test_map_gen", "tests.test_events", "tests.test_run", "tests.test_variety", "tests.test_potions", "tests.test_meta", "tests.test_ui_math",
]


def run() -> int:
    total_pass = total_fail = 0
    for mod_name in MODULES:
        m = importlib.import_module(mod_name)
        for name in sorted(d for d in dir(m) if d.startswith("test_")):
            fn = getattr(m, name)
            cases = [((), "")]
            if hasattr(fn, "_parametrize"):
                argnames, argvalues = fn._parametrize
                names = [a.strip() for a in argnames.split(",")]
                cases = []
                for v in argvalues:
                    args = (v,) if len(names) == 1 else tuple(v)
                    cases.append((args, f"[{args}]"))
            for args, label in cases:
                try:
                    fn(*args)
                    total_pass += 1
                except Exception:
                    total_fail += 1
                    print(f"FAIL {mod_name}.{name}{label}")
                    traceback.print_exc()
    print(f"{total_pass} passed, {total_fail} failed")
    return 1 if total_fail else 0


if __name__ == "__main__":
    sys.exit(run())
