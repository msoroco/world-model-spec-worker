"""Source-shaped rail diagnostic for saved-only meter and negative source gates."""
import hashlib
import json
from pathlib import Path
import shutil

from finalize import analyze
from source_review import ROLES

ASSIGNMENT = "training__C202463__NRS-484B-560-3__motor_vehicle_driver"
HERE = Path(__file__).resolve().parents[1]
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")
VARIANTS = {"probe_a": "right_single_queue", "probe_b": "left_single_queue",
            "probe_c": "left_abreast_queue", "probe_d": "left_abreast_four_lanes",
            "probe_e": "left_abreast_five_lanes"}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def put(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def lines(rows):
    return "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows)


def fixture(path, suffix):
    if suffix not in VARIANTS:
        raise ValueError("Unknown rail diagnostic")
    path.mkdir(parents=True)
    source = HERE / "fixtures/rail_queue" / VARIANTS[suffix]
    for name in ("geometry.json", "gate.jsonl", "actors.jsonl", "sources.json"):
        shutil.copy2(source / name, path / name)
    geo = json.loads((path / "geometry.json").read_text())
    lane_count = geo["total_marked_lanes"]
    (path / "road.xodr").write_text("<OpenDRIVE><header revMajor=\"1\" revMinor=\"4\" name=\"synthetic rail CPU diagnostic\"/></OpenDRIVE>\n")
    gate = [json.loads(line) for line in (path / "gate.jsonl").read_text().splitlines()]
    actors = [json.loads(line) for line in (path / "actors.jsonl").read_text().splitlines()]
    frame_map, trace = [], []
    for i, (signal, row) in enumerate(zip(gate, actors)):
        camera_frames = {name: 1000 + i for name in CAMERAS}
        signal["video_frame"] = i
        row["video_frame"] = i
        row["camera_native_frames"] = camera_frames
        frame_map.append({"video_frame": i, "native_frame": 1000 + i,
            "carla_frame": 1000 + i,
            "time_s": i / 20, "camera_native_frames": camera_frames})
        ego = row["actors"]["ego"]
        trace.append({"frame": 1000 + i, "time_s": i / 20,
            "position": {"x": ego["x_m"], "y": ego["y_m"], "z": 0},
            "speed_mps": ego["speed_mps"]})
    (path / "gate.jsonl").write_text(lines(gate))
    (path / "actors.jsonl").write_text(lines(actors))
    (path / "video_frames.jsonl").write_text(lines(frame_map))
    (path / "trace.jsonl").write_text(lines(trace))
    put(path / "sources.json", {"kind": "synthetic_cpu_rail_stop_queue",
        "sha256": {name: sha(path / name) for name in
                   ("geometry.json", "gate.jsonl", "actors.jsonl")}})
    put(path / "acquisition-provenance.json", {"provenance_kind": "synthetic_fixture"})
    put(path / "rail-inventory.json", {"road_sha256": sha(path / "road.xodr"),
        "crossing_x_m": geo["rail_crossing_x_m"],
        "right_highway_edge_y_m": geo["right_highway_edge_y_m"],
        "total_marked_lanes": lane_count, "gate_actor_id": 42,
        "native_source": False})
    for role in ROLES:
        source_text = path / "rail-review" / (role + ".source.txt")
        source_text.parent.mkdir(parents=True, exist_ok=True)
        source_text.write_text("Synthetic CPU diagnostic source for " + role + " only\n")
        record = {"role": role, "source_sha256": sha(source_text),
            "road_sha256": sha(path / "road.xodr"),
            "provenance_kind": "synthetic_fixture"}
        if role == "required-stop":
            record.update(stop_required=True, authority_clause="synthetic gate exercise only")
        elif role == "rail-crossing":
            record["crossing_x_m"] = geo["rail_crossing_x_m"]
        elif role == "right-edge":
            record["right_highway_edge_y_m"] = geo["right_highway_edge_y_m"]
        elif role == "lane-markings":
            record["total_marked_lanes"] = lane_count
        elif role == "right-availability":
            record["right_space_reviewed"] = True
        else:
            record["native_actor_id"] = 42
        put(path / "rail-review" / (role + ".json"), record)
    for name in CAMERAS:
        (path / (name + ".mkv")).write_text("Synthetic CPU camera placeholder\n")
    case = ASSIGNMENT + "__" + suffix
    put(path / "config.json", {"case_id": case, "selected_case_id": case,
        "law_id": "NRS-484B-560-3", "cell_id": "C202463",
        "rate_hz": 20, "duration_s": 30,
        "queue_mode": {"probe_a": "right_single", "probe_b": "left_single",
            "probe_c": "left_abreast", "probe_d": "left_abreast_four_lanes",
            "probe_e": "left_abreast_five_lanes"}[suffix],
        "recording_description": {"channels": [], "limitations": ["CPU diagnostic only"]}})
    return case


def main(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    outcomes = {}
    for suffix in VARIANTS:
        good = root / suffix
        fixture(good, suffix)
        before = {str(p.relative_to(good)): sha(p) for p in good.rglob("*") if p.is_file()}
        value = analyze(good)
        after = {str(p.relative_to(good)): sha(p) for p in good.rglob("*") if p.is_file()}
        if before != after or not value["context"]["diagnostic_fixture"]:
            raise AssertionError("Diagnostic source mutated or misclassified")
        bad = root / (suffix + "-missing-required-stop")
        shutil.copytree(good, bad)
        (bad / "rail-review/required-stop.json").unlink()
        try:
            analyze(bad)
        except ValueError as error:
            if "Missing required source: rail-review/required-stop.json" not in str(error):
                raise
            negative = str(error)
        else:
            raise AssertionError("Missing required stop source accepted")
        outcomes[suffix] = {"lane_count": value["measurement"]["total_marked_lanes"],
            "abreast_frames": value["measurement"]["abreast_two_queue_frames"],
            "missing_required_stop_rejected": negative}
    return {"passed": True, "diagnostic_only": True,
        "original_required_stop_observed": False, "outcomes": outcomes}


if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        raise SystemExit("Usage: prove_finalizer_source.py SCRATCH")
    print(json.dumps(main(sys.argv[1]), indent=2))
