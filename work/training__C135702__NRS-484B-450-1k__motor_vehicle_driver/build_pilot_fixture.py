"""Build explicit synthetic 600-frame obstruction fixtures for compatibility.

The generic Core packet skeleton comes from a retained synthetic fixture. This
script replaces its subject motion and adds this law's obstruction sources. No
source here is an accepted original recording or an observed CARLA outcome.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from native.geometry import open_drive

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
DONOR = REPO / "work/training__C229397__NRS-484B-450-1e__motor_vehicle_driver"
BASE = DONOR / "selected-source/witness_1"
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
BASE_NAMES = ("acquisition-provenance.json", "capture/evidence.jsonl",
              "capture/manifest.json", "capture/native/frames.jsonl",
              "capture/recorder_info.txt", "trace.jsonl", "video_frames.jsonl")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def write_rows(path: Path, values: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(value, allow_nan=False) + "\n" for value in values))


def build(suffix: str) -> dict:
    if suffix not in ("a", "b"):
        raise ValueError("Unknown selected case")
    case_id = ROOT.name + "__selected_dacdf461__condition_" + suffix
    target = ROOT / "selected-source" / ("condition_" + suffix)
    target.mkdir(parents=True, exist_ok=True)
    for name in BASE_NAMES:
        destination = target / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(BASE / name, destination)
    (target / "road.xodr").write_text(open_drive() + "\n")
    road = [-100.0, -3.5, 100.0, 3.5]
    obstruction = [0.0, 1.0, 5.0, 3.4]
    ego = [.1, -3.4, 4.9, .5 if suffix == "a" else -1.2]
    center = [2.5, (ego[1] + ego[3]) / 2, 1.1]
    flags = {name: False for name in ("traffic_conflict", "law_direction",
                                       "police_direction", "traffic_device")}
    reviewed = {name + "_reviewed": True for name in flags}
    write(target / "exception-context.json", {
        "case_id": case_id, "source_kind": "synthetic_cpu",
        "exceptions": flags, "exception_source": reviewed,
        "legal_verdict_claimed": False})
    write(target / "obstruction-inventory.json", {
        "case_id": case_id, "source_kind": "synthetic_cpu",
        "obstruction_kind": "physical_obstruction",
        "road_xy_m": road, "obstruction_xy_m": obstruction,
        "physical_cause_confirmed": False, "legal_verdict_claimed": False})
    trace = [json.loads(line) for line in (target / "trace.jsonl").read_text().splitlines()]
    evidence = [json.loads(line) for line in (target / "capture/evidence.jsonl").read_text().splitlines()]
    frame_map = [json.loads(line) for line in (target / "video_frames.jsonl").read_text().splitlines()]
    if not len(trace) == len(evidence) == len(frame_map) == 600:
        raise ValueError("Synthetic donor frame count differs")
    samples, cameras = [], []
    for index, (row, packet, mapping) in enumerate(zip(trace, evidence, frame_map)):
        frame = mapping["native_frame"]
        time = index / 20
        if row["frame"] != frame or packet["original_frame"] != frame:
            raise ValueError("Synthetic donor Native frame join differs")
        row["position"] = {"x": center[0], "y": center[1], "z": center[2]}
        row["position_m"] = center
        row["heading_deg"] = 0
        row["speed_mps"] = 0
        row["speed_mph"] = 0
        row["velocity_mps"] = [0, 0, 0]
        packet["ego"]["position_m"] = center
        packet["ego"]["heading_deg"] = 0
        packet["ego"]["speed_mps"] = 0
        packet["ego"]["body_vertices_m"] = [
            [x, y, z] for x, y in ((ego[0], ego[1]), (ego[2], ego[1]),
                                    (ego[2], ego[3]), (ego[0], ego[3]))
            for z in (0, 1.5)]
        traffic_x = -10 if suffix == "a" else -80 + index * 3 / 20
        traffic_speed = 0 if suffix == "a" else 3
        samples.append({"native_frame": frame, "time_s": time,
                        "source_kind": "synthetic_cpu", "road_xy_m": road,
                        "obstruction_xy_m": obstruction,
                        "obstruction_kind": "physical_obstruction",
                        "ego_body_xy_m": ego, "ego_speed_m_s": 0,
                        "passing_body_xy_m": [traffic_x, -.8, traffic_x + 4, .8],
                        "passing_speed_m_s": traffic_speed,
                        "exceptions": flags, "exception_source": reviewed,
                        "controller_clearance_m": .5 if suffix == "a" else 2.2})
        cameras.extend({"frame": index, "native_frame": frame, "camera": view,
                        "source_kind": "synthetic_cpu",
                        "rgb_sha256": hashlib.sha256((case_id + ":" + str(index) + ":" + view).encode()).hexdigest()}
                       for view in VIEWS)
    write_rows(target / "trace.jsonl", trace)
    write_rows(target / "capture/evidence.jsonl", evidence)
    write_rows(target / "native_samples.jsonl", samples)
    write_rows(target / "camera-frames.jsonl", cameras)
    manifest = json.loads((target / "capture/manifest.json").read_text())
    manifest["sources"] = {"road.xodr": sha(target / "road.xodr"),
                           "trace.jsonl": sha(target / "trace.jsonl")}
    write(target / "capture/manifest.json", manifest)
    generator = ROOT / "selected-generator.json"
    if not generator.is_file():
        shutil.copyfile(DONOR / "selected-generator-witness_1.json", generator)
    names = (*BASE_NAMES, "road.xodr", "exception-context.json",
             "obstruction-inventory.json", "native_samples.jsonl", "camera-frames.jsonl")
    recipe = {"format": "worker-fixture-recipe",
              "sources": [{"path": name,
                           "source": str((target / name).relative_to(REPO)),
                           "sha256": sha(target / name)} for name in names],
              "generator": {"source": str(generator.relative_to(REPO)),
                            "sha256": sha(generator)}}
    write(ROOT / ("selected-recipe-condition_" + suffix + ".json"), recipe)
    return {"case_id": case_id, "source_files": len(names),
            "recipe_sha256": sha(ROOT / ("selected-recipe-condition_" + suffix + ".json")),
            "synthetic_only": True}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-suffix", choices=("a", "b"), required=True)
    print(json.dumps(build(parser.parse_args().case_suffix)))
