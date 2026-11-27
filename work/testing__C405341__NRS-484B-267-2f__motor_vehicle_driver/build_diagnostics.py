"""Generate eight explicit synthetic sources for software compatibility only."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import shutil

from emergency_construction import CASES
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
    unit_x = (180.0 - 7.0 * time_s) if case.immediate else (400.0 + 2.0 * time_s)
    if case.direction == "same_direction":
        unit_x = -220.0 + 9.0 * time_s
    if case.state == "preparing":
        unit_x = 180.0 - 7.0 * max(0.0, time_s - 20.0)
    if case.state == "stopped":
        unit_x = 180.0 - 7.0 * min(time_s, 20.0)
    ego_x = (-180.0 + 7.5 * time_s if not case.yielding else
             -180.0 + 7.5 * min(time_s, 19.0) + 5.0 * max(0.0, time_s - 19.0))
    movement_visible = (case.state == "moving" or
                        case.state == "preparing" and time_s >= 20.0 or
                        case.state == "stopped" and time_s < 20.0)
    return {"frame": index, "native_frame": index + 100, "original_frame": index + 100,
            "time_s": time_s, "ego_xy": [ego_x, 0.0], "emergency_xy": [unit_x, 4.0],
            "flashing_light_on": case.light_request != "qualified_inactive" and index % 8 < 4,
            "movement_visible": movement_visible,
            "visible_hand_signal": case.state == "preparing" and 10.0 <= time_s < 20.0,
            "ego_speed_mps": 7.5 if not case.yielding or time_s < 19.0 else 5.0,
            "ego_brake": 0.5 if case.yielding and time_s >= 19.0 else 0.0,
            "officer_direction": "proceed" if case.officer_direction and 18 <= time_s < 20 else None,
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
    for case in CASES:
        name, case_id = case.suffix, AID + "__" + case.suffix
        folder = HERE / "diagnostics" / name
        folder.mkdir(parents=True, exist_ok=True)
        write(folder / "diagnostic-source-note.json", {
            "case_id": case_id, "source_kind": "synthetic_diagnostic_fixture",
            "accepted_original_source": False,
            "scope": "Software finalizer, Core and decode only; no actual emergency motion evidence."})
        write(folder / "emergency-site.json", {
            "ego_id": "ego", "emergency_id": "unit", "emergency_class": case.unit_class,
            "subject_vehicle_class": "ordinary_motor_vehicle",
            "subject_driver_source": "synthetic-driver-control",
            "target_vehicle_class": case.unit_class, "light_request": case.light_request,
            "immediate_approach_request": case.immediate,
            "yield_response_request": case.yielding,
            "approach_direction": case.direction,
            "unit_state": case.state,
            "visible_preparation_source": "synthetic-original-driver-view-hand-signal" if case.state == "preparing" else None,
            "stop_location_source": "synthetic-original-unit-stop-site" if case.state == "stopped" else None,
            "authorization_source": "synthetic-authority", "qualifying_lights_source": "synthetic-equipment",
            "light_rule_source": "DEF-NRS-484A-480-3", "route_source": "synthetic-native-map",
            "front_visible_red_lamp_source": "synthetic-front-view-lamp",
            "front_visible_red_lamp_qualified": case.light_request != "unqualified_active",
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
        history_path = folder / "original-emergency-movement-history.jsonl"
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
                "output_key": "emergency_approach_and_yield_response",
                "method": "measure_case", "value_type": "object", "kind": "measured",
                "inputs": ["original-emergency-movement-history.jsonl", "emergency-site.json",
                           "camera-frame-map.jsonl"]}],
            "negative": {"remove": ["original-emergency-movement-history.jsonl"],
                "error_contains": "Missing required source: original-emergency-movement-history.jsonl"}})
        sources = []
        for relative in SOURCE_FILES:
            source = SHARED / relative
            sources.append({"path": relative, "source": str(source.relative_to(ROOT)), "sha256": sha(source)})
        for relative in ("diagnostic-source-note.json", "emergency-site.json", "trace.jsonl",
                         "capture/evidence.jsonl",
                         "camera-frame-map.jsonl", "original-emergency-movement-history.jsonl"):
            source = folder / relative
            sources.append({"path": relative, "source": str(source.relative_to(ROOT)), "sha256": sha(source)})
        write(HERE / "diagnostics" / (name + "-recipe.json"), {
            "format": "worker-fixture-recipe", "sources": sources,
            "generator": {"source": str(generator_path.relative_to(ROOT)),
                          "sha256": sha(generator_path)}})


if __name__ == "__main__":
    build()
