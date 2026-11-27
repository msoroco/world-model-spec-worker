"""Generate eight explicit synthetic sources for software compatibility only."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil

from native_packet import AID, VIEWS

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
DONOR = ROOT / "work/testing__C24751__NRS-484B-310-1__heavy_vehicle_driver/diagnostics"
DONOR_CASE = DONOR / "_shared"
DONOR_GENERATOR = DONOR / "crosswalk_stop-generator.json"
SHARED = HERE / "diagnostics/_shared"
SOURCE_FILES = ("video_frames.jsonl", "capture/native/frames.jsonl")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj, compact=False):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False,
                               separators=(",", ":") if compact else None,
                               indent=None if compact else 2) + "\n", encoding="utf-8")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("diagnostic source exceeds 2 MiB: " + str(path))


def frame(index, case):
    time_s = index / 20
    unit_x = (180.0 - 7.0 * time_s) if case["immediate_request"] else (400.0 - 2.0 * time_s)
    if case["approach_direction"] == "same_direction":
        unit_x = -220.0 + 9.0 * time_s
    traverse = case["subject_position_request"] == "paved_shoulder_traverse"
    ego_x = -180.0 + 7.5 * min(time_s, 19.0) + (5.0 * max(0.0, time_s - 19.0) if traverse else 0.0)
    ego_y = -4.0 if case["subject_position_request"].startswith("paved_shoulder") else 0.0
    edge_distance = 2.0 if case["closeness_request"] == "intentionally_offset" else 0.3
    body_yaw = 20.0 if case["parallel_request"] == "skewed" else 0.0
    body = [[ego_x - 2.0, ego_y - 0.9], [ego_x + 2.0, ego_y - 0.9],
            [ego_x + 2.0, ego_y + 0.9], [ego_x - 2.0, ego_y + 0.9]]
    movement_visible = True
    return {"frame": index, "native_frame": index + 100, "original_frame": index + 100,
            "time_s": time_s, "ego_xy": [ego_x, ego_y], "emergency_xy": [unit_x, 4.0],
            "ego_body_vertices_m": body,
            "edge_distance_m": edge_distance, "body_yaw_to_edge_deg": body_yaw,
            "intersection_overlap": case["intersection_request"] == "inside_intersection",
            "position_region": case["subject_position_request"],
            "flashing_light_on": case["light_request"] != "qualified_inactive" and index % 8 < 4,
            "movement_visible": movement_visible,
            "ego_speed_mps": 7.5 if time_s < 19.0 else (5.0 if traverse else 0.0),
            "ego_brake": 0.5 if time_s >= 19.0 and not traverse else 0.0,
            "officer_direction": "proceed" if (case["officer_direction_request"] != "none") and 18 <= time_s < 20 else None,
            "motion_source": "synthetic-native-pose", "light_source": "synthetic-light-state",
            "visibility_source": "synthetic-driver-camera", "control_source": "synthetic-ego-controls"}


def build():
    SHARED.mkdir(parents=True, exist_ok=True)
    for relative in SOURCE_FILES:
        source, target = DONOR_CASE / relative, SHARED / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or sha(target) != sha(source):
            shutil.copyfile(source, target)
        if target.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("shared diagnostic source exceeds 2 MiB")
    base = json.loads(DONOR_GENERATOR.read_text(encoding="utf-8"))
    branch = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))["selected_branches"][0]
    for case in json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))["cases"]:
        name, case_id = case["variant"], AID + "__" + case["variant"]
        folder = HERE / "diagnostics" / name
        folder.mkdir(parents=True, exist_ok=True)
        write(folder / "diagnostic-source-note.json", {
            "case_id": case_id, "source_kind": "synthetic_diagnostic_fixture",
            "accepted_original_source": False,
            "scope": "Software finalizer, Core and decode only; no actual emergency motion evidence."})
        write(folder / "curb-site.json", {
            "ego_id": "ego", "emergency_id": "unit", "emergency_class": case["unit_class"],
            "subject_vehicle_class": "ordinary_motor_vehicle",
            "subject_driver_source": "synthetic-driver-control",
            "target_vehicle_class": case["unit_class"], "light_request": case["light_request"],
            "immediate_approach_request": case["immediate_request"],
            "yield_response_request": case["subject_position_request"] != "paved_shoulder_traverse",
            "approach_direction": case["approach_direction"],
            "edge_type": case["edge_type"],
            "parallel_request": case["parallel_request"],
            "closeness_request": case["closeness_request"],
            "intersection_request": case["intersection_request"],
            "subject_position_request": case["subject_position_request"],
            "sign_permitted_class": case["sign_permitted_class"],
            "highway_boundary_source": "synthetic-map-boundary",
            "curb_or_edge_source": "synthetic-map-curb-or-edge",
            "intersection_source": "synthetic-map-intersection",
            "shoulder_boundary_source": "synthetic-map-shoulder",
            "sign_content_source": "synthetic-sign-content",
            "lawful_sign_source": "synthetic-sign-placement",
            "physical_feasibility_source": "synthetic-position-feasibility",
            "traffic_conflict_source": "synthetic-traffic-context",
            "authorization_source": "synthetic-authority", "qualifying_lights_source": "synthetic-equipment",
            "light_rule_source": "DEF-NRS-484A-480-3", "route_source": "synthetic-native-map",
            "front_visible_red_lamp_source": "synthetic-front-view-lamp",
            "front_visible_red_lamp_qualified": case["light_request"] != "unqualified_active",
            "siren_equipment_source": "synthetic-siren-installation",
            "officer_direction_source": "synthetic-officer-context"})
        camera_rows = [dict(frame_index=i, native_frame=100 + i, time_s=i / 20,
                            camera_frames={view: 100 + i for view in VIEWS})
                       for i in range(900)]
        camera_path = folder / "camera-frame-map.jsonl"
        camera_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n"
                                       for row in camera_rows), encoding="utf-8")
        generator = copy.deepcopy(base)
        capture_manifest = json.loads(generator["files"]["capture/manifest.json"])
        capture_manifest["case_id"] = case_id
        generator["files"]["capture/manifest.json"] = json.dumps(capture_manifest, indent=2) + "\n"
        generator_path = HERE / "diagnostics" / (name + "-generator.json")
        write(generator_path, generator, compact=True)
        history_path = folder / "original-curb-position-history.jsonl"
        history = [frame(i, case) for i in range(900)]
        history_path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n"
                                        for row in history), encoding="utf-8")
        if history_path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("case history exceeds 2 MiB")
        trace_path = folder / "trace.jsonl"
        trace_path.write_text("".join(json.dumps({
            "frame": row["native_frame"], "time_s": row["time_s"],
            "position": {"x": row["ego_xy"][0], "y": row["ego_xy"][1], "z": 0.0},
            "position_m": [*row["ego_xy"], 0.0], "heading_deg": 0.0,
            "speed_mps": row["ego_speed_mps"],
            "speed_mph": row["ego_speed_mps"] * 2.2369362921,
            "velocity_mps": [row["ego_speed_mps"], 0.0, 0.0],
            "control": {"brake": row["ego_brake"], "hand_brake": False,
                        "throttle": 0.0 if row["ego_brake"] else 0.3}
        }, separators=(",", ":")) + "\n" for row in history), encoding="utf-8")
        if trace_path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("case trace exceeds 2 MiB")
        donor_evidence = [json.loads(line) for line in
                          (DONOR_CASE / "capture/evidence.jsonl").read_text(encoding="utf-8").splitlines()]
        if len(donor_evidence) != len(history):
            raise ValueError("donor synthetic native fixture frame count changed")
        evidence_path = folder / "capture/evidence.jsonl"
        evidence_path.parent.mkdir(parents=True, exist_ok=True)
        evidence_rows = []
        for old, row in zip(donor_evidence, history):
            evidence = copy.deepcopy(old)
            original = evidence["ego"]["position_m"]
            dx, dy = row["ego_xy"][0] - original[0], row["ego_xy"][1] - original[1]
            evidence["ego"]["position_m"] = [*row["ego_xy"], 0.0]
            evidence["ego"]["speed_mps"] = row["ego_speed_mps"]
            evidence["ego"]["body_vertices_m"] = [
                [point[0] + dx, point[1] + dy, point[2]]
                for point in evidence["ego"]["body_vertices_m"]]
            evidence_rows.append(evidence)
        evidence_path.write_text("".join(json.dumps(row, separators=(",", ":")) + "\n"
                                          for row in evidence_rows), encoding="utf-8")
        if evidence_path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("case evidence exceeds 2 MiB")
        capture_manifest["sources"]["trace.jsonl"] = sha(trace_path)
        generator["files"]["capture/manifest.json"] = json.dumps(capture_manifest, indent=2) + "\n"
        write(generator_path, generator, compact=True)
        write(HERE / "diagnostics" / (name + "-measurement-contract.json"), {
            "format": "worker-measurement-contract", "case_id": case_id,
            "requirements": [{"disposition_index": 0,
                "requirement": branch["requirement"], "source": branch["source"],
                "output_key": "emergency_curb_shoulder_position",
                "method": "measure_case", "value_type": "object", "kind": "measured",
                "inputs": ["original-curb-position-history.jsonl", "curb-site.json",
                           "camera-frame-map.jsonl"]}],
            "negative": {"remove": ["original-curb-position-history.jsonl"],
                "error_contains": "Missing required source: original-curb-position-history.jsonl"}})
        sources = []
        for relative in SOURCE_FILES:
            source = SHARED / relative
            sources.append({"path": relative, "source": str(source.relative_to(ROOT)), "sha256": sha(source)})
        for relative in ("diagnostic-source-note.json", "curb-site.json", "trace.jsonl",
                         "capture/evidence.jsonl",
                         "camera-frame-map.jsonl", "original-curb-position-history.jsonl"):
            source = folder / relative
            sources.append({"path": relative, "source": str(source.relative_to(ROOT)), "sha256": sha(source)})
        write(HERE / "diagnostics" / (name + "-recipe.json"), {
            "format": "worker-fixture-recipe", "sources": sources,
            "generator": {"source": str(generator_path.relative_to(ROOT)),
                          "sha256": sha(generator_path)}})


if __name__ == "__main__":
    build()
