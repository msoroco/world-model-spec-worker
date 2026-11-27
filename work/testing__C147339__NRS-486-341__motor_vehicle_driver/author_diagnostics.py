"""Create case-specific synthetic compatibility inputs; no physical claim."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from lane_use import CASES

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AID = ROOT.name
BASE = REPO / "work/testing__C145696__NRS-486-351-1__motorcycle_or_moped_operator"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, separators=(",", ":"), ensure_ascii=False) + "\n",
                    encoding="utf-8")


def site():
    return {"cell_id": "C147339", "layout": "one_way_multilane",
            **{key: "synthetic-" + key for key in (
                "map_source_sha256", "lane_source_sha256", "highway_source_sha256",
                "public_maintenance_source_sha256", "public_vehicle_access_source_sha256",
                "ego_blueprint_source_sha256", "motorcycle_class_source_sha256",
                "moped_class_source_sha256", "motorcycle_exclusion_review_sha256")},
            "same_one_way_direction": True,
            "lane_ids": {"protected": "-1", "adjacent": "-2"},
            "protected_lane_center_xy": [0, 0], "lane_lateral_unit_xy": [0, 1],
            "protected_lane_width_m": 3.5, "ego_width_m": 2.0,
            "protected_width_m": .8,
            "protected_route": {"source_sha256": "synthetic-protected-route",
                                "waypoints_xy": [[0, 0], [40, 0]]},
            "ego_routes": {name: {"source_sha256": "synthetic-ego-" + name,
                                  "waypoints_xy": [[0, 3.5], [40, target]]}
                           for name, target in (("adjacent", 3.5), ("edge", 1.9),
                                                ("deep", .8))}}


def main():
    source = json.loads((BASE / "diagnostic-both_stationary.json").read_text(encoding="utf-8"))
    evidence_source = [json.loads(line) for line in
                       (BASE / "diagnostic-both_stationary-capture-evidence.jsonl")
                       .read_text(encoding="utf-8").splitlines() if line]
    native_frames = (BASE / "diagnostic-both_stationary-capture-native-frames.jsonl")
    for case in CASES:
        cid = AID + "__" + case.case_id
        value = json.loads(json.dumps(source))
        files = value["files"]
        files.pop("lane-split-scene.json", None)
        files.pop("lane-split-history.jsonl", None)
        files["diagnostic-source-note.json"] = json.dumps({
            "source_kind": "synthetic_diagnostic_fixture", "accepted_original_source": False,
            "case_id": cid}) + "\n"
        files["fixture-provenance.json"] = json.dumps({
            "scope": "synthetic 900-frame software compatibility only", "case_id": cid}) + "\n"
        fixture_site = site()
        files["protected-lane-scene.json"] = json.dumps({
            "format": "synthetic-diagnostic-protected-lane-v1", "case_id": cid,
            "source_kind": "synthetic_diagnostic_fixture", "diagnostic_fixture": True,
            "protected_vehicle_class": case.protected_kind,
            "ego_vehicle_class": "motor_vehicle", "site": fixture_site}) + "\n"
        target = {"adjacent": 3.5, "edge": 1.9, "deep": .8}[case.ego_path]
        trace = [json.loads(line) for line in files["trace.jsonl"].splitlines() if line]
        history = []
        evidence = []
        for frame, original in zip(trace, evidence_source):
            x = frame["position_m"][0]
            frame["position_m"][1] = target
            frame["position"]["y"] = target
            row = {"original_frame": frame["frame"], "time_s": frame["time_s"],
                   "source_sha256": "synthetic-scene", "ego_pose_sha256": "synthetic-ego",
                   "protected_pose_sha256": "synthetic-protected",
                   "map_source_sha256": fixture_site["map_source_sha256"],
                   "lane_source_sha256": fixture_site["lane_source_sha256"],
                   "highway_source_sha256": fixture_site["highway_source_sha256"],
                   "ego_id": 1, "protected_id": 2, "ego_kind": "motor_vehicle",
                   "protected_kind": case.protected_kind, "ego_xy": [x, target],
                   "protected_xy": [x + 2, 0],
                   "protected_speed_mps": 6 if case.protected_driven else 0}
            history.append(json.dumps(row, separators=(",", ":")))
            sample = json.loads(json.dumps(original))
            old_y = sample["ego"]["position_m"][1]
            delta = target - old_y
            sample["ego"]["position_m"][1] = target
            for vertex in sample["ego"].get("body_vertices_m", []):
                vertex[1] += delta
            evidence.append(json.dumps(sample, separators=(",", ":")))
        files["trace.jsonl"] = "\n".join(json.dumps(frame, separators=(",", ":"))
                                             for frame in trace) + "\n"
        capture_manifest = json.loads(files["capture/manifest.json"])
        capture_manifest["case_id"] = cid
        capture_manifest["sources"]["trace.jsonl"] = hashlib.sha256(
            files["trace.jsonl"].encode()).hexdigest()
        files["capture/manifest.json"] = json.dumps(capture_manifest) + "\n"
        files["protected-lane-history.jsonl"] = "\n".join(history) + "\n"
        diag = ROOT / ("diagnostic-" + case.case_id + ".json")
        write(diag, value)
        capture_evidence = ROOT / ("diagnostic-" + case.case_id + "-capture-evidence.jsonl")
        capture_evidence.write_text("\n".join(evidence) + "\n", encoding="utf-8")
        capture_frames = ROOT / ("diagnostic-" + case.case_id + "-capture-native-frames.jsonl")
        capture_frames.write_bytes(native_frames.read_bytes())
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": path, "source": str(file.relative_to(REPO)),
                               "sha256": sha(file)} for path, file in (
                                   ("diagnostic-input.json", diag),
                                   ("capture/evidence.jsonl", capture_evidence),
                                   ("capture/native/frames.jsonl", capture_frames))],
                  "generator": {"source": str(diag.relative_to(REPO)), "sha256": sha(diag)}}
        write(ROOT / ("diagnostic-" + case.case_id + "-recipe.json"), recipe)
        print(case.case_id, "diagnostic bytes", diag.stat().st_size)


if __name__ == "__main__":
    main()
