"""Exercise projection dwell and Native ownership protocol with CPU fixtures."""

import argparse
import json
from pathlib import Path

from physical_completion import assess, sha
from projection_construction import CASES

ROOT = Path(__file__).resolve().parent


def write(path, obj):
    path.write_text(json.dumps(obj, sort_keys=True) + "\n", encoding="utf-8")


def fixture(folder, config, case, kind):
    folder.mkdir(parents=True)
    write(folder / "config.json", config)
    if kind == "missing_evidence":
        return
    history = []
    mapping = []
    cameras = []
    for index in range(900):
        projection = case.projection_m + (.2 if kind == "incomplete_motion" and index >= 450 else 0)
        vehicle = case.projection_m if case.controlling_part == "vehicle" else 4.2
        parts = [{"category": "vehicle", "source_actor_id": "synthetic-ego",
                  "outline_vertices_m": [[100, 0], [102, 0], [102, vehicle], [100, vehicle]]}]
        if case.controlling_part != "vehicle":
            parts.append({"category": case.controlling_part,
                          "source_actor_id": "synthetic-" + case.controlling_part,
                          "outline_vertices_m": [[100, 0], [102, 0], [102, projection], [100, projection]]})
        elif kind == "incomplete_motion" and index >= 450:
            parts[0]["outline_vertices_m"][2][1] = projection
        frame = 30000 + index
        history.append({"assignment_id": ROOT.name, "case_id": case.case_id,
                        "original_trace_id": "CPU-fixture-only", "frame": frame,
                        "time_s": index / 20, "curb_segment_start_m": [80, 0],
                        "curb_segment_end_m": [130, 0], "street_side_reference_m": [80, 8],
                        "load_present": case.controlling_part == "load",
                        "trailer_attached": case.controlling_part == "trailer",
                        "physical_parts": parts})
        mapping.append({"video_frame": index, "carla_frame": frame, "time_s": index / 20})
        cameras.append({"frame_index": index, "native_frame": frame, "time_s": index / 20,
                        "camera_frames": {name: frame for name in
                                          ("overview", "approach", "reference_corner", "driver_reference")}})
    for name, rows in (("original-projection-history.jsonl", history),
                       ("video_frames.jsonl", mapping), ("camera-frame-map.jsonl", cameras)):
        (folder / name).write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def lifecycle(root, config, construction):
    from worker_exchange.native_output import seal_capture
    from worker_exchange.saved_processing import record_native_exit, acknowledge_owner_release, copy_sources
    stage = root / "lifecycle"
    stage.mkdir()
    write(stage / "config.json", config)
    write(stage / "construction.json", construction)
    (stage / "runner.py").write_text(next(f["content"] for f in construction["files"] if f["path"] == "runner.py"), encoding="utf-8")
    traces = [{"frame": 30000 + i, "time_s": i / 20,
               "position": {"x": i, "y": 0, "z": 0}, "position_m": [i, 0, 0],
               "heading_deg": 0, "speed_mps": 1} for i in range(9)]
    mapping = [{"video_frame": i, "carla_frame": 30000 + i, "time_s": i / 20} for i in range(9)]
    for name, rows in (("trace.jsonl", traces), ("video_frames.jsonl", mapping)):
        (stage / name).write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    seal_capture(stage, frames=9, restoration={"restored": True, "settings_readback": "CPU fixture"},
                 errors=[], encoder_exit_codes={"diagnostic": 0})
    exit_receipt = record_native_exit(stage)
    owner = acknowledge_owner_release(stage, stage / "owner-release.json", True)
    saved = root / "saved_stage"
    saved.mkdir()
    copy_sources(stage, saved)
    if (exit_receipt["capture_seal_sha256"] != sha(stage / "capture-seal.json") or
            owner["native_exit_sha256"] != sha(stage / "native-exit.json")):
        raise ValueError("lifecycle source binding failed")
    return ["capture_finished", "encoders_closed", "restoration_verified",
            "native_exit", "owner_released", "saved_processing_started"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    entry = next(x for x in CASES if x.case_id == args.case)
    manifest = json.loads((ROOT / "execution-manifest.json").read_text(encoding="utf-8"))
    selected = next(x for x in manifest["cases"] if x["case_id"] == args.case)
    construction = json.loads((ROOT / selected["construction"]).read_text(encoding="utf-8"))
    config = json.loads(next(f["content"] for f in construction["files"] if f["path"] == "config.json"))
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    for kind, expected in (("complete_motion", "met"), ("incomplete_motion", "not_met"),
                           ("missing_evidence", "unverified")):
        folder = output / kind
        fixture(folder, config, entry, kind)
        result = assess(folder, args.case)
        if result["physical_checks"]["maneuver"]["status"] != expected:
            raise ValueError("physical fixture status differs: " + kind)
        write(ROOT / ("physical-" + entry.suffix + "-" + kind + ".json"), result)
        print(kind, expected)
    print("lifecycle", *lifecycle(output, config, construction))


if __name__ == "__main__":
    main()
