"""Build explicit, hash-bound synthetic public compatibility sources for both cases."""

import hashlib
import json
import tempfile
from pathlib import Path

from test_saved_due_care import ROOT, fixture, write_rows

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent.name
SOURCE_ASSIGNMENT = "inputs/" + ASSIGNMENT + "/assignment.json"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def text_rows(rows):
    return "".join(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n"
                   for row in rows)


def main():
    road = (HERE / "diagnostic-road.xodr").read_text()
    scratch = ROOT / ".runtime-work"
    scratch.mkdir(exist_ok=True)
    receipts = []
    for condition in ("a", "b"):
        with tempfile.TemporaryDirectory(dir=scratch, prefix="c230266-fixture-source-") as temporary:
            folder = Path(temporary)
            source_rows, mapping = fixture(folder)
            if condition == "b":
                x = -35.0
                for row in source_rows:
                    x += 6 / 20
                    row["ego_x_m"] = x
                    row["ego_speed_mps"] = 6.0
                    row["requested_control"] = {"brake": 0.0}
                write_rows(folder / "pedestrian-due-care-trace.jsonl", source_rows)
            (folder / "contact_events.jsonl").write_text("")
            native_trace = [{"frame": row["native_frame"], "time_s": row["time_s"],
                             "position": {"x": row["ego_x_m"], "y": row["ego_y_m"], "z": 0.5},
                             "position_m": [row["ego_x_m"], row["ego_y_m"], 0.5],
                             "heading_deg": 0, "speed_mps": row["ego_speed_mps"],
                             "speed_mph": row["ego_speed_mps"] * 2.2369362921,
                             "velocity_mps": [row["ego_speed_mps"], 0, 0],
                             "control": {"throttle": 0.22 if row["requested_control"]["brake"] == 0 else 0,
                                         "brake": row["requested_control"]["brake"],
                                         "hand_brake": False}}
                            for row in source_rows]
            evidence = []
            native_frames = []
            graphs = []
            for row in source_rows:
                frame = row["native_frame"]
                x, y = row["ego_x_m"], row["ego_y_m"]
                evidence.append({"original_frame": frame, "recording_time_s": row["time_s"],
                                 "replay_frame": frame, "replay_simulation_time_s": row["time_s"],
                                 "actor_id": 1,
                                 "ego": {"position_m": [x, y, 0.5], "heading_deg": 0,
                                         "speed_mps": row["ego_speed_mps"],
                                         "body_vertices_m": [[x - 2, y - 1, 0.5],
                                                             [x - 2, y + 1, 0.5],
                                                             [x + 2, y + 1, 0.5],
                                                             [x + 2, y - 1, 0.5]],
                                         "speed_provenance": "synthetic_native_sample",
                                         "synthetic_diagnostic": True},
                                 "world": {"weather": {"cloudiness": 0, "precipitation": 0,
                                                       "wetness": 0, "fog_density": 0},
                                           "road_projection": {"road_id": 1, "section_id": 0,
                                                               "lane_id": -1, "s_m": 70 + x}}})
                path = "graphs/base/" + f"{frame:08d}" + ".adapter.json"
                native_frames.append({"frame": frame, "simulation_time": row["time_s"],
                                      "time_s": row["time_s"], "base": path,
                                      "adapter_graph": path, "synthetic_diagnostic": True})
                graphs.append({"path": "capture/native/" + path,
                               "attributes": {"frame": frame}, "nodes": [], "edges": []})
            files = {name: (folder / name).read_text()
                     for name in ("road_survey.json", "pedestrian-due-care-trace.jsonl",
                                  "video_frames.jsonl", "contact_events.jsonl")}
            files.update({"trace.jsonl": text_rows(native_trace),
                          "capture/evidence.jsonl": text_rows(evidence),
                          "capture/native/frames.jsonl": text_rows(native_frames),
                          "capture/recorder_info.txt": "Create 1: vehicle.tesla.model3\nCreate 2: walker.pedestrian.0001\n",
                          "road.xodr": road})
            files["capture/manifest.json"] = json.dumps({
                "extraction_confirmed": True, "frames": 600,
                "synthetic_diagnostic": True,
                "sources": {"road.xodr": sha_bytes(road.encode()),
                            "trace.jsonl": sha_bytes(files["trace.jsonl"].encode())}},
                separators=(",", ":")) + "\n"
            videos = [{"path": name + ".mkv", "frames": 600,
                       "width": 1920 if name == "overview" else 1280,
                       "height": 1080 if name == "overview" else 720,
                       "fps": 20, "color": "blue" if condition == "a" else "green"}
                      for name in CAMERAS]
            specification = {"files": files, "graphs": graphs, "videos": videos}
            spec_path = HERE / ("selected-" + condition + "-fixture.json")
            spec_path.write_text(json.dumps(specification, separators=(",", ":")) + "\n")
            recipe = {"format": "worker-fixture-recipe",
                      "sources": [{"path": "diagnostic-input-assignment.json",
                                   "source": SOURCE_ASSIGNMENT,
                                   "sha256": sha_bytes((ROOT / SOURCE_ASSIGNMENT).read_bytes())}],
                      "generator": {"source": "work/" + ASSIGNMENT + "/native/" + spec_path.name,
                                    "sha256": sha_bytes(spec_path.read_bytes())}}
            recipe_path = HERE / ("selected-" + condition + "-fixture-recipe.json")
            recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
            receipts.append({"condition": condition, "spec_sha256": sha_bytes(spec_path.read_bytes()),
                             "spec_bytes": spec_path.stat().st_size,
                             "recipe_sha256": sha_bytes(recipe_path.read_bytes())})
    print(json.dumps({"fixtures": receipts}))


if __name__ == "__main__":
    main()
