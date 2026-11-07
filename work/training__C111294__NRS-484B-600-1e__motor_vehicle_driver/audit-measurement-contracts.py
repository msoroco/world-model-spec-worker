"""Independent source reader for C111294 saved measurement contracts."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
EXPECTED = {"below_80_mph": 75.0, "inside_80_mph": 79.5,
            "above_80_mph": 85.0}
KEYS = {"subject_operation", "speed_relation", "unconditional_scope",
        "other_vehicle_context"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    plan = json.loads((ROOT / "case-plan.json").read_text())
    assert {c["case_id"].split("__")[-1]: c["requested_setting"]
            for c in plan["cases"]} == EXPECTED
    root = ROOT / "draft-fixtures/contracts"
    summary = json.loads((root / "proof-summary.json").read_text())
    assert summary["source_kind"] == "synthetic_cpu_fixture"
    assert not summary["selected"] and not summary["portable_compatibility_verified"]
    checked = {}
    for suffix, expected in EXPECTED.items():
        folder = root / suffix
        contract = json.loads((ROOT / f"draft-measurement-contract-{suffix}.json").read_text())
        report = json.loads((folder / "analysis-report.json").read_text())
        source = folder / "native_samples.jsonl"
        rows = [json.loads(line) for line in source.read_bytes().splitlines()]
        assert len(rows) == 480 and report["case_id"] == contract["case_id"]
        assert {r["output_key"] for r in contract["requirements"]} == KEYS
        assert set(report["measurements"]) == KEYS
        assert not report["selected"] and not report["accepted"]
        assert report["legal_verdict"] is None
        assert summary["cases"][suffix]["source_sha256"] == sha(source)
        assert all(row["source_kind"] == "synthetic_cpu_fixture" for row in rows)
        peak = max(math.sqrt(sum(v*v for v in row["ego_velocity_mps"]))
                   * 2.2369362920544 for row in rows)
        assert math.isclose(peak, expected, abs_tol=1e-7)
        value = report["measurements"]["speed_relation"]["value"]
        assert math.isclose(value["derived_peak_mph"], peak, abs_tol=1e-6)
        assert value["measured_relation"] == (
            "measured_above_80_mph" if expected > 80 else "measured_not_above_80_mph")
        assert report["measurements"]["subject_operation"]["value"]["control_frames"] == 480
        assert report["measurements"]["other_vehicle_context"]["value"]["observed_route_motion_m"] > 200
        for item in report["measurements"].values():
            for name, digest in item["sources"].items():
                assert sha(folder / name) == digest
        checked[suffix] = {"source_sha256": sha(source), "peak_mph": peak}
    print(json.dumps({"passed": True, "independent_reader": True,
                      "source_kind": "synthetic_cpu_fixture",
                      "selected": False, "cases": checked}, sort_keys=True))


if __name__ == "__main__":
    main()
