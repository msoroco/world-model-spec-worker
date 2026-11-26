"""Create explicit nine-frame software fixtures for each exact selected case."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import native_signal as signal


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True,
                               separators=(",", ":"), allow_nan=False) + "\n")


def build():
    scaffold = json.loads((REPO / "runtime/fixtures/example.json").read_text())
    for video, view in zip(scaffold["videos"], signal.VIEWS):
        video["path"] = view + ".mkv"
    write(HERE / "diagnostic-scaffold.json", scaffold)
    scaffold_ref = str((HERE / "diagnostic-scaffold.json").relative_to(REPO))
    for case in signal.CASES:
        folder = HERE / "cases" / case.name / "diagnostic-sources"
        source_records, source_hashes = {}, {}
        for name in signal.SOURCES:
            target = folder / "reviewed-sources" / (name + ".txt")
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("Synthetic diagnostic source for " + name +
                              "; not official or physical evidence.\n")
            digest = sha(target)
            source_records[name] = {"path": str(Path("reviewed-sources") / target.name),
                                    "sha256": digest}
            source_hashes[name + "_source_sha256"] = digest
        line = None if case.reference != "stop_line" else 18.0
        crosswalk = None if case.reference == "nearest_view_point" else 19.0
        site = {
            "source_kind": "reviewed_original_native_signal_site",
            "assignment_id": signal.ASSIGNMENT,
            "case_id": signal.ASSIGNMENT + "__" + case.name,
            "source_records": source_records,
            "signal_id": "diagnostic-signal-A",
            "entrance_ids": ["diagnostic-north", "diagnostic-east"],
            "governing_head_ids": ["diagnostic-head-N1", "diagnostic-head-N2",
                                   "diagnostic-head-E1"],
            "governed_approach": "diagnostic-north",
            "driver_id": "diagnostic-driver", "ego_vehicle_id": "diagnostic-ego",
            "other_vehicle_id": "diagnostic-other", "road_id": 4, "lane_id": -1,
            "through_highway_id": "diagnostic-through",
            "signal_installed": True, "vehicular_heads_uncovered": True,
            "complete_inoperability_at_entry": True,
            "signal_governs_approach": True,
            "through_highway_reviewed": True, "sightline_reviewed": True,
            "blind_intersection_reviewed": True,
            "physical_occluder_reviewed": True,
            "intersection_entry_m": 22.0, "stop_line_m": line,
            "near_crosswalk_m": crosswalk,
            "nearest_view_point_m": 20.0,
            "other_state": case.other_state,
            "ego_policy": case.ego_policy,
            "ego_route_station_m": [0.0, 30.0],
            "other_route_station_m": [0.0, 30.0],
            "map_sha256": sha(REPO / "runtime/library/road.xodr")
            if (REPO / "runtime/library/road.xodr").is_file() else "diagnostic-map-only",
            **source_hashes}
        write(folder / "site.json", site)
        ego_rows, other_rows, frame_map = [], [], []
        stop_station = {
            "stop_line": 17.0, "near_crosswalk": 18.0,
            "nearest_view_point": 19.0}[case.reference]
        front = [10.0, 12.0, 14.0, 16.0, stop_station,
                 stop_station, 20.0, 22.0, 23.0]
        for index in range(9):
            frame, time_s = 38033 + index, round(.05 * (index + 1), 5)
            common = {name + "_source_sha256": source_hashes[name + "_source_sha256"]
                      for name in signal.SOURCES}
            ego_rows.append({"original_frame": frame, "source_frame_id": frame,
                             "time_s": time_s, "vehicle_id": "diagnostic-ego",
                             "signal_id": "diagnostic-signal-A",
                             "approach_id": "diagnostic-north",
                             "front_m": front[index],
                             "speed_mps": 0.0 if index == 5 else 2.0,
                             "signal_installed": True, "signal_uncovered": True,
                             "signal_operating": False,
                             "governing_head_operating": {
                                 "diagnostic-head-N1": False,
                                 "diagnostic-head-N2": False,
                                 "diagnostic-head-E1": False},
                             "all_heads_wholly_inoperative": True,
                             **common})
            other_rows.append({"original_frame": frame, "source_frame_id": frame,
                               "time_s": time_s, "vehicle_id": "diagnostic-other",
                               "signal_id": "diagnostic-signal-A",
                               "front_m": float(index),
                               "speed_mps": 0.0 if case.other_state == "prior_stop" and index == 2 else 2.0,
                               "within_intersection": case.other_state == "within" and index == 5,
                               "cleared_conflict_zone": index >= (4 if case.other_state == "none" else
                                                                    6 if case.ego_policy == "yield" else 8),
                               **common})
            frame_map.append({"frame_index": index, "native_frame": frame,
                              "time_s": time_s})
        write(folder / "ego-history.json", ego_rows)
        write(folder / "other-history.json", other_rows)
        write(folder / "frame-map.json", frame_map)
        signal.measure_original(site, folder / "site.json", case,
                                ego_rows, other_rows, diagnostic=True)
        sources = {key: {"path": name, "sha256": sha(folder / name)}
                   for key, name in (("site", "site.json"),
                                     ("ego_history", "ego-history.json"),
                                     ("other_history", "other-history.json"),
                                     ("frame_map", "frame-map.json"))}
        write(folder / "inventory.json", {
            "case_id": site["case_id"], "source_kind": "original_native",
            "frame_count": 9, "camera_views": list(signal.VIEWS),
            "reviewed_site_sha256": sha(folder / "site.json"),
            "sources": sources})
        recipe_sources = []
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                destination = str(path.relative_to(folder))
                recipe_sources.append({"path": destination,
                                       "source": str(path.relative_to(REPO)),
                                       "sha256": sha(path)})
        write(HERE / "cases" / case.name / "fixture-recipe.json", {
            "format": "worker-fixture-recipe",
            "generator": {"source": scaffold_ref,
                          "sha256": sha(HERE / "diagnostic-scaffold.json")},
            "sources": recipe_sources})
    return len(signal.CASES)


if __name__ == "__main__":
    print(build())
