"""Author explicit nine-frame software fixtures for each selected signal case.

The seed graph is a supplied diagnostic projection. It is never original site,
actor, signal, district or physical evidence for this assignment.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SEED = REPO / "work/testing__C111610__NRS-484B-307-4a__motor_vehicle_driver/diagnostic-crosswalk_clear_turn.json"
PLAN = json.loads((ROOT / "case-plan.json").read_text())


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("returned diagnostic specification exceeds 2 MiB")


def main() -> None:
    seed = json.loads(SEED.read_text())
    frame_map = [json.loads(line) for line in seed["files"]["video_frames.jsonl"].splitlines()]
    if len(frame_map) != 9:
        raise ValueError("diagnostic seed must have nine source frames")
    site_spec = importlib.util.spec_from_file_location("signal_test_site", ROOT / "test_signal_construction.py")
    site_module = importlib.util.module_from_spec(site_spec)
    site_spec.loader.exec_module(site_module)
    for case in PLAN["cases"]:
        case_id = case["case_id"]
        tag = case_id.rsplit("__", 1)[-1]
        spec = json.loads(SEED.read_text())
        district = ("residential" if tag.startswith("residence_") else
                    "other" if tag.startswith("other_area_") else "business")
        site = dict(site_module.site(district), diagnostic_fixture=True)
        site_text = json.dumps(site, sort_keys=True) + "\n"
        weather = "rain" if tag == "business_weather_rain" else "clear"
        start = (2 if tag.endswith("_short") and district == "other" else
                 3 if tag.endswith("_short") else
                 0 if tag.endswith("_continuous") or tag == "business_weather_rain" else
                 1)
        spacing_m = 14.0 if district == "other" else 5.1
        rows = []
        body_rows = []
        for index, mapped in enumerate(frame_map):
            x = spacing_m * index
            heading = -90 if index == 8 else -25 if index == 7 else 0
            signal = index >= start
            corners = [[x + dx, dy] for dx in (-1, 1)
                       for dy in (-.5, .5) for _ in (0, 1)]
            rows.append({"frame": mapped["carla_frame"], "time_s": mapped["time_s"],
                         "x_m": x, "y_m": 0, "heading_deg": heading,
                         "right_signal": signal, "course_change": index == 8,
                         "weather": weather, "body_vertices_m": corners,
                         "camera_frames": {name: {"video_frame": index,
                                                  "source_kind": "diagnostic_fixture"}
                                           for name in ("overview", "approach",
                                                        "reference_corner", "driver_reference")}})
            body_rows.append({"frame": mapped["carla_frame"], "time_s": mapped["time_s"],
                              "body_vertices_m": corners, "heading_deg": heading})
        context = {key: site[key] for key in ("highway_source", "district_source",
                   "frontage_source", "building_use_source", "freight_zone_source",
                   "route_source", "driver_source", "camera_rig_source")}
        context.update(district_kind=district, maneuver="right_turn",
                       weather_source="diagnostic " + weather)
        packet = {"format": "native-turn-signal-samples-v1", "source_kind": "diagnostic_fixture",
                  "diagnostic_fixture": True, "case_id": case_id,
                  "ego_actor": "motor_vehicle_driver", "context": context,
                  "site_sha256": hashlib.sha256(site_text.encode()).hexdigest(),
                  "sampling_hz": 20, "frame_count": 9, "samples": rows}
        spec["files"]["original-site.json"] = site_text
        spec["files"]["original-turn-signal.json"] = json.dumps(packet, sort_keys=True) + "\n"
        spec["files"]["body_history.jsonl"] = "\n".join(json.dumps(row) for row in body_rows) + "\n"
        spec["files"]["fixture-provenance.json"] = json.dumps({
            "diagnostic_fixture": True, "physical_acceptance_claimed": False,
            "case_specific_sources": ["original-site.json", "original-turn-signal.json",
                                      "video_frames.jsonl"]}) + "\n"
        manifest = json.loads(spec["files"]["capture/manifest.json"])
        manifest["case_id"] = case_id
        spec["files"]["capture/manifest.json"] = json.dumps(manifest, sort_keys=True) + "\n"
        spec_path = ROOT / ("diagnostic-" + tag + ".json")
        dump(spec_path, spec)
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "diagnostic-input.json",
                               "source": spec_path.relative_to(REPO).as_posix(),
                               "sha256": sha(spec_path)}],
                  "generator": {"source": spec_path.relative_to(REPO).as_posix(),
                                "sha256": sha(spec_path)}}
        dump(ROOT / ("diagnostic-" + tag + "-recipe.json"), recipe)


if __name__ == "__main__":
    main()
