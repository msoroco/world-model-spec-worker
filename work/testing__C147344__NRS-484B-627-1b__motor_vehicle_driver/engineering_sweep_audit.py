"""Audit six released original speed-sampling attempts without a legal verdict."""
from __future__ import annotations

import json
import math
from pathlib import Path

from build_engineering_sweep_preview import AXES
from engineering_sweep_station import plan_engineering
from reviewed_scene import ASSIGNMENT, _linked


def audit(root: Path, site_ref: dict, receipts: list[dict]) -> dict:
    root = Path(root).resolve()
    _linked(root, site_ref)
    if not isinstance(receipts, list) or len(receipts) != 6:
        raise ValueError("six original engineering sweep attempts required")
    by_case = {row.get("case_id"): row for row in receipts if isinstance(row, dict)}
    expected = {ASSIGNMENT + f"__{axis}-{rank:04d}"
                for axis in AXES for rank in range(3)}
    if len(by_case) != 6 or set(by_case) != expected:
        raise ValueError("six distinct exact engineering cases required")
    traces = set()
    trace_ids = set()
    observations = {}
    scenes = {}
    for case_id in expected:
        receipt = by_case[case_id]
        if (receipt.get("source_kind") != "original_native_attempt" or
                receipt.get("owner_released") is not True or
                receipt.get("diagnostic_fixture") is True or
                receipt.get("native_process_exit_code") != 0 or
                receipt.get("site_sha256") != site_ref["sha256"] or
                not receipt.get("original_trace_id")):
            raise ValueError("released original sweep provenance required")
        path = _linked(root, receipt.get("trace_ref"))
        trace = json.loads(path.read_text(encoding="utf-8"))
        rows = trace.get("frames")
        if (trace.get("case_id") != case_id or
                trace.get("diagnostic_fixture") is True or
                trace.get("original_trace_id") != receipt["original_trace_id"] or
                not isinstance(rows, list) or len(rows) != 900 or
                [row.get("frame") for row in rows] != list(range(900)) or
                [row.get("time_s") for row in rows] != [i / 20 for i in range(900)]):
            raise ValueError("complete original 20 Hz sweep trace required")
        field = "ego_speed_mps" if "__impediment-" in case_id else "slower_vehicle_speed_mps"
        speeds = [row.get(field) for row in rows]
        if any(type(value) not in (int, float) or not math.isfinite(value) or value < 0
               for value in speeds):
            raise ValueError("original speed readback missing")
        scenes[case_id] = plan_engineering(root, site_ref, case_id)
        observations[case_id] = sum(speeds) / len(speeds)
        traces.add(receipt["trace_ref"]["sha256"])
        trace_ids.add(receipt["original_trace_id"])
    if len(traces) != 6 or len(trace_ids) != 6:
        raise ValueError("original sweep traces reused")
    comparisons = []
    for axis in AXES:
        ids = [ASSIGNMENT + f"__{axis}-{rank:04d}" for rank in range(3)]
        selected = [scenes[case_id] for case_id in ids]
        target_role = "ego" if axis == "impediment" else "slower_vehicle"
        actors = [{a["role"]: a for a in scene["actors"]} for scene in selected]
        for role in actors[0]:
            for field in ("lane_id", "station_m", "target_speed_mps"):
                if role == target_role and field == "target_speed_mps":
                    continue
                if any(group[role][field] != actors[0][role][field] for group in actors[1:]):
                    raise ValueError("sweep fixed actor control changed")
        for field in ("site_sha256", "map_sha256", "cameras", "hz", "frames",
                      "rightmost_lane_id"):
            if any(scene[field] != selected[0][field] for scene in selected[1:]):
                raise ValueError("sweep fixed site or capture changed")
        comparisons.append({
            "comparison_id": axis + "_engineering_speed",
            "case_ids": ids,
            "requested_setpoints_mps": [s["engineering_setpoint"]["requested_speed_mps"]
                                        for s in selected],
            "observed_mean_speed_mps": [observations[case_id] for case_id in ids],
            "fixed_controls_verified": True,
            "realized_order_and_legal_effect": "requires independent review",
        })
    return {"format": "c147344-engineering-sweep-audit-v1",
            "site_sha256": site_ref["sha256"], "comparisons": comparisons,
            "physical_acceptance": False, "legal_verdict": None}


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--site-ref", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve().is_relative_to(args.authority_root.resolve()):
        raise ValueError("fresh sweep audit outside original source root required")
    site = json.loads(args.site_ref.read_text(encoding="utf-8"))
    receipts = [json.loads(path.read_text(encoding="utf-8")) for path in args.receipt]
    result = audit(args.authority_root, site, receipts)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
