"""Build small textual synthetic diagnostics; these are never original evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
REFERENCE = REPO / "work/testing__C412262__NRS-484B-493__motor_vehicle_driver/cases/park_left_notice/diagnostic-scaffold.json"
OLD_CASE = "testing__C412262__NRS-484B-493__motor_vehicle_driver__park_left_notice"
VIEWS = ["overview", "approach", "reference_corner", "driver_reference"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    reference = json.loads(REFERENCE.read_text())
    for case in plan["cases"]:
        case_id = case["case_id"]
        folder = ROOT / "cases" / case["variant"]
        sources = folder / "diagnostic-sources"
        sources.mkdir(parents=True, exist_ok=True)
        width = [12.0, 12.0] if case["highway_width_request"] == "wider" else [8.0, 8.0]
        context = {"assignment_id": plan["assignment_id"], "case_id": case_id,
                   "source_kind": "synthetic_diagnostic_fixture",
                   "highway_width_request": case["highway_width_request"],
                   "device_request": case["device_request"],
                   "activity_request": case["activity_request"],
                   "parking_location_request": case["parking_location_request"],
                   "highway_status": "diagnostic_review_pending",
                   "device_status": case["device_request"],
                   "activity_status": case["activity_request"],
                   "full_highway_width_profile_m": width,
                   "highway_boundary_xy_m": [[0, -4], [20, -4], [20, 4], [0, 4]],
                   "device_extent_xy_m": [[0, -2], [20, -2], [20, 2], [0, 2]]}
        for name in ("dedication_sha256", "public_access_sha256", "person_identity_sha256",
                     "vehicle_identity_sha256"):
            context[name] = "diagnostic-fixed-source"
        write(sources / "context.json", context)
        if case["parking_location_request"] == "off_highway":
            body = [[9, 5], [11, 5], [11, 6], [9, 6]]
        elif case["device_request"] == "outside_extent":
            body = [[9, 2.5], [11, 2.5], [11, 3], [9, 3]]
        else:
            body = [[9, -0.5], [11, -0.5], [11, 0.5], [9, 0.5]]
        speed = 2.0 if case["activity_request"] == "travel" else 0.0
        trace = sources / "original-trace.jsonl"
        trace.write_text("".join(json.dumps({"frame": index, "time_s": index / 20,
                    "vehicle_center_xy_m": [10, 0], "vehicle_body_polygon_xy_m": body,
                    "speed_mps": speed}, sort_keys=True) + "\n" for index in range(9)))
        write(sources / "cameras.json", {"frame_count": 9,
             "synthetic_diagnostic_fixture": True, "views": VIEWS})
        write(sources / "receipt.json", {"assignment_id": plan["assignment_id"],
             "case_id": case_id, "source_kind": "synthetic_diagnostic_fixture",
             "frame_count": 9,
             "context_sha256": sha(sources / "context.json"),
             "trace_sha256": sha(trace),
             "camera_manifest_sha256": sha(sources / "cameras.json")})
        scaffold = json.loads(json.dumps(reference).replace(OLD_CASE, case_id))
        scaffold["files"]["fixture-provenance.json"] = json.dumps({
             "diagnostic_fixture": True, "frames": 9,
             "scope": "Synthetic software compatibility only; no original physical or legal evidence."}, sort_keys=True) + "\n"
        spec_path = folder / "diagnostic-scaffold.json"
        write(spec_path, scaffold)
        recipe = {"format": "worker-fixture-recipe", "generator": {
            "source": spec_path.relative_to(REPO).as_posix(), "sha256": sha(spec_path)},
            "sources": [{"path": name, "source": (sources / name).relative_to(REPO).as_posix(),
                         "sha256": sha(sources / name)} for name in
                        ("cameras.json", "context.json", "original-trace.jsonl", "receipt.json")]}
        write(folder / "fixture-recipe.json", recipe)


if __name__ == "__main__":
    build()
