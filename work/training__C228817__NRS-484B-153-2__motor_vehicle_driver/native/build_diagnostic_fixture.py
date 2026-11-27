"""Build source-inventoried software fixtures for the four exact door cases.

These solid-color images do not depict a door. Their annotations exercise the
saved-source joins only and cannot establish physical or legal acceptance.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil

from prove_interference import make


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[2]
ASSIGNMENT = ROOT.parent.name
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":"),
                               allow_nan=False) + "\n")


def lines(rows):
    return "".join(json.dumps(row, sort_keys=True, separators=(",", ":"),
                              allow_nan=False) + "\n" for row in rows)


def build(suffix):
    if suffix not in ("board_overlap", "board_clear", "alight_overlap", "alight_clear"):
        raise ValueError("Unknown selected suffix")
    scratch = make(suffix)
    review = json.loads((scratch / "door-pixel-review.json").read_text())
    source_dir = ROOT / "diagnostic-sources" / suffix
    source_dir.mkdir(parents=True, exist_ok=True)
    for name in ("trace.jsonl", "video_frames.jsonl", "native-door-trace.jsonl",
                 "original-map.json", "original-road.json", "original-transfer.json",
                 "original-scene-review.json"):
        shutil.copyfile(scratch / name, source_dir / name)
    telemetry = [json.loads(row) for row in (source_dir / "trace.jsonl").read_text().splitlines()]
    for row in telemetry:
        row["speed_mph"] = 0.0
        row["position_m"] = [0, 0, 0]
        row["velocity_mps"] = [0, 0, 0]
        row["control"] = {"throttle": 0.0, "brake": 1.0, "hand_brake": True}
    (source_dir / "trace.jsonl").write_text(lines(telemetry))
    road = (REPO / "work/training__C276263__NRS-484B-533__motor_vehicle_driver/native/diagnostic-sources/reference/road.xodr").read_text()
    road = road.replace("C276263-grade", "C228817-flat-door-diagnostic")
    road = road.replace("graded-highway-proposal", "flat-door-diagnostic")
    road = road.replace('b=".04"', 'b="0"')
    (source_dir / "road.xodr").write_text(road.rstrip() + "\n")
    specimen = json.loads((REPO / "work/training__C276263__NRS-484B-533__motor_vehicle_driver/native/reference-adapter-video-spec.json").read_text())
    graphs = specimen["graphs"]
    for i, graph in enumerate(graphs):
        old_frame, new_frame = 900 + i, 1000 + i
        graph["path"] = graph["path"].replace(f"{old_frame:08d}", f"{new_frame:08d}")
        graph["attributes"]["frame"] = new_frame
        graph["attributes"]["source"] = "C228817 synthetic diagnostic graph"
        graph["nodes"][0]["attributes"]["entity_id"] = 1
        graph["nodes"][0]["attributes"]["vertex"] = [0, 0, 0]
    frames = [json.loads(row) for row in specimen["files"]["capture/native/frames.jsonl"].splitlines()]
    evidence = [json.loads(row) for row in specimen["files"]["capture/evidence.jsonl"].splitlines()]
    for i, (frame, item) in enumerate(zip(frames, evidence)):
        old_frame, new_frame = 900 + i, 1000 + i
        frame["frame"] = new_frame
        frame["adapter_graph"] = frame["adapter_graph"].replace(f"{old_frame:08d}", f"{new_frame:08d}")
        frame["base"] = frame["base"].replace(f"{old_frame:08d}", f"{new_frame:08d}")
        item["original_frame"] = new_frame
        item["replay_frame"] = new_frame
        item["actor_id"] = 1
        item["ego"]["position_m"] = [0, 0, 0]
        item["ego"]["synthetic_diagnostic"] = True
    files = {"capture/native/frames.jsonl": lines(frames),
             "capture/evidence.jsonl": lines(evidence),
             "capture/recorder_info.txt": "Create 1: vehicle.tesla.model3\nCreate 2: vehicle.tesla.model3\n",
             "capture/manifest.json": json.dumps({"extraction_confirmed": True,
                "frames": 600, "synthetic_diagnostic": True,
                "sources": {"trace.jsonl": sha(source_dir / "trace.jsonl"),
                            "road.xodr": sha(source_dir / "road.xodr")}},
                sort_keys=True, separators=(",", ":")) + "\n"}
    spec = {"files": files, "graphs": graphs, "videos": specimen["videos"]}
    spec_path = ROOT / (suffix + "-diagnostic-spec.json")
    write(spec_path, spec)
    # The generated fixture is created outside work and supplies only source files.
    from worker_exchange.fixture_generator import generate
    generated = scratch / "generated"
    generated.mkdir()
    generate(spec, generated)
    review["camera_sha256"] = {name: sha(generated / (name + ".mkv"))
                                  for name in CAMERAS}
    write(source_dir / "door-pixel-review.json", review)
    inventory = []
    for path in sorted(source_dir.iterdir()):
        inventory.append({"path": path.name,
                          "source": str(path.relative_to(REPO)), "sha256": sha(path)})
    recipe = {"format": "worker-fixture-recipe", "sources": inventory,
              "generator": {"source": str(spec_path.relative_to(REPO)),
                            "sha256": sha(spec_path)}}
    recipe_path = ROOT / (suffix + "-fixture-recipe.json")
    write(recipe_path, recipe)
    return {"case_id": ASSIGNMENT + "__" + suffix,
            "recipe_sha256": sha(recipe_path), "spec_sha256": sha(spec_path),
            "source_count": len(inventory), "synthetic_diagnostic": True}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--case-suffix", choices=("board_overlap", "board_clear", "alight_overlap", "alight_clear"), required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.case_suffix), sort_keys=True))
