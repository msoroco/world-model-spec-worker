"""Build source-shaped crossing fixtures from an existing 600-frame graph shape.

These textual sources are synthetic and never establish officiality or geometry.
"""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
BASE = ROOT / "work" / "training__C109166__NRS-484B-287-1d__pedestrian" / "diagnostic-probe_01.json"
CASES = {"marked_crosswalk": 40.0, "unmarked_midblock": 60.0}
CAMERAS = (("overview", 1920, 1080), ("approach", 1280, 720),
           ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return sha_bytes(Path(path).read_bytes())


def rows(value):
    return [json.loads(line) for line in value.splitlines() if line]


def lines(values):
    return "".join(json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n"
                   for value in values)


def body(x, y):
    return [[x + dx, y + dy] for dx, dy in ((-.2, -.2), (.2, -.2), (.2, .2), (-.2, .2))]


def body3(x, y):
    return [[x + dx, y + dy, z] for dx, dy in ((-.2, -.2), (.2, -.2),
                                                (.2, .2), (-.2, .2)) for z in (0, 1.8)]


def build():
    original = json.loads(BASE.read_text())
    for case, x in CASES.items():
        spec = {"files": dict(original["files"]), "graphs": original["graphs"],
                "videos": original["videos"]}
        for old in list(spec["files"]):
            if old.startswith("authority/") or old in (
                    "authority-receipt.json", "pedestrian-original.jsonl",
                    "device-original.jsonl", "camera-sources.jsonl",
                    "exception-applicability-source.json"):
                spec["files"].pop(old)
        trace = rows(spec["files"]["trace.jsonl"])
        evidence = rows(spec["files"]["capture/evidence.jsonl"])
        native_frames = rows(spec["files"]["capture/native/frames.jsonl"])
        mapping = rows(spec["files"]["video_frames.jsonl"])
        if not len(trace) == len(evidence) == len(native_frames) == len(mapping) == len(spec["graphs"]) == 600:
            raise ValueError("Existing source shape lacks 600 complete frames")
        people, controls, camera_rows = [], [], []
        pixel_hashes = {name: sha_bytes(bytes(width * height * 3))
                        for name, width, height in CAMERAS}
        prior_y = None
        for index in range(600):
            frame = 100 + index
            time = index / 20
            progress = min(1.0, max(0.0, (index - 200) / 200))
            y = -10 + progress * 20
            entry = prior_y is not None and prior_y < -4 <= y
            prior_y = y
            moving = 200 <= index < 400
            trace[index].update(frame=frame, time_s=time,
                                position={"x": x, "y": y, "z": .5},
                                position_m=[x, y, .5], heading_deg=90,
                                speed_mps=2.0 if moving else 0.0,
                                speed_mph=4.4738725842 if moving else 0.0,
                                velocity_mps=[0, 2.0 if moving else 0, 0])
            evidence[index].update(original_frame=frame, replay_frame=frame,
                                   recording_time_s=time, replay_simulation_time_s=time)
            evidence[index]["ego"].update(position_m=[x, y, .5], heading_deg=90,
                                           speed_mps=2.0 if moving else 0.0,
                                           body_vertices_m=body3(x, y))
            graph = spec["graphs"][index]
            graph["attributes"].update(frame=frame, simulation_time_s=time,
                                       source="C109166 synthetic vertical crossing source shape")
            graph["nodes"][0]["attributes"].update(vertex=[x, y, .5], forward=[0, 1, 0],
                                                      threedbbox=body3(x, y))
            native_frames[index].update(frame=frame, time_s=time, simulation_time=time,
                                        adapter_graph=f"graphs/base/{frame:08d}.adapter.json")
            graph["path"] = f"capture/native/graphs/base/{frame:08d}.adapter.json"
            mapping[index].update(video_frame=index, native_frame=frame, carla_frame=frame,
                                  time_s=time, source_rgb_sha256=pixel_hashes)
            people.append({"frame": frame, "native_frame": frame, "time_s": time,
                           "walker_actor_id": 107, "center_xy_m": [x, y],
                           "footprint_xy_m": body(x, y), "roadway_entry_observed": entry})
            controls.append({"native_frame": frame, "time_s": time,
                             "controls": [{"native_actor_id": ident, "opendrive_id": str(ident),
                                           "native_state": "Green", "frozen": False,
                                           "operating_observed": True} for ident in (201, 202)]})
            for name, width, height in CAMERAS:
                camera_rows.append({"camera": name, "video_frame": index,
                                    "native_frame": frame, "time_s": time,
                                    "width": width, "height": height,
                                    "rgb_sha256": pixel_hashes[name]})
        for name, value in (("trace.jsonl", trace), ("capture/evidence.jsonl", evidence),
                            ("capture/native/frames.jsonl", native_frames),
                            ("video_frames.jsonl", mapping),
                            ("pedestrian-original.jsonl", people),
                            ("controls-original.jsonl", controls),
                            ("camera-sources.jsonl", camera_rows)):
            spec["files"][name] = lines(value)
        spec["files"]["capture/manifest.json"] = json.dumps({
            "extraction_confirmed": True, "frames": 600,
            "required_observations": [], "synthetic_diagnostic": True,
            "sources": {"trace.jsonl": sha_bytes(spec["files"]["trace.jsonl"].encode()),
                        "road.xodr": sha_bytes(spec["files"]["road.xodr"].encode())}},
            separators=(",", ":")) + "\n"
        survey = {"format": "c109166-287-1c-native-survey-v1",
                  "review_status": "synthetic_diagnostic",
                  "independent_reviewer": None,
                  "junction_ids": [101, 102],
                  "crossing_locations": CASES,
                  "controls": [{"native_actor_id": 201, "opendrive_id": "201"},
                               {"native_actor_id": 202, "opendrive_id": "202"}],
                  "marked_crosswalk": {"polygon_xy_m": [[38, -5], [42, -5],
                                                        [42, 5], [38, 5]]},
                  "roadway_boundary": {"entry_y_m": -4.0}}
        spec["files"]["native-survey.json"] = json.dumps(survey, separators=(",", ":")) + "\n"
        media = {}
        for name in ("map.txt", "control-1.txt", "control-2.txt", "marking.txt"):
            source = "synthetic diagnostic " + name + "\n"
            spec["files"]["native-survey-media/" + name] = source
            media[name] = sha_bytes(source.encode())
        spec["files"]["native-survey-provenance.json"] = json.dumps({
            "copied_sha256": sha_bytes(spec["files"]["native-survey.json"].encode()),
            "copied_media": media}, separators=(",", ":")) + "\n"
        spec["files"]["acquisition-provenance.json"] = json.dumps({
            "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True},
            separators=(",", ":")) + "\n"
        spec["files"]["native-capture-report.json"] = json.dumps({
            "case_id": HERE.name + "__" + case, "frames": 600,
            "expected_frames": 600, "error": None, "restoration": {"restored": True},
            "survey_sha256": sha_bytes(spec["files"]["native-survey.json"].encode()),
            "synthetic_diagnostic": True}, separators=(",", ":")) + "\n"
        spec["files"]["exception-applicability-source.json"] = json.dumps({
            "format": "c109166-287-1c-exception-context-v1", "statute": "NRS 484B.290",
            "review_status": "pending_independent_review", "applicability": "undetermined",
            "synthetic_diagnostic": True}, separators=(",", ":")) + "\n"
        path = HERE / ("diagnostic-" + case + ".json")
        path.write_text(json.dumps(spec, separators=(",", ":"), allow_nan=False) + "\n")
        if path.stat().st_size > 2 * 1024 * 1024:
            path.unlink()
            raise ValueError("Diagnostic textual specification exceeds return cap")
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "diagnostic-input.json",
                               "source": str(path.relative_to(ROOT)), "sha256": sha(path)}],
                  "generator": {"source": str(path.relative_to(ROOT)), "sha256": sha(path)}}
        recipe_path = HERE / ("diagnostic-" + case + "-recipe.json")
        recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
        print(json.dumps({"case": case, "spec_bytes": path.stat().st_size,
                          "recipe_sha256": sha(recipe_path)}))


if __name__ == "__main__":
    build()
