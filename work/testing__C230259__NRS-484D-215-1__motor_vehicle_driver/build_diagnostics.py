"""Build explicit five-frame software fixtures; no physical acceptance is inferred."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

from test_beam_publication import _finish_fixture

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SCRATCH = REPO / ".runtime-work" / "c230259-diagnostic-build"
PLAN = json.loads((ROOT / "case-plan.json").read_text())
BASE = REPO / "work/testing__C110454__NRS-484D-165-4__motor_vehicle_driver/diagnostic-high_beam.json"
VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def sha_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(value) -> str:
    return json.dumps(value, sort_keys=True) + "\n"


def rows(value) -> str:
    return "".join(canonical(row) for row in value)


def media_hashes(specs):
    hashes = {}
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=SCRATCH, prefix="media-") as temporary:
        for item in specs:
            path = Path(temporary) / item["path"]
            subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                            "-f", "lavfi", "-i", f"color=c={item['color']}:s={item['width']}x{item['height']}:r={item['fps']}",
                            "-frames:v", str(item["frames"]), "-an", "-c:v", "ffv1", "-threads", "1",
                            "-fflags", "+bitexact", "-flags:v", "+bitexact", str(path)], check=True, timeout=120)
            hashes[item["path"]] = sha_bytes(path.read_bytes())
    return hashes


def build(case, base, movies):
    suffix = case["case_id"].split("__")[-1]
    SCRATCH.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=SCRATCH, prefix="sources-") as temporary:
        folder = Path(temporary)
        _finish_fixture(folder)
        files = {}
        for name in ("actor-state.jsonl", "camera-frame-map.jsonl", "roi-frames.jsonl",
                     "site-packet.json", "trace.jsonl", "video_frames.jsonl"):
            files[name] = (folder / name).read_text()
    states = [json.loads(line) for line in files["actor-state.jsonl"].splitlines()][:5]
    maps = [json.loads(line) for line in files["camera-frame-map.jsonl"].splitlines()][:5]
    rois = [json.loads(line) for line in files["roi-frames.jsonl"].splitlines()][:5]
    trace = [json.loads(line) for line in files["trace.jsonl"].splitlines()][:5]
    video_frames = [json.loads(line) for line in files["video_frames.jsonl"].splitlines()][:5]
    gap_ft = case["requested_start_body_gap_ft"]
    bits = {"high": 4, "low": 2, "off": 0}[case["requested_beam"]]
    for index, state in enumerate(states):
        frame, time = index, index / 20
        ego_x = .1 * index
        center = gap_ft * .3048 + 4 - .1 * index
        state["frame"], state["time_s"] = frame, time
        state["actors"]["ego"]["center_m"] = [ego_x, 0, 0]
        state["actors"]["ego"]["driver_eye_m"] = [ego_x, 0, 1.4]
        state["actors"]["ego"]["lamp_command_bits"] = bits
        state["actors"]["ego"]["lamp_state_bits"] = bits
        state["actors"]["oncoming"]["center_m"] = [center, 0, 0]
        state["actors"]["oncoming"]["driver_eye_m"] = [center, 0, 1.4]
        maps[index] = {"frame": frame, **{view + "_source_frame": frame for view in VIEWS}}
        rois[index]["frame"] = frame
        rois[index]["diagnostic_fixture"] = True
        if case["branch"] == "general":
            rois[index]["regions"].pop("oncoming_eye", None)
        trace[index] = {"frame": frame, "time_s": time, "position_m": [ego_x, 0, 0],
                        "position": {"x": ego_x, "y": 0, "z": 0},
                        "heading_deg": 0, "speed_mps": 2,
                        "speed_mph": 2 / .44704, "velocity_mps": [2, 0, 0],
                        "control": {}}
        video_frames[index] = {"video_frame": index, "carla_frame": frame,
                               "native_frame": frame, "time_s": time}
    files.update({"actor-state.jsonl": rows(states), "camera-frame-map.jsonl": rows(maps),
                  "roi-frames.jsonl": rows(rois), "trace.jsonl": rows(trace),
                  "video_frames.jsonl": rows(video_frames)})
    site = json.loads(files["site-packet.json"])
    site.update({"case_id": case["case_id"], "requested_beam": case["requested_beam"],
                 "requested_contour": case["requested_contour"], "requested_load": case["requested_load"],
                 "requested_start_body_gap_ft": case["requested_start_body_gap_ft"],
                 "diagnostic_fixture": True,
                 "source_refs": [{"path": "synthetic-diagnostic-site", "sha256": "a" * 64}]})
    files["site-packet.json"] = canonical(site)
    files["acquisition-provenance.json"] = canonical({"diagnostic_fixture": True,
        "provenance_kind": "synthetic_fixture", "scope": "software compatibility only"})
    source_names = ("actor-state.jsonl", "camera-frame-map.jsonl", "site-packet.json")
    pixel_names = ("roi-frames.jsonl", "camera-frame-map.jsonl")
    receipt = {"format": "beam-road-native-source-v1", "case_id": case["case_id"],
               "frame_count": 5, "diagnostic_fixture": True,
               "source_hashes": {name: sha_bytes(files[name].encode()) for name in source_names},
               "pixel_source_hashes": {name: sha_bytes(files[name].encode()) for name in pixel_names} |
                  {view + ".mkv": movies[view + ".mkv"] for view in ("approach", "driver_reference")},
               "camera_movies": {view: {"path": view + ".mkv", "sha256": movies[view + ".mkv"],
                                        "source_frame_count": 5} for view in VIEWS},
               "physical_acceptance_claimed": False}
    files["native-source-receipt.json"] = canonical(receipt)
    files["road.xodr"] = base["files"]["road.xodr"]
    capture = json.loads(base["files"]["capture/manifest.json"])
    capture["case_id"] = case["case_id"]
    capture["sources"] = {"road.xodr": sha_bytes(files["road.xodr"].encode()),
                          "trace.jsonl": sha_bytes(files["trace.jsonl"].encode())}
    files["capture/manifest.json"] = canonical(capture)
    files["capture/native/frames.jsonl"] = base["files"]["capture/native/frames.jsonl"]
    files["capture/recorder_info.txt"] = "Create 1: vehicle.tesla.model3 (road beam diagnostic) at (0.0, 0.0, 0)\n"
    observations = []
    evidence = []
    graphs = []
    for index, state in enumerate(states):
        participants = []
        for role, actor in state["actors"].items():
            cx, cy, cz = actor["center_m"]
            length, width, height = ((.3, .3, 1.8) if role == "person" else (2, 1, 2))
            vertices = [[cx + sx * length, cy + sy * width, cz + z * height]
                        for sx, sy, z in ((-1, -1, 0), (-1, -1, 1), (1, -1, 0), (1, -1, 1),
                                          (1, 1, 0), (1, 1, 1), (-1, 1, 0), (-1, 1, 1))]
            speed = 2 if role in ("ego", "oncoming") else 0
            participants.append({"actor_id": actor["id"], "role": role,
                                 "blueprint": "walker.pedestrian.0001" if role == "person" else "vehicle.tesla.model3",
                                 "body_vertices_m": vertices,
                                 "heading_deg": 180 if role == "oncoming" else 0,
                                 "position_m": actor["center_m"],
                                 "velocity_mps": [-2, 0, 0] if role == "oncoming" else [speed, 0, 0],
                                 "speed_mps": speed})
        obs = {"frame": index, "time_s": index / 20,
               "map_context": {"declared_public_way_road_ids": []},
               "participants": participants}
        observations.append(obs)
        ego = state["actors"]["ego"]
        evidence.append({"actor_id": ego["id"], "ego": {
            "body_vertices_m": [[ego["center_m"][0] + x, y, z]
                                for x, y, z in ((-2, -1, 0), (-2, -1, 2),
                                                (2, -1, 0), (2, -1, 2),
                                                (2, 1, 0), (2, 1, 2),
                                                (-2, 1, 0), (-2, 1, 2))],
            "heading_deg": 0, "position_m": ego["center_m"], "speed_mps": ego["speed_mps"],
            "speed_provenance": "synthetic_native_sample"},
            "original_frame": index, "original_observations": obs,
            "recording_time_s": index / 20, "replay_frame": index,
            "replay_simulation_time_s": index / 20, "world": {"weather": {}}})
        graphs.append({"path": f"capture/native/graphs/base/{index:08d}.adapter.json",
                       "nodes": [], "edges": [],
                       "attributes": {"frame": index, "time_s": index / 20,
                                      "observed_evidence": obs}})
    files["capture/evidence.jsonl"] = rows(evidence)
    files["acquisition.json"] = canonical({name: {"kind": "diagnostic_fixture",
        "sha256": sha_bytes(value.encode())} for name, value in files.items()
        if name in ("actor-state.jsonl", "camera-frame-map.jsonl", "site-packet.json",
                    "trace.jsonl", "video_frames.jsonl", "roi-frames.jsonl")})
    specification = {"files": files, "graphs": graphs,
                     "videos": [{"path": view + ".mkv", "frames": 5,
                                 "width": 1920 if view == "overview" else 1280,
                                 "height": 1080 if view == "overview" else 720,
                                 "fps": 20, "color": "black"} for view in VIEWS]}
    target = ROOT / "cases" / suffix / "diagnostic.json"
    target.write_text(json.dumps(specification, sort_keys=True) + "\n")
    recipe = {"format": "worker-fixture-recipe",
              "generator": {"source": target.relative_to(REPO).as_posix(),
                            "sha256": sha_bytes(target.read_bytes())},
              "sources": [{"path": "diagnostic-note.txt", "source":
                           (ROOT / "diagnostic-note.txt").relative_to(REPO).as_posix(),
                           "sha256": sha_bytes((ROOT / "diagnostic-note.txt").read_bytes())}]}
    (ROOT / "cases" / suffix / "fixture-recipe.json").write_text(json.dumps(recipe, indent=2) + "\n")


def main():
    (ROOT / "diagnostic-note.txt").write_text(
        "Synthetic five-frame software fixture; no Native physical or legal acceptance.\n")
    base = json.loads(BASE.read_text())
    videos = [{"path": view + ".mkv", "frames": 5,
               "width": 1920 if view == "overview" else 1280,
               "height": 1080 if view == "overview" else 720,
               "fps": 20, "color": "black"} for view in VIEWS]
    hashes = media_hashes(videos)
    for case in PLAN["cases"]:
        build(case, base, hashes)


if __name__ == "__main__":
    main()
