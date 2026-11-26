"""Build source-inventoried software fixtures for the four exact door cases.

These solid-color images do not depict a door. Their annotations exercise the
saved-source joins only and cannot establish physical or legal acceptance.
"""

import hashlib
import json
import os
from pathlib import Path
import shutil

from prove_finalize import make


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


def build(number):
    kind = "cargo" if number >= 3 else "passenger"
    close = 212 if number % 2 else 400
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) / ("fixture-probe-" + str(number))
    if scratch.exists():
        shutil.rmtree(scratch)
    review = make(scratch, close, kind)
    source_dir = ROOT / "diagnostic-sources" / ("probe-" + str(number))
    source_dir.mkdir(parents=True, exist_ok=True)
    for name in ("trace.jsonl", "video_frames.jsonl", "native-door-trace.jsonl",
                 "original-map.json", "original-road.json", "original-transfer.json",
                 "original-scene-review.json"):
        shutil.copyfile(scratch / name, source_dir / name)
    specimen = json.loads((REPO / "work/training__C276263__NRS-484B-533__motor_vehicle_driver/native/reference-adapter-video-spec.json").read_text())
    graphs = specimen["graphs"]
    for graph in graphs:
        graph["attributes"]["source"] = "C228817 synthetic diagnostic graph"
        graph["nodes"][0]["attributes"]["entity_id"] = 1
        graph["nodes"][0]["attributes"]["vertex"] = [0, 0, 0]
    frames = [json.loads(row) for row in specimen["files"]["capture/native/frames.jsonl"].splitlines()]
    evidence = [json.loads(row) for row in specimen["files"]["capture/evidence.jsonl"].splitlines()]
    for item in evidence:
        item["actor_id"] = 1
        item["ego"]["position_m"] = [0, 0, 0]
        item["ego"]["synthetic_diagnostic"] = True
    files = {"capture/native/frames.jsonl": lines(frames),
             "capture/evidence.jsonl": lines(evidence),
             "capture/recorder_info.txt": "Create 1: synthetic ego vehicle\nCreate 2: synthetic passing vehicle\n",
             "capture/manifest.json": json.dumps({"extraction_confirmed": True,
                "frames": 600, "synthetic_diagnostic": True,
                "sources": {"trace.jsonl": sha(source_dir / "trace.jsonl")}},
                sort_keys=True, separators=(",", ":")) + "\n"}
    spec = {"files": files, "graphs": graphs, "videos": specimen["videos"]}
    spec_path = ROOT / ("probe-" + str(number) + "-diagnostic-spec.json")
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
    recipe_path = ROOT / ("probe-" + str(number) + "-fixture-recipe.json")
    write(recipe_path, recipe)
    return {"case_id": ASSIGNMENT + "__probe_" + str(number),
            "recipe_sha256": sha(recipe_path), "spec_sha256": sha(spec_path),
            "source_count": len(inventory), "synthetic_diagnostic": True}


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", type=int, choices=(1, 2, 3, 4), required=True)
    args = parser.parse_args()
    print(json.dumps(build(args.probe), sort_keys=True))
