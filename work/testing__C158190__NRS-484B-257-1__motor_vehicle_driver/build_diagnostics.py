"""Build explicitly synthetic nine-frame yield software fixtures for three cases."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
TEMPLATE = REPO / "work/testing__C255863__NRS-484B-363-3__motor_vehicle_driver/cases/no_children/diagnostic-scaffold.json"
VARIANTS = {"yield_slow_hazard": ("slow", "close"),
            "yield_stop_hazard": ("stop", "close"),
            "yield_slow_no_hazard": ("slow", "clear")}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main():
    for suffix, (response, phase) in VARIANTS.items():
        case_id = ASSIGNMENT + "__" + suffix
        folder = ROOT / "cases" / suffix
        sources = folder / "diagnostic-sources"
        sources.mkdir(parents=True, exist_ok=True)
        context = {"assignment_id": ASSIGNMENT, "case_id": case_id,
                   "source_kind": "synthetic_diagnostic_fixture",
                   "control": "yield_sign", "stop_line_present": False,
                   "near_crosswalk_present": False,
                   "sidewalk_derived_crosswalk_present": False,
                   "police_control_active": False,
                   "traffic_signal_control_active": False,
                   "planned_ego_response": response,
                   "planned_through_traffic_phase": phase,
                   "original_reviewed_site_available": False,
                   "legal_hazard_judgment": None}
        write(sources / "context.json", context)
        rows = [{"frame": i, "time_s": i / 20, "case_id": case_id,
                 "source_kind": "synthetic_diagnostic_fixture",
                 "ego_response_requested": response,
                 "through_phase_requested": phase} for i in range(9)]
        (sources / "original-trace.jsonl").write_text(
            "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n")
        write(sources / "cameras.json", {"assignment_id": ASSIGNMENT,
                                          "case_id": case_id, "frame_count": 9,
                                          "source_kind": "synthetic_diagnostic_fixture"})
        write(sources / "receipt.json", {"assignment_id": ASSIGNMENT,
                                          "case_id": case_id,
                                          "source_kind": "synthetic_diagnostic_fixture",
                                          "context_sha256": sha(sources / "context.json"),
                                          "trace_sha256": sha(sources / "original-trace.jsonl"),
                                          "camera_manifest_sha256": sha(sources / "cameras.json")})
        scaffold = json.loads(TEMPLATE.read_text())
        capture_manifest = json.loads(scaffold["files"]["capture/manifest.json"])
        capture_manifest["case_id"] = case_id
        capture_manifest["scope"] = ("Synthetic yield/no-line nearest-view software compatibility only; "
                                     "no original Native or legal evidence")
        scaffold["files"]["capture/manifest.json"] = json.dumps(capture_manifest, sort_keys=True) + "\n"
        (folder / "diagnostic-scaffold.json").write_text(
            json.dumps(scaffold, sort_keys=True, separators=(",", ":")) + "\n")
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": name, "source": str((sources / name).relative_to(REPO)),
                               "sha256": sha(sources / name)}
                              for name in ("context.json", "original-trace.jsonl", "cameras.json", "receipt.json")],
                  "generator": {"source": str((folder / "diagnostic-scaffold.json").relative_to(REPO)),
                                "sha256": sha(folder / "diagnostic-scaffold.json")}}
        write(folder / "fixture-recipe.json", recipe)
    print("three explicit synthetic diagnostic fixtures")


if __name__ == "__main__":
    main()
