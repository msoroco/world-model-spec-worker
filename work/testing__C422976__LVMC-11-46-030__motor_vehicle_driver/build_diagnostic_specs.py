"""Build software-only school-lane fixtures; never evidence of Native success."""

import hashlib
import json
from pathlib import Path

from school_lane_controls import ASSIGNMENT, selected_schedule


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
BASE = REPO / "work/testing__C227824__NRS-484B-307-9c__pedestrian/cases/enter_no_other_device/diagnostic-spec.json"
BASE_MAP = REPO / "work/testing__C227824__NRS-484B-307-9c__pedestrian/diagnostic-map.xodr"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":"), sort_keys=True) + "\n")


def rows(case_id):
    schedule = selected_schedule(case_id, 100.0)
    station = 55.0
    target = schedule["ego_stop_reference_station_target_m"]
    output = []
    for frame in range(900):
        release = schedule["release_frame"]
        if target is None:
            speed = 6.0
        elif station < target - .3:
            speed = 6.0
        elif schedule["requested_ego_response"] == "premature" and frame >= 400:
            speed = 6.0
        elif release is not None and frame >= release and schedule["requested_ego_response"] == "proceed":
            speed = 6.0
        else:
            speed = 0.0
        station += speed / 20
        kind = schedule["requested_warning_actor"]
        onset = schedule["warning_on_from_frame"]
        warning = kind == "human" and onset is not None and frame >= onset and (
            release is None or frame < release or schedule["requested_release"] == "continued")
        row = {"frame": frame, "time_s": frame/20,
               "ego_reference_station_m": round(station, 5), "ego_speed_mps": speed,
               "human_warning_active": warning,
               "person_stationed": kind in ("human", "human_present") and not (
                   schedule["requested_release"] == "depart" and release is not None and frame >= release),
               "children_about_to_cross_or_crossing": kind in ("human", "device") and frame >= 100,
               "human_go_signal": kind == "human" and schedule["requested_release"] == "go" and
                   release is not None and frame >= release,
               "human_left_locality": kind == "human" and schedule["requested_release"] == "depart" and
                   release is not None and frame >= release,
               "device_signal_stopped_raised_or_removed": kind == "device" and
                   release is not None and frame >= release}
        output.append(row)
    return output


def main():
    map_bytes = BASE_MAP.read_bytes()
    (HERE / "diagnostic-map.xodr").write_bytes(map_bytes)
    base = json.loads(BASE.read_text())
    proposal = json.loads((HERE / "proposals/cases.json").read_text())
    cases = [c for c in proposal["cases"] if c.get("target_law_id")]
    for case in cases:
        case_id = case["case_id"]
        data = json.loads(json.dumps(base))
        frames = rows(case_id)
        context = {"assignment_id": ASSIGNMENT, "case_id": case_id,
                   "diagnostic_fixture": True, "school_lane_nearest_side_station_m": 100.0,
                   "vehicle_reference_point": "front_body_extent"}
        for name in ("municipal_jurisdiction_source", "school_pedestrian_lane_source",
                     "nearest_side_geometry_source", "ego_connected_approach_source",
                     "road_lane_identity_source", "responsible_person_source", "vehicle_source",
                     "stationed_person_identity_source", "human_warning_source",
                     "children_presence_source", "human_signal_source", "person_location_source",
                     "vehicle_body_reference_source", "driver_view_camera_source"):
            context[name] = "synthetic CPU fixture; no physical authority"
        data["files"]["context.json"] = json.dumps(context, separators=(",", ":")) + "\n"
        data["files"]["trace.json"] = json.dumps({"case_id": case_id, "diagnostic_fixture": True,
                                                    "frames": frames}, separators=(",", ":")) + "\n"
        data["files"]["site.json"] = json.dumps({"diagnostic_fixture": True,
            "reviewed_original_site": False, "case_id": case_id}, separators=(",", ":")) + "\n"
        motion = []
        evidence = []
        for frame, line in zip(frames, data["files"]["trace.jsonl"].splitlines()):
            value = json.loads(line)
            x = frame["ego_reference_station_m"]
            value.update(position_m=[x, 0, 0], position={"x": x, "y": 0, "z": 0},
                         speed_mps=frame["ego_speed_mps"],
                         speed_mph=frame["ego_speed_mps"]*2.2369362921,
                         velocity_mps=[frame["ego_speed_mps"], 0, 0])
            motion.append(json.dumps(value, separators=(",", ":")))
        data["files"]["trace.jsonl"] = "\n".join(motion) + "\n"
        for frame, line in zip(frames, data["files"]["capture/evidence.jsonl"].splitlines()):
            value = json.loads(line)
            x = frame["ego_reference_station_m"]
            value["ego"]["position_m"] = [x, 0, 0]
            value["ego"]["speed_mps"] = frame["ego_speed_mps"]
            value["ego"]["body_vertices_m"] = [[x + dx, dy, z]
                for dx in (-2.0, 2.0) for dy in (-.8, .8) for z in (0, 1.5)]
            evidence.append(json.dumps(value, separators=(",", ":")))
        data["files"]["capture/evidence.jsonl"] = "\n".join(evidence) + "\n"
        data["files"]["capture/recorder_info.txt"] = "Create 11: vehicle.test (synthetic) at school-lane approach\n"
        manifest = json.loads(data["files"]["capture/manifest.json"])
        manifest["case_id"] = case_id
        manifest["sources"] = {"road.xodr": sha(map_bytes),
                               "trace.jsonl": sha(data["files"]["trace.jsonl"].encode())}
        data["files"]["capture/manifest.json"] = json.dumps(manifest, separators=(",", ":")) + "\n"
        data["files"].pop("road.xodr", None)
        case_folder = HERE / "cases" / case_id.rsplit("__", 1)[-1]
        spec_path = case_folder / "diagnostic-spec.json"
        write(spec_path, data)
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "road.xodr", "source": "work/" + ASSIGNMENT + "/diagnostic-map.xodr",
                               "sha256": sha(map_bytes)}],
                  "generator": {"source": str(spec_path.relative_to(REPO)),
                                "sha256": sha(spec_path.read_bytes())}}
        write(case_folder / "diagnostic-recipe.json", recipe)
        if spec_path.stat().st_size > 2*1024*1024:
            raise ValueError("diagnostic spec exceeds returned file limit")
    print("Built 15 bounded synthetic school-lane diagnostic recipes")


if __name__ == "__main__":
    main()
