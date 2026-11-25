"""Build 900-frame synthetic source pairs and prove the comparison CLI boundary."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
STAGE = REPO / ".runtime-work/c160013-comparison-proof"


def _sha(data):
    return hashlib.sha256(data.encode()).hexdigest()


def _body(x, y):
    return [[x - 1, y - 1], [x + 1, y - 1], [x + 1, y + 1], [x - 1, y + 1]]


def _write(root, spacing, *, narrow):
    root.mkdir(parents=True, exist_ok=True)
    context = {"native_map_id": "FixtureMap", "highway_id": 44, "road_id": 7,
               "outside_business_district": True, "caravan_or_motorcade": True,
               "roadway_polygon_xy_m": [[0, -5], [80, -5], [80, 5], [0, 5]],
               "road_forward_xy": [1, 0]}
    for key in ("business_district_source", "caravan_membership_source",
                "route_source", "lane_source"):
        name = key + ".txt"
        content = "synthetic structural diagnostic source for " + key + "\n"
        (root / name).write_text(content)
        context[key] = {"path": name, "sha256": _sha(content)}
    (root / "road_context.json").write_text(json.dumps(context, indent=2) + "\n")
    with (root / "caravan_history.jsonl").open("w") as history, \
            (root / "video_frames.jsonl").open("w") as frames:
        for index in range(900):
            move = .01 * index
            members = [{"actor_id": member + 1, "blueprint_id": "vehicle.tesla.model3",
                        "body_vertices_xy_m": _body(10 + member * spacing + move, 0)}
                       for member in range(3)]
            if narrow:
                entrant_x, entrant_y = 11.5 + move, -3
            else:
                entrant_x = 3 + move + 12 * min(index / 40, 1)
                entrant_y = -3 + 3 * min(max((index - 40) / 40, 0), 1)
            frame = 100 + index
            time_s = round(1 + index / 20, 9)
            history.write(json.dumps({"frame": frame, "time_s": time_s, "road_id": 7,
                                      "caravan_members": members,
                                      "entering_vehicle": {"actor_id": 9, "blueprint_id": "vehicle.tesla.model3",
                                                           "body_vertices_xy_m": _body(entrant_x, entrant_y)}}) + "\n")
            frames.write(json.dumps({"video_frame": index, "carla_frame": frame,
                                     "time_s": time_s}) + "\n")


def run():
    output_root = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", "/")).resolve()
    if not output_root.is_relative_to(REPO / ".runtime-work"):
        raise ValueError("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work")
    wide, narrow = STAGE / "wide", STAGE / "narrow"
    _write(wide, 10, narrow=False)
    _write(narrow, 3, narrow=True)
    script = PACKAGE / "caravan_comparison.py"
    receipt = PACKAGE / "cases/caravan-comparison-diagnostic.json"
    positive = PACKAGE / "cases/caravan-comparison-positive.log"
    command = [sys.executable, str(script), "--wide", str(wide), "--narrow", str(narrow),
               "--output", str(receipt)]
    with positive.open("w") as stream:
        result = subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT,
                                timeout=600, check=False)
    if result.returncode:
        raise RuntimeError("900-frame comparison positive failed: " + positive.read_text()[-800:])
    value = json.loads(receipt.read_text())
    if (value["wide_frames"], value["narrow_frames"]) != (900, 900) or value["physical_acceptance_claimed"]:
        raise ValueError("Comparison receipt is incomplete or overclaims")
    context_path = narrow / "road_context.json"
    context = json.loads(context_path.read_text())
    source_path = narrow / "lane_source.txt"
    source_path.write_text("changed synthetic lane source\n")
    context["lane_source"]["sha256"] = hashlib.sha256(source_path.read_bytes()).hexdigest()
    context_path.write_text(json.dumps(context, indent=2) + "\n")
    negative = PACKAGE / "cases/caravan-comparison-negative.log"
    with negative.open("w") as stream:
        result = subprocess.run(command, cwd=REPO, stdout=stream, stderr=subprocess.STDOUT,
                                timeout=600, check=False)
    if result.returncode == 0 or "changed original context sources" not in negative.read_text():
        raise ValueError("Changed original context source was not rejected")
    print(json.dumps({"frames_per_case": 900, "positive_exit": 0,
                      "changed_source_negative_exit": result.returncode,
                      "receipt": str(receipt.relative_to(PACKAGE)),
                      "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    run()
