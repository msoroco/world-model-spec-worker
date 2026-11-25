"""Check all four hash-bound diagnostic recipes against the pinned runtime."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))

from worker_exchange.fixture_recipe import inspect


for case in ("nearest_view_hold", "nearest_view_continue", "nearest_view_clear",
             "active_signal_exception"):
    recipe, sources = inspect(ROOT, HERE / ("diagnostic-" + case + "-recipe.json"))
    print(case, len(sources), "sources", recipe["generator"]["source"])
