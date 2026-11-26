"""Synthetic three-outcome overtaking and owner-closure protocol proof."""

import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def corners(x, y, half_length, half_width):
    return [[x - half_length, y - half_width, 0.0],
            [x - half_length, y + half_width, 0.0],
            [x + half_length, y - half_width, 0.0],
            [x + half_length, y + half_width, 0.0]]


def fixture(folder, config, construction, kind):
    folder.mkdir()
    write(folder / "config.json", config)
    write(folder / "construction.json", construction)
    (folder / "runner.py").write_text(next(item["content"] for item in
                                           construction["files"] if item["path"] == "runner.py"),
                                         encoding="utf-8")
    write(folder / "acquisition-provenance.json",
          {"provenance_kind": "synthetic_fixture", "diagnostic_fixture": True})
    if kind == "missing_evidence":
        return
    trace = []
    mapping = []
    for index in range(900):
        time_s = index / 20
        frame = 20000 + index
        if kind == "complete_motion":
            ego_x = 4 * time_s
            bike_x = 50 + time_s
            ego_y = min(2.0, max(0.0, (time_s - 5) / 2))
            if time_s > 35:
                ego_y = max(0.0, 2.0 - (time_s - 35) / 2)
        else:
            ego_x = 0.2 * time_s
            bike_x = 50 + time_s
            ego_y = 0.0
        trace.append({"frame": frame, "time_s": time_s,
                      "position_m": [ego_x, ego_y, 0.0],
                      "vehicle_vertices_m": corners(ego_x, ego_y, 1.0, 0.5),
                      "bicycle_vertices_m": corners(bike_x, 0.0, 1.0, 0.25)})
        mapping.append({"video_frame": index, "carla_frame": frame,
                        "time_s": time_s})
    for name, rows in (("trace.jsonl", trace), ("video_frames.jsonl", mapping)):
        (folder / name).write_text("".join(json.dumps(row) + "\n" for row in rows),
                                   encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    from worker_exchange.native_output import physical_result, seal_capture
    from worker_exchange.saved_processing import (acknowledge_owner_release,
                                                  copy_sources, record_native_exit)
    manifest = json.loads((HERE / "execution-manifest.selected-draft.json").read_text())
    entry = next(item for item in manifest["cases"] if item["case_id"] == args.case)
    construction = json.loads((HERE / entry["construction"]).read_text())
    config = json.loads(next(item["content"] for item in construction["files"]
                             if item["path"] == "config.json"))
    suffix = args.case.removeprefix(HERE.name + "__")
    output = Path(args.output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    for kind, expected in (("complete_motion", "met"),
                           ("incomplete_motion", "not_met"),
                           ("missing_evidence", "unverified")):
        folder = output / kind
        fixture(folder, config, construction, kind)
        result = physical_result(folder, {"case_id": args.case, "target_checks": [{
            "target": "original body-center passes qualifying rider with lateral transition",
            "requested": True, "measured": kind == "complete_motion",
            "method": "synthetic source-shaped 20 Hz body geometry; engineering event only",
            "tolerance": 0, "matched": kind == "complete_motion",
            "physical_cause_confirmed": False,
            "cause_evidence": "diagnostic fixture only"}]})
        if result["physical_checks"]["maneuver"]["status"] != expected or \
                result["maneuver_completed"] != (expected == "met"):
            raise ValueError("Physical overtaking outcome mismatch: " + kind)
        write(HERE / ("physical-" + suffix + "-" + kind + ".json"), result)
        print(kind, expected, sorted(result["physical_checks"]["maneuver"]["sources"]))
    complete = output / "complete_motion"
    seal = seal_capture(complete, frames=900,
                        restoration={"restored": True, "settings_readback":
                                     "CPU owner protocol fixture"},
                        errors=[], encoder_exit_codes={"diagnostic": 0})
    exit_receipt = record_native_exit(complete)
    owner = acknowledge_owner_release(complete, complete / "owner-release.json", True)
    stage = output / "saved_stage"
    stage.mkdir()
    copy_sources(complete, stage)
    if exit_receipt["capture_seal_sha256"] != sha(complete / "capture-seal.json") or \
            owner["native_exit_sha256"] != sha(complete / "native-exit.json"):
        raise ValueError("Native closure source binding failed")
    print("lifecycle", *seal["events"], "native_exit", "owner_released",
          "saved_processing_started")


if __name__ == "__main__":
    main()
