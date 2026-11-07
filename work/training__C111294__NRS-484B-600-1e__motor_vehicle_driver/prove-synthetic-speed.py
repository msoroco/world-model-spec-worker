"""Materialize three controlled, unselected saved speed diagnostics."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "native"))
import geometry
import measure_speed


def main() -> None:
    out = ROOT / "draft-fixtures"
    out.mkdir(exist_ok=True)
    geom = geometry.check()
    (out / "road.xodr").write_text(geometry.open_drive())
    (out / "geometry-check.json").write_text(json.dumps(geom, indent=2) + "\n")
    reports = {}
    for case, requested_mph in geometry.SPEED_MPH.items():
        raw = measure_speed.synthetic_fixture(requested_mph)
        source = out / f"{case}-synthetic-native-samples.jsonl"
        source.write_bytes(raw)
        receipt = measure_speed.measure(source, hashlib.sha256(raw).hexdigest())
        receipt.update({"case_id": f"{ROOT.name}__{case}",
                        "source_kind": "synthetic_cpu_fixture",
                        "requested_setting_mph": requested_mph,
                        "selected": False, "delivery_ready": False})
        (out / f"{case}-measurement.json").write_text(
            json.dumps(receipt, indent=2, sort_keys=True) + "\n")
        reports[case] = receipt
    common = ("ego_actor_id", "other_actor_id", "frames", "rate_hz",
              "uncertainty_mph", "statutory_value_mph", "velocity_source")
    if any({reports[c][key] for c in reports} != {reports[next(iter(reports))][key]}
           for key in common):
        raise ValueError("Controlled fixture context differs")
    if [reports[c]["measured_relation"] for c in geometry.SPEED_MPH] != [
            "measured_not_above_80_mph", "measured_not_above_80_mph",
            "measured_above_80_mph"]:
        raise ValueError("Unexpected synthetic relation")
    summary = {"passed": True, "selected": False, "delivery_ready": False,
               "source_kind": "synthetic_cpu_fixture",
               "controlled_variable": "derived_peak_mph",
               "fixed_context_fields": list(common),
               "cases": {c: {"source_sha256": r["source_sha256"],
                             "derived_peak_mph": r["derived_peak_mph"],
                             "measured_relation": r["measured_relation"]}
                         for c, r in reports.items()},
               "physical_native_capture_verified": False,
               "portable_compatibility_verified": False,
               "legal_verdict": None}
    (out / "synthetic-comparison.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    main()
