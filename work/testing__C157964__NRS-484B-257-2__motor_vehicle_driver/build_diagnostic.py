"""Create text-only synthetic sources for exact officer software compatibility."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = REPO / "work/testing__C158208__NRS-484B-257-2__motor_vehicle_driver/diagnostic-occupied_response.json"
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")
SOURCES = ("map_opendrive", "jurisdiction", "intersection_geometry",
           "entrance_controls", "officer_location", "officer_directive_visibility",
           "other_obligation", "ego_route", "other_route", "camera_sightlines")


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def encoded(value):
    return json.dumps(value, sort_keys=True) + "\n"


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    base = json.loads(BASE.read_text())
    traces = [json.loads(line) for line in base["files"]["trace.jsonl"].splitlines()]
    videos = [json.loads(line) for line in base["files"]["video_frames.jsonl"].splitlines()]
    if len(traces) != 9 or len(videos) != 9:
        raise ValueError("synthetic scaffold changed")
    for case in plan["cases"]:
        case_id = case["case_id"]
        suffix = case_id.removeprefix(ROOT.name + "__")
        variables = case["draft_variables"]
        files = {name: value for name, value in base["files"].items()
                 if not name.startswith("original-attempt/")}
        sources = {}
        for name in SOURCES:
            relative = "original-attempt/source-review/" + name + ".txt"
            files[relative] = "synthetic officer " + name + "\n"
            sources[name] = {"path": "source-review/" + name + ".txt",
                             "sha256": sha(files[relative].encode())}
        site = {"format": "c157964-reviewed-officer-site-v1",
                "cell_id": plan["cell_id"], "law_id": plan["law_id"],
                "actor": plan["actor"], "case_id": case_id,
                "control": "police_officer", "signal_controls": False,
                "layout": "one_way_to_two_way_intersection", "maneuver": "straight",
                "officer_controls_traffic": True,
                "non_through_highway": True,
                "officer_visible_from_ego_approach": True,
                "other_vehicle_obligated_to_stop_or_yield": False,
                "ego_route_xy": [[-15, 0], [0, 0], [15, 0]],
                "other_spawn_xy": [0, -15], "officer_spawn_xy": [4, -4],
                "officer_lateral_offset_limit_m": 1.5,
                "intersection_entry_station_m": 0,
                "upstream_reference_station_m": -3,
                "entrances": [{"id": "ego", "control": "yield",
                               "reviewed_source": "synthetic fixture"},
                              {"id": "other", "control": "none",
                               "reviewed_source": "synthetic fixture"}],
                "sources": sources}
        for name in SOURCES:
            if name != "map_opendrive":
                site[name + "_source_sha256"] = sources[name]["sha256"]
        files["original-attempt/site-packet.json"] = encoded(site)
        rows = []
        mapping = []
        for index, (trace, video) in enumerate(zip(traces, videos)):
            frame = trace["frame"]
            time_s = trace["time_s"]
            station = -3.0 if index < 4 else 1.0 + .1 * (index - 4)
            state = {"ego": {"id": "fixture-ego", "speed_mps": 2.0,
                              "leading_station_m": station,
                              "across_or_within": index >= 4},
                     "other": {"id": "fixture-other",
                               "center_station_m": variables["requested_other_station_m"] - .1 * index,
                               "phase": variables["other_phase"] if index <= 6 else "cleared"},
                     "officer": {"id": "fixture-officer", "controls_traffic": True,
                                 "visible": True,
                                 "directive": variables["officer_directive"]},
                     "officer_directive": variables["officer_directive"]}
            rows.append({"case_id": case_id, "frame": frame,
                         "elapsed_s": index / 20, "time_s": time_s,
                         "state": state, "camera_frames": {}})
            mapping.append({"frame": index, "carla_frame": frame,
                            "elapsed_s": index / 20, "time_s": time_s})
        for view in VIEWS:
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, "w", zipfile.ZIP_STORED) as archive:
                for index, row in enumerate(rows):
                    raw = b"\x89PNG\r\n\x1a\n" + (view + "-" + str(index)).encode()
                    filename = f"{index:04d}-{row['frame']}.png"
                    archive.writestr(filename, raw)
                    row["camera_frames"][view] = {"member": filename, "sha256": sha(raw)}
            files["original-attempt/" + view + ".zip.b64"] = \
                base64.b64encode(buffer.getvalue()).decode() + "\n"
        files["original-attempt/history.json"] = encoded(rows)
        files["original-attempt/frame-map.json"] = encoded(mapping)
        files["original-attempt/officer-review.json"] = encoded({
            "case_id": case_id, "source_kind": "synthetic_review",
            "reviewer_id": "synthetic software fixture",
            "officer_visible": True, "officer_controlling_traffic": True,
            "observed_directive": variables["officer_directive"],
            "crossing_interval_frames": [3, 8]})
        inventory_names = ["original-attempt/history.json",
                           "original-attempt/frame-map.json",
                           "original-attempt/site-packet.json",
                           "trace.jsonl", "video_frames.jsonl"]
        inventory_names += ["original-attempt/source-review/" + name + ".txt"
                            for name in SOURCES]
        inventory_names += ["original-attempt/" + view + ".zip.b64" for view in VIEWS]
        inventory = {name: sha(files[name].encode()) for name in inventory_names}
        seal = {
            "format": "c157964-synthetic-capture-seal-v1",
            "case_id": case_id, "frame_count": len(rows),
            "diagnostic_fixture": True, "provenance_kind": "synthetic_fixture",
            "events": ["capture_finished", "encoders_closed", "restoration_verified"],
            "source_sha256": inventory, "sources": inventory,
            "native_revision": {
                "construction_sha256": sha((ROOT / f"cases/{suffix}/construction.json").read_bytes()),
                "runner_sha256": sha((ROOT / "runner.py").read_bytes())},
            "physical_acceptance_claimed": False, "legal_judgment": None}
        files["capture-seal.json"] = encoded(seal)
        files["native-exit.json"] = encoded({
            "event": "native_exit", "capture_seal_sha256": sha(files["capture-seal.json"].encode()),
            "native_revision": seal["native_revision"]})
        files["fixture-provenance.json"] = encoded({
            "diagnostic_fixture": True, "scope": "synthetic officer software compatibility",
            "physical_acceptance_claimed": False, "legal_acceptance_claimed": False,
            "frames": len(rows)})
        capture_manifest = json.loads(files["capture/manifest.json"])
        capture_manifest["case_id"] = case_id
        capture_manifest["acquisition"] = "synthetic_diagnostic_fixture"
        capture_manifest["source_run"] = "fixture:officer-software-compatibility"
        capture_manifest["sources"]["trace.jsonl"] = sha(files["trace.jsonl"].encode())
        files["capture/manifest.json"] = encoded(capture_manifest)
        diagnostic = {"files": files, "graphs": base["graphs"],
                      "videos": base["videos"]}
        path = ROOT / ("diagnostic-" + suffix + ".json")
        path.write_text(encoded(diagnostic))
        digest = sha(path.read_bytes())
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "diagnostic-input.json",
                               "source": "work/" + ROOT.name + "/" + path.name,
                               "sha256": digest}],
                  "generator": {"source": "work/" + ROOT.name + "/" + path.name,
                                "sha256": digest}}
        (ROOT / ("diagnostic-" + suffix + "-recipe.json")).write_text(
            encoded(recipe))
        print(suffix, path.stat().st_size)


if __name__ == "__main__":
    main()
