"""Generate five explicit synthetic crosswalk diagnostic recipes and contracts."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
EXAMPLE = REPO / "runtime/fixtures/example.json"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    example = json.loads(EXAMPLE.read_text())
    road_hash = sha(example["files"]["road.xodr"].encode())
    fixed = {"map_sha256": road_hash,
             "crosswalk_source_sha256": sha(b"synthetic-crosswalk-qualification"),
             "crosswalk_id": "synthetic-cw-1", "one_way_road_id": "synthetic-one-way-1",
             "access_source_sha256": sha(b"synthetic-access"),
             "signal_source_sha256": sha(b"synthetic-signal"),
             "participant_source_sha256": sha(b"synthetic-participants"),
             "pedestrian_source_sha256": sha(b"synthetic-pedestrian")}
    for case in plan["cases"]:
        cid = case["case_id"]
        short = cid.split("__")[-1]
        folder = ROOT / "cases" / short
        folder.mkdir(parents=True, exist_ok=True)
        diagnostic = json.loads(json.dumps(example))
        files = diagnostic["files"]
        source_manifest = json.loads(files["capture/manifest.json"])
        source_manifest["case_id"] = cid
        files["capture/manifest.json"] = json.dumps(source_manifest, sort_keys=True) + "\n"
        reverse = case["direction"] == "reverse"
        right = case["target_half"] == "right"
        obstructed = case["obstacle_context"] != "clear"
        site = dict(fixed, obstacle_source_sha256=sha(b"synthetic-obstruction" if obstructed else b"synthetic-clear"),
                    crosswalk_qualification="native_crosswalk_readback",
                    crosswalk_width_m=4.0, entry_center=[0, 8] if reverse else [0, 0],
                    exit_center=[0, 0] if reverse else [0, 8],
                    governing_signal="none_read_back", pedestrian_access=True,
                    diagnostic_fixture=True)
        mapping = [json.loads(s) for s in files["video_frames.jsonl"].splitlines()]
        x = (-1 if reverse else 1) * (1 if right else -1)
        positions = []
        obstacles = []
        participants = []
        for index, row in enumerate(mapping):
            y = (8 - index if reverse else index)
            observed_x = .1 if obstructed and 2 <= y <= 6 else x
            positions.append({"frame": row["carla_frame"], "elapsed_s": row["time_s"],
                "pedestrian_id": "synthetic-walker", "pedestrian_xy": [observed_x, y],
                "pedestrian_source_sha256": site["pedestrian_source_sha256"]})
            obstacles.append({"frame": row["carla_frame"],
                "source_sha256": site["obstacle_source_sha256"],
                "available_right_width_m": .5 if obstructed else 2.0,
                "obstacle_geometry": {"polygon_xy": [[.2, 2], [2, 2], [2, 6], [.2, 6]]}
                    if obstructed else None})
            participants.append({"frame": row["carla_frame"],
                "source_sha256": site["participant_source_sha256"],
                "participants": []})
        entries = {"original-site.json": json.dumps(site, sort_keys=True) + "\n",
            "original-pedestrian.jsonl": "".join(json.dumps(x, sort_keys=True) + "\n" for x in positions),
            "original-obstacles.jsonl": "".join(json.dumps(x, sort_keys=True) + "\n" for x in obstacles),
            "original-participants.jsonl": "".join(json.dumps(x, sort_keys=True) + "\n" for x in participants)}
        files.update(entries)
        receipt = {"case_id": cid, "fps": 20, "frame_count": len(mapping),
                   "diagnostic_fixture": True,
                   "sources": {name: sha(text.encode()) for name, text in entries.items()}}
        files["original-receipt.json"] = json.dumps(receipt, sort_keys=True) + "\n"
        files["fixture-provenance.json"] = json.dumps({"case_id": cid,
            "scope": "Synthetic nine-frame CPU diagnostic only; not reviewed site, physical motion or legal practicability"},
            sort_keys=True) + "\n"
        generator = folder / "diagnostic.json"
        generator.write_text(json.dumps(diagnostic, separators=(",", ":")) + "\n")
        source = str(generator.relative_to(REPO))
        write(folder / "fixture-recipe.json", {"format": "worker-fixture-recipe",
            "sources": [{"path": "diagnostic-input.json", "source": source,
                         "sha256": sha(generator.read_bytes())}],
            "generator": {"source": source, "sha256": sha(generator.read_bytes())}})
        write(folder / "measurement-contract.json", {"format": "worker-measurement-contract",
            "case_id": cid, "requirements": [{"disposition_index": 0,
                "requirement": plan["requirement_dispositions"][0]["requirement"],
                "source": plan["requirement_dispositions"][0]["source"],
                "output_key": "crosswalk_passage", "method": "measure_crosswalk_passage",
                "value_type": "object", "kind": "measured",
                "inputs": list(entries) + ["original-receipt.json"]}],
            "negative": {"remove": ["original-site.json"],
                         "error_contains": "Missing required source: original-site.json"}})


if __name__ == "__main__":
    build()
    print("five synthetic crosswalk recipes and contracts generated")
