"""Compare exact diagnostic source histories without claiming Native acceptance."""

import argparse
import hashlib
import json
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon

HERE = Path(__file__).resolve().parent
NAMES = ("primary", "at-red", "after-red", "yellow-stop")
CASE_SUFFIXES = ("entry_before_red", "entry_at_red", "entry_after_red", "stops_on_yellow")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect(name, *, corrupt=False):
    path = HERE / (name + "-diagnostic-sources.json")
    source = json.loads(path.read_text())
    files = source["files"]
    context = json.loads(files["junction_context.json"])
    history = [json.loads(line) for line in files["signal_vehicle_history.jsonl"].splitlines()]
    frames = [json.loads(line) for line in files["video_frames.jsonl"].splitlines()]
    if corrupt:
        history[0]["lane_id"] += 1
    if len(history) != 900 or len(frames) != 900:
        raise ValueError("Incomplete original diagnostic frame history")
    polygon = Polygon(context["intersection_polygon_xy_m"])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError("Invalid source intersection polygon")
    states, times, speeds = [], [], []
    first_entry = red_onset = None
    previous_inside = False
    for index, (row, frame) in enumerate(zip(history, frames)):
        if (row["frame"] != index or frame["video_frame"] != index or
                frame["carla_frame"] != row["frame"] or frame["time_s"] != row["time_s"]):
            raise ValueError("Original source frame join differs")
        if (row["native_signal_id"] != context["native_signal_id"] or
                row["road_id"] != context["governed_road_id"] or
                row["lane_id"] != context["governed_lane_id"]):
            raise ValueError("Original governed signal or lane differs")
        if row["signal_state"] not in ("Green", "Yellow", "Red"):
            raise ValueError("Invalid original signal state")
        body = MultiPoint(row["ego_body_vertices_xy_m"]).convex_hull
        inside = body.intersects(polygon)
        if index and states[-1] == "Yellow" and row["signal_state"] == "Red" and red_onset is None:
            red_onset = index
        if inside and not previous_inside and first_entry is None:
            first_entry = index
        previous_inside = inside
        states.append(row["signal_state"])
        times.append(row["time_s"])
        speeds.append(row["ego_speed_mps"])
    if red_onset is None or any(abs(time - index / 20) > 1e-7 for index, time in enumerate(times)):
        raise ValueError("Original signal transition or timebase differs")
    return {"source": path.name, "source_sha256": sha(path), "context": context,
            "signal_states": states, "times": times, "speeds": speeds,
            "red_onset_frame": red_onset, "first_entry_frame": first_entry,
            "video_profiles": source["videos"]}


def compare(*, corrupt=False):
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    entries = {item["case_id"].removeprefix(HERE.name + "__"): item
               for item in manifest["cases"]}
    if set(entries) != set(CASE_SUFFIXES):
        raise ValueError("Current manifest does not cover the selected comparison cases")
    for name, suffix in zip(NAMES, CASE_SUFFIXES):
        recipe = HERE.parents[1] / entries[suffix]["fixture_recipe"]
        recipe_data = json.loads(recipe.read_text())
        source = HERE / (name + "-diagnostic-sources.json")
        if (recipe_data["generator"]["source"] != str(source.relative_to(HERE.parents[1])) or
                recipe_data["generator"]["sha256"] != sha(source)):
            raise ValueError("Current manifest fixture recipe differs from compared source")
    data = [inspect(name, corrupt=corrupt and name == "after-red") for name in NAMES]
    base = data[0]
    for other in data[1:]:
        for key in ("native_map_id", "intersection_id", "native_signal_id", "governed_road_id",
                    "governed_lane_id", "intersection_polygon_xy_m"):
            if other["context"][key] != base["context"][key]:
                raise ValueError("Comparison fixed source context differs: " + key)
        if (other["signal_states"] != base["signal_states"] or
                other["times"] != base["times"] or
                other["video_profiles"] != base["video_profiles"]):
            raise ValueError("Comparison fixed signal or capture profile differs")
    before, at, after, stopped = data
    red = base["red_onset_frame"]
    if not (before["first_entry_frame"] is not None and before["first_entry_frame"] < red and
            at["first_entry_frame"] == red and
            after["first_entry_frame"] is not None and after["first_entry_frame"] > red and
            stopped["first_entry_frame"] is None):
        raise ValueError("Comparison entry timing differs from selected branches")
    if (before["speeds"][:red] != at["speeds"][:red] or
            before["speeds"][:red] != after["speeds"][:red]):
        raise ValueError("Red-entry comparison approach speed differs")
    return {"format": "worker-cpu-source-comparison-diagnostic", "passed": True,
            "physical_acceptance_claimed": False, "source_specifications": {
                name: {"path": item["source"], "sha256": item["source_sha256"]}
                for name, item in zip(NAMES, data)},
            "fixed_checks": ["signal_actor", "governed_lane", "intersection_polygon",
                             "signal_sequence", "timebase", "capture_profiles",
                             "red_entry_approach_speed"],
            "red_onset_frame": red,
            "first_entry_frames": {case: item["first_entry_frame"]
                                   for case, item in zip(CASE_SUFFIXES, data)},
            "comparison_ids": ["red_entry_timing", "yellow_entry_vs_stop"],
            "manifest_sha256": sha(manifest_path)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-governance", action="store_true")
    args = parser.parse_args()
    print(json.dumps(compare(corrupt=args.negative_governance), sort_keys=True))
