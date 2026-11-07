"""Independent reader of saved C111294 synthetic source and measurement receipts."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "draft-fixtures"
EXPECTED = {"below_80_mph": 75.0, "inside_80_mph": 79.5,
            "above_80_mph": 85.0}
MPS_TO_MPH = 2.2369362920544


def main() -> None:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    assert plan["source_law_text"].endswith("greater than 80 miles per hour.")
    assert {case["case_id"].split("__")[-1]: case["requested_setting"]
            for case in plan["cases"]} == EXPECTED
    summary = json.loads((OUT / "synthetic-comparison.json").read_text())
    assert summary["selected"] is False and summary["delivery_ready"] is False
    assert summary["portable_compatibility_verified"] is False
    fixed_sources = []
    audited = {}
    for case, expected in EXPECTED.items():
        source = OUT / f"{case}-synthetic-native-samples.jsonl"
        raw = source.read_bytes()
        rows = [json.loads(line) for line in raw.splitlines()]
        receipt = json.loads((OUT / f"{case}-measurement.json").read_text())
        assert len(rows) == 480
        assert hashlib.sha256(raw).hexdigest() == receipt["source_sha256"]
        assert receipt["source_sha256"] == summary["cases"][case]["source_sha256"]
        assert [r["frame"] for r in rows] == list(range(480))
        assert all(abs(r["t_s"] - i / 20) < 1e-8 for i, r in enumerate(rows))
        assert all(r["source_kind"] == "synthetic_cpu_fixture" for r in rows)
        peak = max(math.hypot(*r["ego_velocity_mps"][:2]) * MPS_TO_MPH
                   for r in rows)
        assert math.isclose(peak, expected, abs_tol=1e-7)
        assert math.isclose(receipt["derived_peak_mph"], peak, abs_tol=1e-6)
        assert receipt["measured_relation"] == (
            "measured_above_80_mph" if expected > 80 else "measured_not_above_80_mph")
        assert receipt["legal_verdict"] is None
        # Compare the full other-actor trajectory and all fixed identity,
        # provenance, rate and timing fields, not only summary labels.
        fixed_sources.append([(r["frame"], r["t_s"], r["ego_actor_id"],
                               r["other_actor_id"], r["ego_role"], r["other_role"],
                               r["ego_blueprint"], r["other_blueprint"],
                               r["other_position_m"], r["source_kind"])
                              for r in rows])
        audited[case] = {"source_sha256": receipt["source_sha256"],
                         "derived_peak_mph": receipt["derived_peak_mph"]}
    assert fixed_sources[0] == fixed_sources[1] == fixed_sources[2]
    assert len({v["derived_peak_mph"] for v in audited.values()}) == 3
    print(json.dumps({"passed": True, "independent_reader": True,
                      "fixed_other_actor_and_capture": True,
                      "source_kind": "synthetic_cpu_fixture",
                      "selected": False, "delivery_ready": False,
                      "cases": audited}, sort_keys=True))


if __name__ == "__main__":
    main()
