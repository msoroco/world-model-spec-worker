"""Generate source-hashed 600-frame public diagnostic fixtures for all cases."""

import hashlib
import json
import tempfile
from pathlib import Path

from test_saved_hydrant import ROOT, fixture

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
ASSIGNMENT = WORK.name
SOURCE_ASSIGNMENT = "inputs/" + ASSIGNMENT + "/assignment.json"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha_bytes(value):
    return hashlib.sha256(value).hexdigest()


def text_rows(rows):
    return "".join(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n"
                   for row in rows)


def main():
    road = (HERE / "diagnostic-road.xodr").read_text()
    plan = json.loads((WORK / "case-plan.json").read_text())
    receipts = []
    for case in plan["cases"]:
        suffix = case["case_id"].split("__")[-1]
        construction = json.loads((HERE / ("selected-" + suffix + "-construction.json")).read_text())
        config = json.loads(next(row["content"] for row in construction["files"]
                                 if row["path"] == "config.json"))
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work",
                                         prefix="c200568-fixture-source-") as temporary:
            folder = Path(temporary)
            trace_rows = []
            survey, source_rows, mapping = fixture(folder, config)
            evidence, native_frames, graphs = [], [], []
            for row in source_rows:
                frame, native = row["frame"], row["native_frame"]
                x, y, z = row["ego_xyz_m"]
                extent_x, extent_y, _ = row["ego_extent_xyz_m"]
                body = [[x - extent_x, y - extent_y, z],
                        [x - extent_x, y + extent_y, z],
                        [x + extent_x, y + extent_y, z],
                        [x + extent_x, y - extent_y, z]]
                trace_rows.append({"frame": native, "time_s": row["time_s"],
                    "position": {"x": x, "y": y, "z": z},
                    "position_m": [x, y, z], "body_vertices_m": body,
                    "heading_deg": 0, "speed_mps": 0,
                    "speed_mph": 0, "velocity_mps": [0, 0, 0],
                    "control": {"throttle": 0, "brake": 1, "hand_brake": True}})
                evidence.append({"original_frame": native,
                    "recording_time_s": row["time_s"], "replay_frame": native,
                    "replay_simulation_time_s": row["time_s"], "actor_id": 1,
                    "ego": {"position_m": [x, y, z], "heading_deg": 0,
                            "speed_mps": 0, "body_vertices_m": body,
                            "speed_provenance": "synthetic_native_sample",
                            "synthetic_diagnostic": True},
                    "world": {"weather": {"cloudiness": 0, "precipitation": 0,
                                           "wetness": 0, "fog_density": 0},
                              "road_projection": {"road_id": 1, "section_id": 0,
                                                  "lane_id": -1, "s_m": 70 + x}}})
                path = "graphs/base/" + f"{native:08d}" + ".adapter.json"
                native_frames.append({"frame": native, "simulation_time": row["time_s"],
                                      "time_s": row["time_s"], "base": path,
                                      "adapter_graph": path, "synthetic_diagnostic": True})
                graphs.append({"path": "capture/native/" + path,
                               "attributes": {"frame": native}, "nodes": [], "edges": []})
            files = {name: (folder / name).read_text() for name in
                     ("hydrant_survey.json", "hydrant-trace.jsonl", "video_frames.jsonl")}
            files.update({"trace.jsonl": text_rows(trace_rows),
                          "capture/evidence.jsonl": text_rows(evidence),
                          "capture/native/frames.jsonl": text_rows(native_frames),
                          "capture/recorder_info.txt":
                              "Create 1: vehicle.tesla.model3\nCreate 2: static.prop.firehydrant\n",
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
                       "fps": 20, "color": "blue" if suffix.endswith("1") else "green"}
                      for name in CAMERAS]
            specification = {"files": files, "graphs": graphs, "videos": videos}
            spec_path = HERE / ("selected-" + suffix + "-fixture.json")
            spec_path.write_text(json.dumps(specification, separators=(",", ":")) + "\n")
            recipe = {"format": "worker-fixture-recipe",
                      "sources": [{"path": "diagnostic-input-assignment.json",
                                   "source": SOURCE_ASSIGNMENT,
                                   "sha256": sha_bytes((ROOT / SOURCE_ASSIGNMENT).read_bytes())}],
                      "generator": {"source": "work/" + ASSIGNMENT + "/native/" +
                                    spec_path.name,
                                    "sha256": sha_bytes(spec_path.read_bytes())}}
            recipe_path = HERE / ("selected-" + suffix + "-fixture-recipe.json")
            recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
            receipts.append({"case": suffix, "spec_sha256": sha_bytes(spec_path.read_bytes()),
                             "spec_bytes": spec_path.stat().st_size,
                             "recipe_sha256": sha_bytes(recipe_path.read_bytes())})
    print(json.dumps({"fixtures": receipts}))


if __name__ == "__main__":
    main()
