"""Four-decodable-source diagnostic for both saved C125751 signal cases.

The fixture is synthetic and short. It checks the saved-source machinery, not
physical signal visibility, statutory inoperability, or delivery readiness.
"""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PACKAGE = Path(__file__).resolve().parent
OUT = ROOT / ".runtime-work/c125751-two-signal-saved-source-55s-v6"
sys.path.insert(0, str(PACKAGE / "tests"))
sys.path.insert(0, str(PACKAGE))
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))

from test_finalizer import SavedFinalizerTests, body
from finalizer import CAMERAS, CASES, finalize
from worker_exchange.capture import PROFILE
from worker_exchange.media import audit, check_four_view_sources
from worker_exchange.native_output import validate_result

FRAMES = 1100


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_rows(path, values):
    path.write_text("".join(json.dumps(value, allow_nan=False) + "\n" for value in values))


def make_sources(attempt, case, state):
    attempt.mkdir(parents=True)
    SavedFinalizerTests().sources(attempt)
    config_path = attempt / "config.json"
    config = json.loads(config_path.read_text())
    config["selected_case_id"] = case
    config["target_signal_state"] = state
    config["duration_s"] = 55
    config_path.write_text(json.dumps(config, indent=2) + "\n")
    crossing = rows(attempt / "crossing_history.jsonl")
    signal = rows(attempt / "signal_history.jsonl")
    other_state = "Red" if state == "Green" else "Off"
    for row in signal:
        row["other_state"] = other_state
    stop = rows(attempt / "stop_history.jsonl")
    mapping = rows(attempt / "video_frames.jsonl")
    trace = rows(attempt / "trace.jsonl")
    for i in range(4, FRAMES):
        frame, t = 100 + i, i / 20
        ex, oy = min(9, -4 + .12 * (i-3)), min(9, -3 + .12 * (i-3))
        ego, other = body(ex, 0), body(0, oy)
        ego.update(heading_deg=0, native_road_id=1, native_lane_id=-1)
        other.update(heading_deg=90, native_road_id=2, native_lane_id=-1)
        crossing.append({"frame": frame, "time_s": t, "ego": ego,
                         "other": other, "ego_vertices_m": ego["body_vertices_xy_m"]})
        signal.append({"frame": frame, "time_s": t, "native_signal_id": 55, "state": state,
                       "other_native_signal_id": 56, "other_state": other_state})
        stop.append({"frame": frame, "time_s": t,
                     "ego": {"speed_mps": 0 if ex >= 9 else 2,
                             "front_xy_m": [ex+.3, 0], "body_inside_crossing": -5.3 <= ex <= 5.3},
                     "other": {"speed_mps": 0 if oy >= 9 else 2,
                               "front_xy_m": [0, oy+.3], "body_inside_crossing": -5.3 <= oy <= 5.3}})
        mapping.append({"video_frame": i, "carla_frame": frame, "time_s": t})
        trace.append({"frame": frame, "time_s": t, "position_m": [ex, 0, 0]})
    for row in crossing[:4]:
        row["ego_vertices_m"] = row["ego"]["body_vertices_xy_m"]
    for name, values in (("crossing_history.jsonl", crossing), ("signal_history.jsonl", signal),
                         ("stop_history.jsonl", stop), ("video_frames.jsonl", mapping),
                         ("trace.jsonl", trace)):
        write_rows(attempt / name, values)
    signal_path = attempt / "signal_history.jsonl"
    for row in signal:
        if row["frame"] >= 102:
            row["state"] = state
    write_rows(signal_path, signal)
    sizes = {"overview": PROFILE["overview"],
             **dict(zip(("approach", "reference_corner", "driver_reference"),
                        PROFILE["detail_views"]))}
    for name in CAMERAS:
        path = attempt / name
        path.unlink()
        width, height = sizes[name.removesuffix(".mkv")]
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                        "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r=20",
                        "-frames:v", str(FRAMES), "-an", "-c:v", "ffv1", "-threads", "1",
                        str(path)], check=True, timeout=300)
    review_path = attempt / "head_visibility_review.json"
    review = json.loads(review_path.read_text())
    review["source_video_sha256"] = sha(attempt / "approach.mkv")
    review["review_basis"] = "synthetic source binding only; black pixels do not establish a visible head"
    review_path.write_text(json.dumps(review, indent=2) + "\n")
    other_review_path = attempt / "other_head_visibility_review.json"
    other_review = json.loads(other_review_path.read_text())
    other_review["source_video_sha256"] = sha(attempt / "reference_corner.mkv")
    other_review["review_basis"] = review["review_basis"]
    other_review_path.write_text(json.dumps(other_review, indent=2) + "\n")
    return sizes


def negative_with_bad_review(attempt, negative, role):
    negative.mkdir()
    (negative / "capture").mkdir()
    for name in ("config.json", "road_geometry.json", "turn_route_context.json", "crossing_history.jsonl",
                 "signal_context.json", "signal_history.jsonl", "stop_context.json",
                 "stop_history.jsonl", "video_frames.jsonl", "trace.jsonl", *CAMERAS):
        (negative / name).hardlink_to(attempt / name)
    (negative / "capture/evidence.jsonl").hardlink_to(attempt / "capture/evidence.jsonl")
    selected = "head_visibility_review.json" if role == "ego" else "other_head_visibility_review.json"
    intact = "other_head_visibility_review.json" if role == "ego" else "head_visibility_review.json"
    (negative / intact).hardlink_to(attempt / intact)
    review = json.loads((attempt / selected).read_text())
    review["source_video_sha256"] = "0" * 64
    (negative / selected).write_text(json.dumps(review) + "\n")
    try:
        finalize(negative, negative / "analysis-report.json")
    except ValueError as error:
        assert "Head review is not bound to retained source video" in str(error), error
    else:
        raise AssertionError("A stale reviewed-camera hash was accepted")
    assert not (negative / "result.json").exists()


def main():
    if OUT.exists():
        raise ValueError("Retain prior proof; choose a new output path")
    receipts = []
    for case, state in CASES.items():
        label = "operative" if state == "Green" else "off"
        other_state = "Red" if state == "Green" else "Off"
        attempt = OUT / label
        sizes = make_sources(attempt, case, state)
        check_four_view_sources({name.removesuffix(".mkv"): attempt / name for name in CAMERAS})
        mapping_sha = sha(attempt / "video_frames.jsonl")
        decodes = {}
        for name in CAMERAS:
            receipt = audit(attempt / name, FRAMES, mapping_sha256=mapping_sha)
            assert receipt["dimensions"] == list(sizes[name.removesuffix(".mkv")])
            decodes[name] = {"frames": receipt["frames"], "source_sha256": receipt["video_sha256"]}
        negative_with_bad_review(attempt, OUT / (label + "-stale-ego-head-review"), "ego")
        negative_with_bad_review(attempt, OUT / (label + "-stale-other-head-review"), "other")
        measurements = finalize(attempt, attempt / "analysis-report.json")
        result = validate_result(json.loads((attempt / "result.json").read_text()))
        assert result["case_id"] == case
        assert result["target_checks"][0]["matched"] is True
        assert result["source_evidence_hashes"]["approach.mkv"] == decodes["approach.mkv"]["source_sha256"]
        assert result["source_evidence_hashes"]["reference_corner.mkv"] == decodes["reference_corner.mkv"]["source_sha256"]
        assert measurements["signal_at_entry"]["value"]["at_body_entry"]["ego"]["native_state"] == state
        assert measurements["signal_at_entry"]["value"]["at_body_entry"]["other"]["native_state"] == other_state
        assert measurements["stop_order"]["value"]["statutory_stop_judgment"] == "unresolved"
        for name in ("signal_state.jsonl", "stop_state.jsonl", "entry_context.json"):
            assert (attempt / "channels" / name).is_file()
        receipts.append({"case_id": case, "state_at_ego_entry": state,
                         "state_at_other_entry": other_state,
                         "source_decodes": decodes, "frame_map_sha256": mapping_sha,
                         "measurement_names": sorted(measurements),
                         "negative": "stale ego and other reviewed-camera source hashes rejected before finalization"})
    receipt = {"format": "worker-c125751-two-case-saved-source-proof",
               "cases": receipts, "frames_per_case": FRAMES, "rate_hz": 20,
               "synthetic_only": True, "physical_acceptance_claimed": False,
               "legal_acceptance_claimed": False,
               "limitations": "The full-duration black diagnostic streams cannot establish visible signal heads or actual Native motion/capture."}
    print(json.dumps(receipt, allow_nan=False, sort_keys=True))


if __name__ == "__main__":
    main()
