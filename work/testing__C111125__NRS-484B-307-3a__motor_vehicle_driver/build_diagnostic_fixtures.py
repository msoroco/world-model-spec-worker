"""Author five-frame synthetic source packets for pinned compatibility.

The generic Core scaffold was copied from the bus green-arrow diagnostic. Its
extra bus files are ignored here; all dual-green source packets are new and
explicitly marked synthetic. No physical or legal acceptance follows.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PREFIX = HERE.name + "__"
SUFFIXES = ("dual_clear", "dual_vehicle_present", "dual_pedestrian_present",
            "dual_pedestrian_late")


def encode(value):
    return json.dumps(value, sort_keys=True, allow_nan=False) + "\n"


def ref(files, name, value):
    content = encode(value)
    files[name] = content
    return {"path": name, "sha256": hashlib.sha256(content.encode()).hexdigest()}


def build_case(suffix, seed, road):
    files = copy.deepcopy(seed["files"])
    case_id = PREFIX + suffix
    names = ("map", "route", "signal", "crosswalk", "permission")
    sources = [ref(files, "diagnostic-source-" + name + ".json", {
        "format": "synthetic-dual-green-site-source", "kind": name,
        "physical_review": False}) for name in names]
    site = {
        "cell_id": "C111125", "actor": "motor_vehicle_driver",
        "original_sources": sources,
        "map_source_path": sources[0]["path"],
        "route_source_path": sources[1]["path"],
        "signal_survey_path": sources[2]["path"],
        "crosswalk_source_path": sources[3]["path"],
        "movement_permission_source_path": sources[4]["path"],
        "official_head_id": "5", "ego_approach_id": "east",
        "facing_relation": True, "arrow_direction": "left",
        "ego_movement": "straight", "straight_permission_review": "source_review_pending",
        "ego_route_xy": [[9.0, -1.8], [10.8, -1.8], [12.5, -1.8]],
        "straight_tolerance_m": .01,
        "intersection_polygon_xy": [[10.5, -3], [11.2, -3], [11.2, 0], [10.5, 0]],
        "adjacent_crosswalk_polygon_xy": [[10, 3], [12, 3], [12, 5], [10, 5]],
    }
    files["site.json"] = encode(site)
    frames = []
    events = []
    for frame in range(5):
        marker = ref(files, f"synthetic-lamp-{frame}.json", {
            "format": "synthetic-dual-green-lamp-observation",
            "frame": frame, "physical_observation": False})
        lamp = ref(files, f"lamp-{frame}.json", {
            "frame": frame, "official_head_id": "5", "facing_approach_id": "east",
            "lit_aspects": ["circular_green", "green_left_arrow"],
            "original_observation": marker,
        })
        user_rows = []
        lawful_refs = {}
        if suffix != "dual_clear":
            kind = "motor_vehicle" if suffix == "dual_vehicle_present" else "pedestrian"
            xy = [10.8, -1.8] if kind == "motor_vehicle" else [10.8,
                6.0 if suffix == "dual_pedestrian_late" and frame == 0 else 4.0]
            lawful = ref(files, f"lawful-{frame}.json", {
                "frame": frame, "user_id": "2", "review": "synthetic_unresolved",
                "lawful_use_confirmed": False})
            lawful_refs["2"] = lawful
            user_rows.append({"id": "2", "kind": kind, "xy": xy,
                              "lawful_use_source": lawful["path"],
                              "lawful_use_sha256": lawful["sha256"]})
        frames.append({"carla_frame": frame, "lamp": lamp,
                       "lawful_use": lawful_refs})
        events.append({"frame": frame, "elapsed_seconds": frame * .05,
                       "official_head_id": "5", "facing_approach_id": "east",
                       "aspect_observation_source": lamp["path"],
                       "aspect_observation_sha256": lamp["sha256"],
                       "lit_aspects": ["circular_green", "green_left_arrow"],
                       "ego_xy": [10 + .4 * frame, -1.8],
                       "other_users": user_rows})
    files["original-source-handoff.json"] = encode({
        "format": "dual-green-original-source-handoff", "case_id": case_id,
        "official_head_id": "5", "facing_approach_id": "east",
        "observer_method": "synthetic_diagnostic", "frames": frames})
    files["original-events.json"] = encode(events)
    files["road.xodr"] = road
    files["carla_recorder.log"] = "Synthetic diagnostic recorder placeholder\n"
    capture = json.loads(files["capture/manifest.json"])
    capture["case_id"] = case_id
    capture["acquisition"] = "synthetic_diagnostic_fixture"
    capture["extraction_confirmed"] = True
    capture["diagnostic_fixture"] = True
    capture["sources"]["road.xodr"] = hashlib.sha256(road.encode()).hexdigest()
    files["capture/manifest.json"] = encode(capture)
    return {"files": files, "graphs": copy.deepcopy(seed["graphs"]),
            "videos": copy.deepcopy(seed["videos"])}


def main():
    seed = json.loads((HERE / "generic-core-scaffold.json").read_text())
    source = Path("work/testing__C147332__NRS-484B-307-12a__bus_driver/cases/green_selected_drive/construction.json")
    construction = json.loads(source.read_text())
    road = next(item["content"] for item in construction["files"] if item["path"] == "road.xodr")
    note = HERE / "diagnostic-fixture-note.txt"
    note.write_text("Synthetic five-frame dual-green software fixture; no physical or legal acceptance.\n")
    manifest_path = HERE / "execution-manifest.draft.json"
    manifest = json.loads(manifest_path.read_text())
    manifest["format"] = "worker-execution-manifest"
    manifest["runtime_manifest_sha256"] = "5e2dd81ac49dd2d9814a10b71ee30cf85323868a8369116020b06a69cbfcc5e3"
    for row, suffix in zip(manifest["cases"], SUFFIXES):
        spec_path = HERE / ("diagnostic-" + suffix + ".json")
        spec_path.write_text(encode(build_case(suffix, seed, road)))
        recipe_path = HERE / ("fixture-recipe-" + suffix + ".json")
        recipe = {"format": "worker-fixture-recipe", "sources": [{
            "path": "diagnostic-fixture-note.txt",
            "source": str(note.relative_to(Path.cwd())),
            "sha256": hashlib.sha256(note.read_bytes()).hexdigest()}],
            "generator": {"source": str(spec_path.relative_to(Path.cwd())),
                          "sha256": hashlib.sha256(spec_path.read_bytes()).hexdigest()}}
        recipe_path.write_text(encode(recipe))
        row["fixture_recipe"] = str(recipe_path.relative_to(Path.cwd()))
        acquisition = {}
        for name in ("signal_head_history", "ego_body_history",
                     "vehicle_body_history", "pedestrian_body_history",
                     "intersection_geometry", "crosswalk_geometry",
                     "lawful_presence_context", "original_lamp_pixels"):
            producer = ("source_handoff.py" if name in
                        ("signal_head_history", "lawful_presence_context") else
                        "native_cameras.py" if name == "original_lamp_pixels" else
                        "native_attempt.py")
            acquisition[name] = {
                "entrypoint": producer,
                "method": "same-frame original source acquisition and saved channel projection",
                "evidence": name + ".jsonl",
            }
        acquisition["site_source_survey"] = {
            "entrypoint": "dual_green.py",
            "method": "source-hashed site survey and exact geometry check",
            "evidence": "site-source-survey.json",
        }
        row["acquisition"] = acquisition
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")
    print("built", len(SUFFIXES), "synthetic dual-green diagnostic fixture recipes")


if __name__ == "__main__":
    main()
