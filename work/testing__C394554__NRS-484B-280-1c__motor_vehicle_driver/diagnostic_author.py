"""Build bounded synthetic transit source text for CPU compatibility only."""
import hashlib
import json
from pathlib import Path

from road_scene import measure, load_site


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def body(x, y):
    return [[x, y, 0], [x + 1, y, 0], [x + 1, y + 1, 0], [x, y + 1, 0]]


def write_case(phase):
    fixture = json.loads((REPO / "runtime/fixtures/example.json").read_text())
    files = fixture["files"]
    trace = [json.loads(line) for line in files["trace.jsonl"].splitlines() if line.strip()]
    if len(trace) != 9:
        raise ValueError("pinned diagnostic frame count changed")
    files["map.xodr"] = "<OpenDRIVE>diagnostic transit-road text</OpenDRIVE>\n"
    bus_body = body(0, 3)
    site = {"format": "worker-transit-stop-site", "cell_id": "C394554",
            "layout": "road", "control": "bus_stop",
            "map_source": {"path": "map.xodr", "sha256": digest(files["map.xodr"])},
            "road": {"road_id": 9, "lane_source": "diagnostic Native-shaped waypoint"},
            "stop": {"actor_id": 30, "blueprint_id": "static.prop.busstop",
                     "position_m": [0, 6, 0], "position_source": "diagnostic actor transform"},
            "bus": {"actor_id": 40, "blueprint_id": "vehicle.mitsubishi.fusorosa",
                    "position_m": [1, 4.5, 0], "body_vertices_m": bus_body,
                    "door_side_source": "diagnostic bus-body curb proxy",
                    "door_region_source": "diagnostic bus-body proxy, actual door unverified",
                    "door_region_m": {"x_min": 0, "x_max": 1, "y_min": 4, "y_max": 4.5}},
            "diagnostic_only": True}
    files["transit-site.json"] = json.dumps(site, sort_keys=True) + "\n"
    history = []
    for i, frame in enumerate(trace):
        ego = body(-12 + i, 0)
        pedestrian = body(0, 5 - 0.1 * i if phase == "boarding_bus" else 5)
        event = ({"source": "original_driver_input", "observed": True,
                  "kind": "diagnostic_scripted_input"} if i >= 2 else None)
        sample = {"frame": frame["frame"], "time_s": frame["time_s"],
                  "ego_body_vertices_m": ego, "pedestrian_body_vertices_m": pedestrian,
                  "bus_body_vertices_m": bus_body, "bus_actor_id": 40, "stop_actor_id": 30,
                  "ego_class": "motor_vehicle", "pedestrian_class": "pedestrian",
                  "ego_class_source": "diagnostic/blueprint", "pedestrian_class_source": "diagnostic/blueprint",
                  "driver_control_source": "diagnostic/scripted-driver-input",
                  "driver_observation_event": event, "ego_speed_mps": 4,
                  "ego_brake": int(i >= 2), "passenger_phase": phase,
                  "contact_event": False}
        # Derive reported metrics from the same body geometry the saved analyzer rechecks.
        pedestrian_box = (0, pedestrian[0][1], 1, pedestrian[2][1])
        door = site["bus"]["door_region_m"]
        sample["pedestrian_stop_distance_m"] = ((0.5 - 0) ** 2 +
            ((pedestrian_box[1] + pedestrian_box[3]) / 2 - 6) ** 2) ** 0.5
        sample["pedestrian_bus_door_region_gap_m"] = max(pedestrian_box[1] - door["y_max"], 0)
        history.append(sample)
    files["encounter-history.jsonl"] = "".join(json.dumps(row, sort_keys=True) + "\n" for row in history)
    names = ("map.xodr", "transit-site.json", "encounter-history.jsonl", "video_frames.jsonl")
    files["acquisition.json"] = json.dumps({name: {"kind": "original_native", "sha256": digest(files[name])}
                                             for name in names}, sort_keys=True) + "\n"
    files["fixture-provenance.json"] = json.dumps({"scope": "CPU synthetic source text only",
        "case_specific_sources": list(names), "physical_acceptance_claimed": False,
        "actual_door_verified": False, "human_observation_claimed": False}) + "\n"
    path = ROOT / ("diagnostic-" + phase + ".json")
    path.write_text(json.dumps(fixture, ensure_ascii=False, separators=(",", ":")) + "\n")
    assignment = ROOT / "assignment.json"
    recipe = {"format": "worker-fixture-recipe",
              "sources": [{"path": "diagnostic-input.json",
                           "source": str(assignment.relative_to(REPO)),
                           "sha256": hashlib.sha256(assignment.read_bytes()).hexdigest()}],
              "generator": {"source": str(path.relative_to(REPO)),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}}
    (ROOT / ("diagnostic-" + phase + "-recipe.json")).write_text(json.dumps(recipe, indent=2) + "\n")


if __name__ == "__main__":
    for selected in ("waiting_at_stop", "boarding_bus"):
        write_case(selected)
