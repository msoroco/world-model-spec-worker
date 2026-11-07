"""Independent structural audit of twelve unselected C111294 policy drafts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CASES = {"below_80_mph": 75.0, "inside_80_mph": 79.5,
         "above_80_mph": 85.0}
CHANGES = {"primary": {}, "fallback1": {"speed_pid_kp": 0.55},
           "fallback2": {"steering_lookahead_m": 11.0},
           "fallback3": {"brake_pid_kp": 0.50}}
METRICS = {"fallback1": ("approach_speed_shortfall_mph", 0.75),
           "fallback2": ("max_lane_center_error_m", 0.35),
           "fallback3": ("peak_speed_overshoot_mph", 0.75)}


def main() -> None:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    assert {c["case_id"].split("__")[-1]: c["requested_setting"]
            for c in plan["cases"]} == CASES
    rows = json.loads((ROOT / "draft-candidates.json").read_text())
    assert len(rows) == 12
    assert {(r["case_id"].split("__")[-1], r["candidate"]) for r in rows} == {
        (case, candidate) for case in CASES for candidate in CHANGES}
    road_hash = hashlib.sha256((ROOT / "draft-fixtures/road.xodr").read_bytes()).hexdigest()
    assert road_hash == "bc708461e9ccb79fef6df587b5e13189197a2cc0e31c535a5edbe374fe45327e"
    common_keys = ("law_id", "cell_id", "actor", "comparison_variable",
                   "fixed_authored_road", "fixed_other_actor_route")
    for case, mph in CASES.items():
        variants = {r["candidate"]: r for r in rows
                    if r["case_id"].endswith("__" + case)}
        primary = variants["primary"]
        assert primary["requested_setting_mph"] == mph
        assert primary["changed_knobs"] == {}
        for name, row in variants.items():
            assert row["status"] == "unselected_draft" and not row["physical_effect_verified"]
            assert row["requested_setting_mph"] == mph
            assert all(row[key] == primary[key] for key in common_keys)
            assert row["changed_knobs"] == CHANGES[name]
            assert {k: v for k, v in row["knobs"].items()
                    if primary["knobs"].get(k) != v} == CHANGES[name]
            if name == "primary":
                assert row["fallback_trigger"] is None
            else:
                metric, threshold = METRICS[name]
                trigger = row["fallback_trigger"]
                assert (trigger["metric"], trigger["threshold"], trigger["op"]) == (
                    metric, threshold, ">")
    print(json.dumps({"passed": True, "independent_audit": True,
                      "unselected_plans": 12, "cases": 3,
                      "authored_road_sha256": road_hash,
                      "selected": False, "exact_offline_proven": False}, sort_keys=True))


if __name__ == "__main__":
    main()
