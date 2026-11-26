"""Saved source assessment of a complete parked assembly dwell.

The 0.08 m drift allowance is an engineering capture criterion only. The law's
15 ft (4.572 m) perpendicular boundary is not altered by this checker.
"""

import hashlib
import json
from pathlib import Path

from projection_measurement import measure_packet
from projection_construction import CASES
from projection_sources import CAMERAS


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def assess(root, case_id):
    root = Path(root)
    names = ("config.json", "original-projection-history.jsonl", "video_frames.jsonl",
             "camera-frame-map.jsonl")
    sources = {name: sha(root / name) for name in names if (root / name).is_file()}
    missing = [name for name in names if name not in sources]
    status = "unverified"
    observed = {}
    if not missing:
        config = json.loads((root / "config.json").read_text(encoding="utf-8"))
        history = [json.loads(line) for line in (root / names[1]).read_text(encoding="utf-8").splitlines()]
        mapping = [json.loads(line) for line in (root / names[2]).read_text(encoding="utf-8").splitlines()]
        cameras = [json.loads(line) for line in (root / names[3]).read_text(encoding="utf-8").splitlines()]
        expected = config["frame_count"]
        case = next(item for item in CASES if item.case_id == case_id)
        if (config["selected_case_id"] == case_id and len(history) == expected == len(mapping) == len(cameras) and
                all(row["frame"] == maprow["carla_frame"] and
                    abs(row["time_s"] - maprow["time_s"]) < 1e-6 and
                    maprow["video_frame"] == index and camera["native_frame"] == row["frame"] and
                    camera["camera_frames"] == {name: row["frame"] for name in CAMERAS}
                    for index, (row, maprow, camera) in enumerate(zip(history, mapping, cameras)))):
            measurements = [measure_packet(dict(row, load_present=case.controlling_part == "load",
                                                trailer_attached=case.controlling_part == "trailer"), sources)
                            ["maximum_street_projection_m"] for row in history]
            observed = {"frames": expected, "maximum_projection_m": max(measurements),
                        "minimum_projection_m": min(measurements),
                        "projection_drift_m": max(measurements) - min(measurements),
                        "statutory_boundary_m": 4.572,
                        "engineering_stability_tolerance_m": .08}
            status = "met" if observed["projection_drift_m"] <= .08 else "not_met"
    check = {"status": status, "method": "900 joined original complete-part outline measurements during parked dwell",
             "sources": sources, "missing_evidence": missing,
             "details": observed, "legal_verdict_claimed": False}
    provenance_path = root / "acquisition-provenance.json"
    provenance = json.loads(provenance_path.read_text(encoding="utf-8")) if provenance_path.is_file() else {}
    original = provenance.get("provenance_kind") == "native" and provenance.get("diagnostic_fixture") is False
    return {"physical_checks": {"maneuver": check},
            "maneuver_completed": status == "met", "realized_observables": observed,
            "provenance_kind": "native" if original else "synthetic_fixture",
            "diagnostic_fixture": not original,
            "physical_acceptance_claimed": False}
