"""Create explicit nine-frame synthetic timing sources for CPU compatibility only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def content(value):
    return json.dumps(value, sort_keys=True) + "\n"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def body(index, entry):
    x = 1 if index >= entry else -3
    return [[x, 4], [x + 1, 4], [x + 1, 5], [x, 5]]


def main():
    base = json.loads((REPO / "runtime/fixtures/example.json").read_text())
    for suffix, ego_entry in (("entry_below", 1), ("entry_inside", 4),
                              ("entry_above", 7)):
        exact = ROOT.name + "__" + suffix
        source = json.loads(json.dumps(base))
        packet = {"case_id": exact, "source_kind": "synthetic_fixture",
                  "diagnostic_fixture": True,
                  "map_source_sha256": "diagnostic-map",
                  "intersection_source_sha256": "diagnostic-intersection",
                  "highway_source_sha256": "diagnostic-distinct-highways",
                  "device_source_sha256": "diagnostic-device-unknown",
                  "ego_actor_id": 11, "other_actor_id": 12,
                  "ego_road_id": 3, "other_road_id": 4,
                  "intersection_polygon_xy_m": [[0, 0], [10, 0], [10, 10], [0, 10]],
                  "frames": []}
        for index in range(9):
            packet["frames"].append({"frame": 100 + index, "time_s": index * .05,
                                     "ego": {"id": 11, "road_id": 3,
                                             "body_corners_xy_m": body(index, ego_entry)},
                                     "other": {"id": 12, "road_id": 4,
                                               "body_corners_xy_m": body(index, 4)}})
        source["files"]["original-attempt/entry-timing-source.json"] = content(packet)
        source["files"]["fixture-provenance.json"] = content({
            "diagnostic_fixture": True, "scope": "software compatibility only",
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False})
        capture = json.loads(source["files"]["capture/manifest.json"])
        capture["case_id"] = exact
        capture["acquisition"] = "synthetic_diagnostic_fixture"
        capture["source_run"] = "fixture:entry-timing-software-compatibility"
        source["files"]["capture/manifest.json"] = content(capture)
        path = ROOT / ("diagnostic-" + suffix + ".json")
        path.write_text(content(source))
        if path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError("diagnostic text exceeds return limit")
        recipe = {"format": "worker-fixture-recipe",
                  "generator": {"source": "work/" + ROOT.name + "/" + path.name,
                                "sha256": sha(path)},
                  "sources": [{"path": "diagnostic-input.json",
                               "source": "work/" + ROOT.name + "/" + path.name,
                               "sha256": sha(path)}]}
        (ROOT / ("diagnostic-" + suffix + "-recipe.json")).write_text(
            json.dumps(recipe, indent=2, sort_keys=True) + "\n")
        print(suffix, path.stat().st_size)


if __name__ == "__main__":
    main()
