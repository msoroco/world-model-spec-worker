"""Build bounded synthetic source text for exact CPU compatibility checks."""
import hashlib
import json
from pathlib import Path

from road_scene import surface_gap


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def body(x, y):
    return [[x, y, 0], [x + 1, y, 0], [x + 1, y + 1, 0], [x, y + 1, 0]]


def write_case(label):
    fixture = json.loads((REPO / "runtime/fixtures/example.json").read_text())
    files = fixture["files"]
    trace = [json.loads(line) for line in files["trace.jsonl"].splitlines() if line.strip()]
    if len(trace) != 9:
        raise ValueError("pinned diagnostic frame count changed")
    files["map.xodr"] = "<OpenDRIVE>diagnostic road text</OpenDRIVE>\n"
    site = {"format": "worker-near-road-site", "cell_id": "C416422",
            "layout": "single_lane_per_direction", "sidewalk_present": True,
            "map_source": {"path": "map.xodr", "sha256": digest(files["map.xodr"])},
            "road": {"lateral_bounds_m": [-6, 2],
                     "classification_source": "diagnostic Native-shaped driving-lane waypoint",
                     "edge_review_source": "diagnostic Native-shaped lane width"},
            "sidewalk": {"lateral_bounds_m": [2.5, 4.5],
                         "lane_source": "diagnostic Native-shaped Sidewalk lane",
                         "adjacency_source": "diagnostic Native-shaped adjacent lane"},
            "ego_start_xy_m": [-30, 0], "ego_end_xy_m": [20, 0],
            "pedestrian_start_xy_m": [0, 3], "pedestrian_end_xy_m": [1, 3],
            "diagnostic_only": True}
    files["road-site.json"] = json.dumps(site, sort_keys=True) + "\n"
    history = []
    for i, frame in enumerate(trace):
        ego, pedestrian = body(-12 + i, 0), body(0, 3)
        event = ({"source": "original_driver_input", "observed": True,
                  "kind": "diagnostic_scripted_input"} if i >= 2 else None)
        brake = int(i >= (2 if label == "prompt_brake" else 5))
        history.append({"frame": frame["frame"], "time_s": frame["time_s"],
                        "ego_body_vertices_m": ego, "pedestrian_body_vertices_m": pedestrian,
                        "ego_speed_mps": 4, "ego_brake": brake,
                        "pedestrian_class_source": "diagnostic/actor-blueprint",
                        "driver_control_source": "diagnostic/scripted-driver-input",
                        "pedestrian_class": "pedestrian", "ego_class": "motor_vehicle",
                        "driver_observation_event": event,
                        "surface_gap_m": surface_gap(ego, pedestrian),
                        "contact_event": False})
    files["encounter-history.jsonl"] = "".join(json.dumps(row, sort_keys=True) + "\n" for row in history)
    names = ("map.xodr", "road-site.json", "encounter-history.jsonl", "video_frames.jsonl")
    files["acquisition.json"] = json.dumps({name: {"kind": "original_native", "sha256": digest(files[name])}
                                             for name in names}, sort_keys=True) + "\n"
    files["fixture-provenance.json"] = json.dumps({"scope": "CPU synthetic source text only",
        "case_specific_sources": list(names), "physical_acceptance_claimed": False,
        "human_observation_claimed": False}) + "\n"
    path = ROOT / ("diagnostic-" + label + ".json")
    path.write_text(json.dumps(fixture, ensure_ascii=False, separators=(",", ":")) + "\n")
    assignment = ROOT / "assignment.json"
    recipe = {"format": "worker-fixture-recipe",
              "sources": [{"path": "diagnostic-input.json",
                           "source": str(assignment.relative_to(REPO)),
                           "sha256": hashlib.sha256(assignment.read_bytes()).hexdigest()}],
              "generator": {"source": str(path.relative_to(REPO)),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}}
    (ROOT / ("diagnostic-" + label + "-recipe.json")).write_text(json.dumps(recipe, indent=2) + "\n")


if __name__ == "__main__":
    for label in ("prompt_brake", "deferred_brake"):
        write_case(label)
