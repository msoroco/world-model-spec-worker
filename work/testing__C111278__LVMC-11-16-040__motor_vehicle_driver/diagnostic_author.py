"""Author explicit synthetic CPU fixtures for the six exact sight-speed cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ARMS = ("west", "north", "east")


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"


def sha_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def digest(value):
    return sha_bytes(encoded(value).encode())


def main():
    template = json.loads((REPO / "runtime/fixtures/example.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    manifest_path = ROOT / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    by_case = {entry["case_id"]: entry for entry in manifest["cases"]}
    for case in plan["cases"]:
        suffix = case["case_key"]
        case_id = case["case_id"]
        files = dict(template["files"])
        site = {"selected_case_id": case_id,
                "jurisdiction": "synthetic CPU diagnostic; municipal authority unverified",
                "road_kind": "synthetic street intersection",
                "ego_road_through": case["through_designation"],
                "traffic_controlled_intersection": case["traffic_controlled_intersection"],
                "diagnostic_fixture": True}
        speed = case["requested_traversal_speed_mph"] * 0.44704
        frames = []
        mapping = [json.loads(line) for line in files["video_frames.jsonl"].splitlines()]
        if len(mapping) != 9:
            raise ValueError("Pinned diagnostic frame count changed")
        for index, row in enumerate(mapping):
            rays = {}
            for arm in ARMS:
                blocked = case["requested_occluder"] is not None and arm == "west"
                rays[arm] = {"observer_convention": "lane_waypoint_1.4m_bbox_9",
                             "sampled_extent_m": 30.48,
                             "intersection_view": "blocked" if blocked else "clear",
                             "traffic_view": "blocked" if blocked else "clear",
                             "ray_frame_source_sha256": digest([suffix, arm, index])}
            frames.append({"frame": row["carla_frame"], "time_s": row["time_s"],
                           "approach_distance_m": [30.48, 24, 16, 8, 0, -1, -2, -3, -4][index],
                           "ego_speed_mps": speed,
                           "traversing_intersection": index >= 5,
                           "rays": rays})
        packet = {"case_id": case_id, "map_hash": digest("synthetic diagnostic map"),
                  "site_source_sha256": digest(site),
                  "boundary_source_sha256": digest("diagnostic boundary"),
                  "through_source_sha256": digest(case["through_designation"]),
                  "control_source_sha256": digest(case["traffic_controlled_intersection"]),
                  "entering_arms": list(ARMS), "frames": frames,
                  "frame_source_sha256": digest(frames),
                  "ray_source_sha256": digest([f["rays"] for f in frames]),
                  "speed_source_sha256": digest([f["ego_speed_mps"] for f in frames]),
                  "through_designation": case["through_designation"],
                  "traffic_controlled": case["traffic_controlled_intersection"]}
        files["site.json"] = encoded(site)
        files["native-sight.json"] = encoded(packet)
        files["native-sight-receipt.json"] = encoded({
            "case_id": case_id, "source_path": "native-sight.json",
            "source_sha256": sha_bytes(files["native-sight.json"].encode()),
            "capture_kind": "synthetic_fixture", "diagnostic_fixture": True})
        files["fixture-provenance.json"] = encoded({
            "diagnostic_fixture": True, "physical_acceptance_claimed": False,
            "scope": "synthetic original-shaped CPU software compatibility only"})
        specification = dict(template, files=files)
        spec_path = ROOT / f"diagnostic-{suffix}.json"
        spec_path.write_text(encoded(specification))
        assignment = REPO / "inputs" / ROOT.name / "assignment.json"
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "diagnostic-input.json",
                               "source": str(assignment.relative_to(REPO)),
                               "sha256": sha_bytes(assignment.read_bytes())}],
                  "generator": {"source": str(spec_path.relative_to(REPO)),
                                "sha256": sha_bytes(spec_path.read_bytes())}}
        recipe_path = ROOT / f"diagnostic-{suffix}-recipe.json"
        recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
        by_case[case_id]["fixture_recipe"] = str(recipe_path.relative_to(REPO))
        print(suffix, "diagnostic recipe authored")
    manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
