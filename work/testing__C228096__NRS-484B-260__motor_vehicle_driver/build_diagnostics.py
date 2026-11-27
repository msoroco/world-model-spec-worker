"""Build synthetic source-shaped diagnostics for nine exact private-way cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from private_way_construction import ASSIGNMENT, CASES
from private_way_site import REQUIRED_SOURCES


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = REPO / "runtime" / "fixtures" / "example.json"


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"


def _sha(value):
    return hashlib.sha256(value.encode() if isinstance(value, str) else value).hexdigest()


def create(variant):
    case_id = ASSIGNMENT + "__" + variant
    maneuver, sides, policy = CASES[variant]
    diagnostic = json.loads(BASE.read_text())
    files = diagnostic["files"]
    for name in list(files):
        if name.startswith("original-attempt/"):
            del files[name]
    frames = [json.loads(line) for line in files["video_frames.jsonl"].splitlines()]
    sources = {}
    for name in REQUIRED_SOURCES:
        content = (files["road.xodr"] if name == "native_opendrive_map"
                   else "Synthetic diagnostic source for " + name + "; original review pending.\n")
        relative = "site-sources/" + name + ".source"
        files["original-attempt/" + relative] = content
        sources[name] = {"path": relative, "sha256": _sha(content)}
    site = {
        "format": "worker-private-way-site-v1", "case_id": case_id,
        "sources": sources,
        "reviewed_assertions": {"private_ownership": True,
                                "restricted_public_access": True,
                                "destination_public_highway": True,
                                "permitted_vehicular_use": True,
                                "feasible_connection": True},
        "private_way_polygon": [[-10, -2], [-3, -2], [-3, 2], [-10, 2]],
        "highway_polygon": [[-2, -4], [10, -4], [10, 4], [-2, 4]],
        "connection_xy": [0, 0], "highway_axis_xy": [1, 0],
        "routes": {"enter": [[-8, 0], [0, 0], [5, 0]],
                   "cross": [[-8, 0], [0, 0], [12, 0]]},
        "approaches": {"left": [[-1, -3], [0, 0], [2, 3]],
                       "right": [[8, 2], [0, 0], [-1, -2]]},
        "diagnostic_fixture": True,
    }
    files["original-attempt/site.json"] = _json(site)
    rows = []
    for index, frame in enumerate(frames):
        actors = [{"actor_id": side + "-synthetic", "side": side,
                   "distance_to_connection_m": (14 if side == "right" else 12) - index,
                   "speed_mps": 2.0} for side in sides]
        rows.append({"case_id": case_id, "frame": index,
                     "native_frame": frame["carla_frame"], "time_s": frame["time_s"],
                     "ego_on_highway": index >= (7 if policy == "yield_all" else 5),
                     "ego_speed_mps": 0 if index < (7 if policy == "yield_all" else 5) else 3,
                     "highway_vehicles": actors})
    motion = "".join(_json(row) for row in rows)
    files["original-attempt/motion.jsonl"] = motion
    files["original-attempt/motion-seal.json"] = _json({
        "format": "worker-private-way-motion-seal", "case_id": case_id,
        "frame_count": 9, "diagnostic_fixture": True,
        "motion_sha256": _sha(motion),
        "site_sha256": _sha(files["original-attempt/site.json"]),
    })
    frame_map = {"case_id": case_id,
                 "frames": [{"frame": index, "native_frame": frame["carla_frame"],
                             "native_time_s": frame["time_s"]}
                            for index, frame in enumerate(frames)]}
    files["original-attempt/frame-map.json"] = _json(frame_map)
    actor_inventory = {"ego_vehicle_id": "ego-synthetic",
                       "highway_vehicles": {side: side + "-synthetic" for side in sides}}
    files["original-attempt/actors.json"] = _json(actor_inventory)
    files["original-attempt/inventory.json"] = _json({
        "case_id": case_id, "source_kind": "synthetic_fixture", "frame_count": 9,
        "motion_sha256": _sha(motion),
        "frame_map_sha256": _sha(files["original-attempt/frame-map.json"]),
        "camera_archives": {name: {"path": name + ".zip", "sha256": "diagnostic-only"}
                            for name in ("overview", "approach", "reference_corner",
                                         "driver_reference")},
        "physical_acceptance_claimed": False,
    })
    files["fixture-provenance.json"] = _json({
        "case_id": case_id, "diagnostic_fixture": True,
        "physical_acceptance_claimed": False,
        "source": "pinned synthetic Core telemetry plus private-way source-shape diagnostic"})
    capture = json.loads(files["capture/manifest.json"])
    capture["case_id"] = case_id
    capture["source_run"] = "synthetic_private_way_diagnostic"
    files["capture/manifest.json"] = json.dumps(capture, indent=2, sort_keys=True) + "\n"
    directory = ROOT / "diagnostics" / variant
    directory.mkdir(parents=True, exist_ok=True)
    generated = directory / "diagnostic.json"
    generated.write_text(json.dumps(diagnostic, separators=(",", ":")) + "\n")
    if generated.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("returned diagnostic exceeds 2 MiB")
    source = str(generated.relative_to(REPO))
    recipe = {"format": "worker-fixture-recipe",
              "sources": [{"path": "diagnostic-input.json", "source": source,
                           "sha256": _sha(generated.read_bytes())}],
              "generator": {"source": source, "sha256": _sha(generated.read_bytes())}}
    (directory / "fixture-recipe.json").write_text(json.dumps(recipe, indent=2,
                                                              sort_keys=True) + "\n")
    return str((directory / "fixture-recipe.json").relative_to(REPO))


def main():
    manifest_path = ROOT / "execution-manifest.draft.json"
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest["cases"]:
        entry["fixture_recipe"] = create(entry["case_id"].removeprefix(ASSIGNMENT + "__"))
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    plan = json.loads((ROOT / "case-plan.json").read_text())
    proposals = []
    for case in plan["cases"]:
        variant = case["variant"]
        construction = json.loads((ROOT / "cases" / variant / "construction.json").read_text())
        proposals.append({
            "case_id": case["case_id"], "target_law_id": "NRS-484B-260",
            "target_type": "delivery", "rationale": case["target_description"],
            "variable_assignments": {
                name: {"kind": "controller" if name == "ego_control_policy" else "world_setup",
                       "value": value, "note": "engineering target; legal judgment unresolved"}
                for name, value in case["draft_variables"].items()},
            "unresolved_judgment_calls": ["private way and public highway source sufficiency",
                                          "all approaching highway vehicles and legal yielding"],
            "recording_description": construction["recording_description"],
        })
    (ROOT / "proposals").mkdir(exist_ok=True)
    (ROOT / "proposals" / "cases.json").write_text(json.dumps({
        "cell_id": "C228096", "actor": "motor_vehicle_driver", "status": "draft",
        "cases": proposals, "sweep_specs": [], "sweeps_expanded": True},
        indent=2, sort_keys=True) + "\n")
    print(len(manifest["cases"]))


if __name__ == "__main__":
    main()
