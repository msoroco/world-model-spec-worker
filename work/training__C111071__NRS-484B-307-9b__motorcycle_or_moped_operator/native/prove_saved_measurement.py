"""Exercise source joins and negative mutations for the saved CPU analyzer."""
from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

from finalize import CAMERAS, finalize
from saved_measurement import analyze


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2] / ".runtime-work"


def write(path: Path, rows: list[dict] | dict) -> None:
    if isinstance(rows, list):
        path.write_text("".join(json.dumps(row, allow_nan=False) + "\n" for row in rows))
    else:
        path.write_text(json.dumps(rows, indent=2, allow_nan=False) + "\n")


def fixture(path: Path, entry: int) -> None:
    path.mkdir()
    native, mapping = [], []
    for frame in range(600):
        phase = ("cross_green", "cross_yellow", "cross_red")[(frame % 120) // 40]
        front = -4.0 if frame < entry else 1.0
        native.append({
            "native_frame": frame + 100, "time_s": frame / 20,
            "signal_actor_id": 17, "cross_signal_actor_id": 18,
            "ego_face_observed": "circular_red_green_left_arrow",
            "cross_phase_observed": phase, "controller_cycle_count": frame // 120,
            "actor_class_observed": "motorcycle", "detector_request_present": True,
            "detector_request_serviced": False, "other_device_prohibition_observed": False,
            "body_vertices_m": [[-1, front-2], [1, front-2], [-1, front], [1, front]],
            "speed_mps": 0 if 15 <= frame < entry else 3,
            "entered_intersection": frame >= entry,
            "pedestrians_in_crosswalk": False, "lawful_traffic_conflict": False,
        })
        mapping.append({"video_frame": frame, "native_frame": frame + 100,
                        "time_s": frame / 20})
    write(path / "native_samples.jsonl", native)
    write(path / "video_frames.jsonl", mapping)
    write(path / "road_geometry.json", {
        "signal_actor_id": 17, "cross_signal_actor_id": 18,
        "governing_face": "circular_red_green_left_arrow",
        "approach_enters_intersection": True,
        "stop_reference_kind": "nearest_crosswalk", "approach_axis": 1,
        "approach_sign": 1, "stop_reference_coordinate_m": 0,
        "other_device_prohibition_survey": False,
    })


def add_video_sources(path: Path, variant: str) -> None:
    write(path / "config.json", {
        "assignment_id": "training__C111071__NRS-484B-307-9b__motorcycle_or_moped_operator",
        "case_id": "training__C111071__NRS-484B-307-9b__motorcycle_or_moped_operator__" + variant,
        "case_variant": variant, "rate_hz": 20, "duration_s": 30,
        "recording_description": {"channels": ["native_samples", "video_frame_map"]},
    })
    for name in CAMERAS:
        run = subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                              "-f", "lavfi", "-i", "color=c=black:s=64x36:r=20",
                              "-frames:v", "600", "-an", "-c:v", "ffv1", str(path / (name + ".mkv"))],
                             text=True, capture_output=True, timeout=120)
        if run.returncode:
            raise RuntimeError("Synthetic source-video fixture failed: " + run.stderr)


def mutate(path: Path, name: str) -> None:
    native_path = path / "native_samples.jsonl"
    map_path = path / "video_frames.jsonl"
    geometry_path = path / "road_geometry.json"
    native = [json.loads(line) for line in native_path.read_text().splitlines()]
    mapping = [json.loads(line) for line in map_path.read_text().splitlines()]
    geometry = json.loads(geometry_path.read_text())
    if name == "missing_native_frame": native.pop(200)
    elif name == "altered_frame_join": mapping[200]["native_frame"] += 1
    elif name == "altered_time_join": native[200]["time_s"] += 0.1
    elif name == "missing_body": native[200].pop("body_vertices_m")
    elif name == "altered_signal_identity": native[200]["signal_actor_id"] = 99
    elif name == "wrong_phase_order": native[200]["cross_phase_observed"] = "cross_green"
    elif name == "fabricated_cycle_count": native[200]["controller_cycle_count"] = 10
    elif name == "serviced_detector": native[200]["detector_request_serviced"] = True
    elif name == "prohibiting_device": geometry["other_device_prohibition_survey"] = True
    elif name == "missing_stop":
        for row in native: row["speed_mps"] = 3
    elif name == "conflict_at_entry": native[250]["pedestrians_in_crosswalk"] = True
    else: raise AssertionError(name)
    write(native_path, native)
    write(map_path, mapping)
    write(geometry_path, geometry)


def main() -> None:
    names = ("missing_native_frame", "altered_frame_join", "altered_time_join",
             "missing_body", "altered_signal_identity", "wrong_phase_order",
             "fabricated_cycle_count", "serviced_detector", "prohibiting_device",
             "missing_stop", "conflict_at_entry")
    ROOT.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="c111071-saved-", dir=ROOT) as temp:
        root = Path(temp)
        positive = root / "positive"
        fixture(positive, 250)
        p = analyze(positive)
        assert p["case_observation"]["requested_gate_satisfied"]
        assert p["case_observation"]["complete_cycle_end_frames"][:2] == [120, 240]
        early = root / "early"
        fixture(early, 130)
        n = analyze(early)
        assert not n["case_observation"]["requested_gate_satisfied"]
        add_video_sources(positive, "two_cycles")
        add_video_sources(early, "one_cycle")
        final_positive = finalize(positive, root / "positive_output")
        final_early = finalize(early, root / "early_output")
        assert final_positive["video_frame_counts"] == {name + ".mkv": 600 for name in CAMERAS}
        assert json.loads((root / "positive_output" / "result.json").read_text())["target_checks"][0]["matched"]
        assert json.loads((root / "early_output" / "result.json").read_text())["target_checks"][0]["matched"]
        missing_camera = root / "missing_camera"
        fixture(missing_camera, 250)
        add_video_sources(missing_camera, "two_cycles")
        (missing_camera / "driver_reference.mkv").unlink()
        try:
            finalize(missing_camera, root / "missing_camera_output")
            raise AssertionError("Missing source camera was accepted")
        except ValueError as error:
            assert "Missing original source camera" in str(error)
        negatives = {}
        for name in names:
            path = root / name
            fixture(path, 250)
            mutate(path, name)
            try:
                observed = analyze(path)
                negatives[name] = not observed["case_observation"]["requested_gate_satisfied"]
            except ValueError:
                negatives[name] = True
        assert all(negatives.values()), negatives
    proof = {"format": "c111071-saved-measurement-cpu-proof-v1",
             "assignment_id": "training__C111071__NRS-484B-307-9b__motorcycle_or_moped_operator",
             "analyzer_sha256": hashlib.sha256((HERE / "saved_measurement.py").read_bytes()).hexdigest(),
             "positive": {"entry": p["case_observation"]["entry_frame"],
                          "cycle_ends": p["case_observation"]["complete_cycle_end_frames"][:2]},
             "controlled_early_entry": {"entry": n["case_observation"]["entry_frame"],
                                         "two_cycles": n["case_observation"]["two_cycles_before_entry"]},
             "negative_mutations_rejected": negatives,
             "finalizer_sha256": hashlib.sha256((HERE / "finalize.py").read_bytes()).hexdigest(),
             "finalizer_positive_and_contrast": True,
             "four_source_cameras_decoded": True,
             "missing_source_camera_rejected": True,
             "source_kind": "synthetic_native_sample", "native_observation": False,
             "physical_or_legal_acceptance": False}
    receipt = HERE / "saved-measurement-proof.json"
    receipt.write_text(json.dumps(proof, indent=2) + "\n")
    print(json.dumps({"positive": True, "controlled_early_entry": True,
                      "negative_count": len(negatives), "receipt": str(receipt)}, sort_keys=True))


if __name__ == "__main__": main()
