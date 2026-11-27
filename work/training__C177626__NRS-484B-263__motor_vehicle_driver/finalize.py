"""Saved-only C177626 measurement; no legal conclusion or source rewrite."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "native"))
from acquisition import VIEWS, bind_original


def _required(root: Path, name: str) -> Path:
    path = root / name
    if not path.is_file():
        raise ValueError("Missing required source: " + name)
    return path


def _rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def _digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def finalize(attempt: Path, output: Path) -> dict:
    root = Path(attempt)
    config = json.loads(_required(root, "config.json").read_text())
    case_id = config.get("case_id")
    if case_id not in (
        "training__C177626__NRS-484B-263__motor_vehicle_driver__selected_ed45c8e4__condition_a",
        "training__C177626__NRS-484B-263__motor_vehicle_driver__selected_ed45c8e4__condition_b",
    ):
        raise ValueError("exact selected entry case missing")
    names = ("native_samples.jsonl", "camera_frames.jsonl", "entry_history.jsonl", "authored-context.json",
             "capture-seal.json", "trace.jsonl", "video_frames.jsonl",
             "capture/evidence.jsonl")
    for name in names:
        _required(root, name)
    for view in VIEWS:
        _required(root, view + ".mkv")
    native = _rows(root / "native_samples.jsonl")
    cameras = _rows(root / "camera_frames.jsonl")
    trace = _rows(root / "trace.jsonl")
    entry = _rows(root / "entry_history.jsonl")
    mapping = _rows(root / "video_frames.jsonl")
    events = _rows(root / "capture/evidence.jsonl")
    if any(len(stream) != 600 for stream in (native, cameras, entry, trace, mapping, events)):
        raise ValueError("complete 600-frame original source join required")
    for index, (row, camera, road, motion, frame, event) in enumerate(
        zip(native, cameras, entry, trace, mapping, events)
    ):
        source_frame = row.get("native_frame")
        if (row.get("frame") != index or camera.get("frame") != source_frame or
                motion.get("frame") != source_frame or road.get("frame") != source_frame or
                road.get("road_id") != row.get("ego", {}).get("road_id") or
                frame.get("video_frame") != index or
                frame.get("native_frame") != source_frame or
                event.get("original_frame") != source_frame or
                abs(frame.get("time_s", -1) - row.get("native_elapsed_s", -2)) > 1e-4):
            raise ValueError("original actor, camera, trace, frame and event join differs")
    context = json.loads((root / "authored-context.json").read_text())
    policy = "earlier_yield" if case_id.endswith("_a") else "later_yield"
    bound = bind_original(native, cameras, context, policy)
    diagnostic = json.loads((root / "capture-seal.json").read_text()).get("diagnostic_fixture") is True
    description = config["recording_description"]
    channel_dir = root / "channels"
    channel_dir.mkdir(exist_ok=True)
    recording = []
    for channel in description["channels"]:
        term = channel["name"]
        target = channel_dir / (term.replace(".", "_") + ".json")
        target.write_text(json.dumps({"source_sha256": bound["original_source_sha256"],
                                      "term": term, "measurements": bound["measurements"]},
                                     allow_nan=False, separators=(",", ":")) + "\n")
        recording.append({"name": term, "unit": channel["unit"],
                          "reference": "channels/" + target.name})
    target = {"target": "original_entry_source_join", "requested": 600,
              "measured": bound["frames"],
              "method": "sealed original actors, two inventoried highway vehicles and four camera frames",
              "tolerance": 0, "matched": bound["frames"] == 600,
              "physical_cause_confirmed": False,
              "cause_evidence": list(names)}
    result = {
        "case_id": case_id, "measured_values": bound,
        "target_checks": [target], "setup_confirmed": False,
        "behavior_attempted": False, "maneuver_completed": False,
        "termination_reason": "Saved entry source assessed; physical and legal review pending",
        "physical_failure_flags": ["controlled_access_designation_and_physical_review_pending"],
        "trace_reference": "trace.jsonl",
        "video_references": [view + ".mkv" for view in VIEWS],
        "video_frame_map_reference": "video_frames.jsonl",
        "recording_description": description,
        "recording_evidence": recording,
        "realized_observables": {
            "entry_source_frames": {"value": bound["frames"], "unit": "frames",
                                    "statistic": "count", "method": target["method"],
                                    "time_window": "30 s / 600 frames",
                                    "reference": "native_samples.jsonl"}},
        "provenance_kind": "synthetic_fixture" if diagnostic else "native",
        "physical_acceptance_claimed": False, "legal_verdict_claimed": False,
    }
    from worker_exchange.native_output import write_result
    write_result(root, result)
    report = {
        "format": "worker-c177626-saved-analysis-v1", "case_id": case_id,
        "measurements": {"entry_source": {
            "method": "bind_original", "value": bound,
            "sources": {name: _digest(root / name) for name in names}}},
        "original_native_source": not diagnostic,
        "controlled_access_designation_verified": False,
        "legal_conclusion": None,
    }
    Path(output).write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    finalize(Path(args.attempt), Path(args.output))
