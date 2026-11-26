"""Check six original sweep attempts for source identity and control isolation.

Measured speeds are reported for independent physical and legal review. This
audit does not assert impediment, passing necessity, or a legal speed cutoff.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

from reviewed_scene import _linked
from source_gated_sweeps import prepare


def audit(root: Path, site_ref: dict, ranges_ref: dict, receipts: list[dict]) -> dict:
    root = Path(root).resolve()
    packet = prepare(root, site_ref, ranges_ref)
    scenes = {scene["case_id"]: scene for scene in packet["scenes"]}
    by_case = {receipt.get("case_id"): receipt for receipt in receipts
               if isinstance(receipt, dict)}
    if len(receipts) != 6 or len(by_case) != 6 or set(by_case) != set(scenes):
        raise ValueError("six exact distinct original sweep attempts required")
    rows_by_case = {}
    trace_ids = set()
    trace_hashes = set()
    for case_id, scene in scenes.items():
        receipt = by_case[case_id]
        if (receipt.get("source_kind") != "original_native_attempt" or
                receipt.get("owner_released") is not True or
                receipt.get("diagnostic_fixture") is True or
                receipt.get("native_process_exit_code") != 0 or
                receipt.get("site_sha256") != packet["site_sha256"] or
                receipt.get("ranges_sha256") != packet["ranges_sha256"] or
                not receipt.get("original_trace_id")):
            raise ValueError("reviewed original sweep provenance missing")
        trace_ref = receipt.get("trace_ref")
        trace_path = _linked(root, trace_ref)
        trace = json.loads(trace_path.read_text(encoding="utf-8"))
        rows = trace.get("frames")
        if (trace.get("case_id") != case_id or trace.get("diagnostic_fixture") is True or
                trace.get("original_trace_id") != receipt["original_trace_id"] or
                not isinstance(rows, list) or len(rows) != 900 or
                [row.get("frame") for row in rows] != list(range(900)) or
                [row.get("time_s") for row in rows] != [i / 20 for i in range(900)]):
            raise ValueError("complete original 20 Hz speed readback required")
        field = scene["sweep"]["original_readback_field"]
        speeds = [row.get(field) for row in rows]
        if any(type(v) not in (int, float) or not math.isfinite(v) or v < 0
               for v in speeds):
            raise ValueError("original numeric speed readback missing")
        trace_ids.add(receipt["original_trace_id"])
        trace_hashes.add(trace_ref["sha256"])
        rows_by_case[case_id] = speeds
    if len(trace_ids) != 6 or len(trace_hashes) != 6:
        raise ValueError("sweep attempts or original motion packets reused")
    comparisons = []
    for axis_name in ("impediment", "passing_necessity"):
        selected = [scene for scene in packet["scenes"]
                    if scene["sweep"]["axis_id"] == axis_name]
        selected.sort(key=lambda scene: scene["sweep"]["requested_setpoint"])
        actors = [{actor["role"]: actor for actor in scene["actors"]} for scene in selected]
        target = "ego" if axis_name == "impediment" else "slower_vehicle"
        for role in actors[0]:
            for field in ("lane_id", "station_m", "target_speed_mps"):
                if role == target and field == "target_speed_mps":
                    continue
                if any(group[role][field] != actors[0][role][field] for group in actors[1:]):
                    raise ValueError("sweep fixed actor control differs")
        for field in ("site_sha256", "map_sha256", "cameras", "hz", "frames",
                      "rightmost_lane_id"):
            if any(scene[field] != selected[0][field] for scene in selected[1:]):
                raise ValueError("sweep fixed source or capture differs")
        comparisons.append({"comparison_id": axis_name + "_speed_sweep",
                            "case_ids": [scene["case_id"] for scene in selected],
                            "requested_setpoints_mps": [scene["sweep"]["requested_setpoint"]
                                                        for scene in selected],
                            "observed_mean_speed_mps": [sum(rows_by_case[scene["case_id"]]) / 900
                                                        for scene in selected],
                            "requested_control_isolated": True,
                            "realized_order_and_legal_effect": "requires independent review"})
    return {"format": "c147344-original-sweep-comparison-v1",
            "site_sha256": packet["site_sha256"], "ranges_sha256": packet["ranges_sha256"],
            "comparisons": comparisons, "physical_acceptance": False,
            "legal_impediment_or_exception": "unresolved"}
