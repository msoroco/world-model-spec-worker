"""Create small synthetic stop-source recipes for software checks only."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from stop_sign_branch import ASSIGNMENT, CASES


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = ROOT / "cases/yield_slow_hazard/diagnostic-scaffold.json"
OLD_CASE = ASSIGNMENT + "__yield_slow_hazard"


def raw(value):
    return json.dumps(value, indent=2, sort_keys=True) + "\n"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(data)
    return sha(data.encode())


def build():
    original = BASE.read_text()
    for case_id, response in CASES.items():
        suffix = case_id.removeprefix(ASSIGNMENT + "__")
        folder = ROOT / "cases" / suffix
        source = folder / "diagnostic-sources"
        source.mkdir(parents=True, exist_ok=True)
        scaffold = folder / "diagnostic-scaffold.json"
        write(scaffold, original.replace(OLD_CASE, case_id))
        context = {"assignment_id": ASSIGNMENT, "case_id": case_id,
                   "source_kind": "synthetic_diagnostic_fixture", "control": "stop_sign",
                   "cell_id": "C158190", "planned_response": response,
                   "stop_line_present": False, "near_crosswalk_present": False,
                   "sidewalk_derived_crosswalk_present": False,
                   "police_control_active": False, "traffic_signal_control_active": False,
                   "original_reviewed_site_available": False,
                   "legal_hazard_judgment": None}
        context_sha = write(source / "context.json", raw(context))
        rows = []
        for index in range(9):
            rows.append({"case_id": case_id, "frame": index, "time_s": index / 20,
                         "source_kind": "synthetic_diagnostic_fixture",
                         "ego_speed_mps": 0.0 if index in (3, 4) else 2.0,
                         "ego_within_intersection": index in (6, 7),
                         "distance_to_intersection_m": max(0.0, 6.0 - index),
                         "through_vehicles": [{"id": "synthetic-through", "through_highway": True,
                                               "distance_to_conflict_m": 10.0 - index,
                                               "speed_mps": 4.0}]})
        trace_sha = write(source / "original-trace.jsonl",
                          "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows))
        camera_sha = write(source / "cameras.json", raw({
            "assignment_id": ASSIGNMENT, "case_id": case_id, "frame_count": 9,
            "source_kind": "synthetic_diagnostic_fixture"}))
        receipt_sha = write(source / "receipt.json", raw({
            "assignment_id": ASSIGNMENT, "case_id": case_id,
            "source_kind": "synthetic_diagnostic_fixture", "context_sha256": context_sha,
            "trace_sha256": trace_sha, "camera_manifest_sha256": camera_sha}))
        records = [("context.json", context_sha), ("original-trace.jsonl", trace_sha),
                   ("cameras.json", camera_sha), ("receipt.json", receipt_sha)]
        recipe = {"format": "worker-fixture-recipe",
                  "generator": {"source": str(scaffold.relative_to(REPO)),
                                "sha256": sha(scaffold.read_bytes())},
                  "sources": [{"path": name, "source": str((source / name).relative_to(REPO)),
                               "sha256": digest} for name, digest in records]}
        write(folder / "fixture-recipe.json", raw(recipe))
    print("two synthetic stop fixtures; no original evidence")


if __name__ == "__main__":
    build()
