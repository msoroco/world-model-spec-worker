"""Generate six explicit synthetic sources for software compatibility only."""

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
SOURCE_FILES = ("trace.jsonl", "video_frames.jsonl",
                "capture/native/frames.jsonl", "capture/evidence.jsonl")


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
    unit_x = min(2.0, max(0.0, (time_s - 17.0) * 1.0))
    ego_x = -180.0 + time_s * 7.5
    movement_visible = case.visible and 17.0 <= time_s <= 19.5
    hand_visible = case.cue == "hand_signal" and 16.5 <= time_s <= 19.0
    return {"frame": index, "native_frame": index + 100, "original_frame": index + 100,
            "time_s": time_s, "ego_xy": [ego_x, 0.0], "emergency_xy": [unit_x, 4.0],
            "flashing_light_on": index % 8 < 4, "movement_visible": movement_visible,
            "driver_hand_signal_visible": hand_visible,
            "hand_signal_source": "synthetic-driver-camera" if hand_visible else None,
            "ego_speed_mps": 7.5 if not case.brake_after_cue or time_s < 19.0 else 5.0,
            "ego_brake": 0.5 if case.brake_after_cue and time_s >= 19.0 else 0.0,
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
            "authorization_source": "synthetic-authority", "qualifying_lights_source": "synthetic-equipment",
            "light_rule_source": "DEF-NRS-484A-480-3", "route_source": "synthetic-native-map",
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
        history_path = folder / "original-emergency-history.jsonl"
        history_path.write_text("".join(json.dumps(frame(i, case), separators=(",", ":")) + "\n"
                                        for i in range(900)), encoding="utf-8")
        if history_path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("case history exceeds 2 MiB")
        write(HERE / "diagnostics" / (name + "-measurement-contract.json"), {
            "format": "worker-measurement-contract", "case_id": case_id,
            "requirements": [{"disposition_index": 0,
                "requirement": branch["requirement"], "source": branch["source"],
                "output_key": "emergency_movement_and_response",
                "method": "measure_case", "value_type": "object", "kind": "measured",
                "inputs": ["original-emergency-history.jsonl", "emergency-site.json"]}],
            "negative": {"remove": ["original-emergency-history.jsonl"],
                "error_contains": "Missing required source: original-emergency-history.jsonl"}})
        sources = []
        for relative in SOURCE_FILES:
            source = SHARED / relative
            sources.append({"path": relative, "source": str(source.relative_to(ROOT)), "sha256": sha(source)})
        for relative in ("diagnostic-source-note.json", "emergency-site.json",
                         "camera-frame-map.jsonl", "original-emergency-history.jsonl"):
            source = folder / relative
            sources.append({"path": relative, "source": str(source.relative_to(ROOT)), "sha256": sha(source)})
        write(HERE / "diagnostics" / (name + "-recipe.json"), {
            "format": "worker-fixture-recipe", "sources": sources,
            "generator": {"source": str(generator_path.relative_to(ROOT)),
                          "sha256": sha(generator_path)}})


if __name__ == "__main__":
    build()
