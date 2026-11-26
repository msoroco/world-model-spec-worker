"""Source-bound 600-frame flashing-red stop and post-stop conflict diagnostic."""
import hashlib
import json
import math
from pathlib import Path

FRAMES = 600
RATE = 20


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError("Missing retained source: " + path.name)
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def measure(config_path, native_path, frame_path, geometry_path):
    config = json.loads(Path(config_path).read_text())
    geometry = json.loads(Path(geometry_path).read_text())
    native, frames = rows(native_path), rows(frame_path)
    if config.get("frames") != FRAMES or config.get("rate_hz") != RATE or \
            len(native) != FRAMES or len(frames) != FRAMES:
        raise ValueError("Exact 30-second source contract differs")
    if geometry.get("source_kind") not in ("synthetic_native_sample", "original_native"):
        raise ValueError("Geometry provenance missing")
    if geometry.get("limit_line_x_m") is not None:
        reference, xref = "limit_line", geometry["limit_line_x_m"]
    elif geometry.get("crosswalk_near_x_m") is not None:
        reference, xref = "crosswalk", geometry["crosswalk_near_x_m"]
    else:
        reference, xref = "intersection", geometry["intersection_near_x_m"]
    if type(xref) not in (int, float) or not math.isfinite(xref):
        raise ValueError("Stopping reference geometry invalid")
    stopped_before = []
    crossed = None
    prior_frame = None
    prior_x = None
    conflicts_after_crossing = []
    signal_states = []
    if not geometry.get("official_device_source") or not geometry.get("signal_head_facing_source") or not geometry.get("signal_head_id"):
        raise ValueError("Official facing signal source missing")
    for i, (sample, frame) in enumerate(zip(native, frames)):
        nframe = sample.get("native_frame")
        t = i / RATE
        if type(nframe) is not int or (prior_frame is not None and nframe != prior_frame + 1):
            raise ValueError("Native sequence differs")
        prior_frame = nframe
        if frame.get("video_frame") != i or frame.get("native_frame") != nframe or \
                any(type(v) not in (int, float) or abs(v - t) > 1e-4 for v in
                    (sample.get("time_s"), frame.get("time_s"))):
            raise ValueError("Native/video frame-time join differs")
        x, speed = sample.get("front_x_m"), sample.get("speed_mps")
        if (type(x) not in (int, float) or type(speed) not in (int, float) or
                not math.isfinite(x) or not math.isfinite(speed) or speed < 0 or
                (prior_x is not None and x < prior_x - .1)):
            raise ValueError("Native body motion differs")
        prior_x = x
        if sample.get("source_kind") != geometry["source_kind"]:
            raise ValueError("Native and geometry provenance differ")
        if sample.get("signal_head_id") != geometry["signal_head_id"] or \
                sample.get("signal_lamp_state") not in ("red", "off") or \
                type(sample.get("signal_faces_ego_observed")) is not bool or \
                type(sample.get("conflict_occupied")) is not bool:
            raise ValueError("Original signal or conflict source missing")
        if not sample["signal_faces_ego_observed"]:
            raise ValueError("Facing flashing-red source incomplete")
        signal_states.append(sample["signal_lamp_state"])
        if speed <= .05 and x < xref and crossed is None:
            stopped_before.append(i)
        if crossed is None and x >= xref:
            crossed = i
        if sample["conflict_occupied"] and x >= xref:
            conflicts_after_crossing.append(i)
    if (set(signal_states) != {"red", "off"} or
            sum(a != b for a, b in zip(signal_states, signal_states[1:])) < 4):
        raise ValueError("Facing flashing-red source incomplete")
    halt_runs = []
    for frame_index in stopped_before:
        if not halt_runs or frame_index != halt_runs[-1][-1] + 1:
            halt_runs.append([])
        halt_runs[-1].append(frame_index)
    return {"format": "c111271-source-measurement-v2", "case_id": config["case_id"],
            "frames": FRAMES, "stopping_reference": reference,
            "stopping_reference_x_m": xref, "stopped_before_reference_frames": len(stopped_before),
            "longest_pre_reference_halt_frames": max(map(len, halt_runs), default=0),
            "pre_reference_halt_runs": [[run[0], run[-1]] for run in halt_runs],
            "first_crossing_frame": crossed,
            "conflict_occupied_after_crossing_frames": len(conflicts_after_crossing),
            "first_conflict_after_crossing_frame": (conflicts_after_crossing[0] if conflicts_after_crossing else None),
            "flashing_red_transition_count": sum(a != b for a, b in zip(signal_states, signal_states[1:])),
            "source_hashes": {"config": sha(config_path), "native": sha(native_path),
                              "frame_map": sha(frame_path), "geometry": sha(geometry_path)},
            "engineering_stop_threshold_mps": .05,
            "physical_legal_verdict": None,
            "original_pixels_verified": False}
