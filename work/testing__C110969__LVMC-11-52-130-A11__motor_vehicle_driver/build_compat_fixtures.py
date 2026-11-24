"""Build exact synthetic source recipes for current-runtime compatibility.

The 900-frame fixtures prove software plumbing only.  They contain no reviewed
intersection, original traffic necessity, officer direction, or legal finding.
"""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import shutil
import sys
import types

from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
from native_bundle import capture_bundle
from native_map import PREFIX, SUFFIXES

SCAFFOLD = ROOT / "work/testing__C110969__NRS-484B-450-1c__motor_vehicle_driver/cases/inside_stop/diagnostic.json"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class World:
    def __init__(self, road):
        self.road, self.frame = road, 100

    def get_map(self):
        return types.SimpleNamespace(name="C110969 synthetic intersection",
                                     to_opendrive=lambda: self.road)

    def get_settings(self):
        return types.SimpleNamespace(synchronous_mode=True, fixed_delta_seconds=0.05)

    def tick(self):
        self.frame += 1
        return self.frame


class Control:
    def __init__(self, throttle=0.0, brake=0.0):
        self.throttle, self.brake = throttle, brake


class Ego:
    id = 17

    def __init__(self, x):
        self.x, self.controls = x, []

    def get_transform(self):
        return types.SimpleNamespace(x=self.x, y=0.0, heading=180.0)

    def get_velocity(self):
        return types.SimpleNamespace(x=0.0, y=0.0, z=0.0)

    def get_control(self):
        return Control()

    def apply_control(self, control):
        self.controls.append(control)


def build():
    scratch = ROOT / ".runtime-work/c110969-compat-fixture-build"
    scratch.mkdir(parents=True, exist_ok=True)
    scaffold = json.loads(SCAFFOLD.read_text())
    road = scaffold["files"]["road.xodr"].replace("C150530", "C110969 synthetic intersection")
    pixel = scratch / "fixture-pixel.png"
    if not pixel.exists():
        image = io.BytesIO()
        Image.new("RGB", (2, 2), (23, 41, 59)).save(image, format="PNG")
        pixel.write_bytes(image.getvalue())
    plan = json.loads((HERE / "case-plan.json").read_text())
    for case in plan["cases"]:
        case_id = case["case_id"]
        suffix = case_id.removeprefix(HERE.name + "__")
        if case_id != PREFIX + suffix or suffix not in SUFFIXES:
            raise ValueError("Foreign exact case")
        folder = HERE / "cases" / suffix
        source_root = folder / "fixture-sources"
        source_root.mkdir(exist_ok=True)
        run = scratch / suffix
        if run.exists():
            shutil.rmtree(run)
        run.mkdir()
        packet = run / "map-packet.json"
        packet.write_text(encoded({
            "case_ids": sorted(PREFIX + name for name in SUFFIXES),
            "map_name": "C110969 synthetic intersection",
            "opendrive_sha256": hashlib.sha256(road.encode()).hexdigest(),
            "geometry_provenance": "synthetic CPU fixture only",
            "boundary_review_source_sha256": "a" * 64,
            "intersection_boundary_local_m": {"west": -8, "south": -8,
                                               "east": 8, "north": 8},
            "approach": "east", "route_waypoint_ids": [11, 12, 13],
            "local_transform_source_sha256": "b" * 64,
            "vehicle_length_m": 4.5, "vehicle_width_m": 1.8}))
        png = pixel.read_bytes()
        gap_ft = case["requested_front_body_gap_ft"]
        attempt = run / "original-attempt"
        capture_bundle(World(road), Ego(8 + gap_ft * 0.3048 + 2.25), attempt,
                       map_packet_path=packet, case_id=case_id,
                       attempt_id="synthetic-" + suffix,
                       recording_id="synthetic-" + suffix,
                       world_to_local=lambda t: (t.x, t.y, t.heading),
                       read_camera=lambda _name, frame: (frame, png),
                       read_context=lambda frame: {"world_frame": frame,
                                                   "participants": [], "directions": {},
                                                   "police_direction_judgment": "unresolved",
                                                   "necessity_judgment": "unresolved"})
        pose = [json.loads(line) for line in (attempt / "pose.jsonl").read_text().splitlines()]
        fixture_text = {}
        for path in attempt.rglob("*"):
            if path.is_file() and path.suffix != ".png":
                rel = "original-attempt/" + str(path.relative_to(attempt))
                target = source_root / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(path.read_bytes())
                fixture_text[rel] = target
        trace = [{"frame": p["world_frame"], "time_s": p["time_s"],
                  "position": {"x": p["x_m"], "y": p["y_m"], "z": 0.0},
                  "position_m": [p["x_m"], p["y_m"], 0.0],
                  "heading_deg": p["heading_deg"], "speed_mps": p["speed_mps"],
                  "speed_mph": p["speed_mps"] / 0.44704,
                  "velocity_mps": [0.0, 0.0, 0.0], "control": {}}
                 for p in pose]
        video_map = [{"video_frame": i, "carla_frame": p["world_frame"],
                      "time_s": p["time_s"]} for i, p in enumerate(pose)]
        events = []
        frames = []
        graphs = []
        for p in pose:
            number = p["world_frame"]
            x = p["x_m"]
            body = [[x + dx, y, z] for dx in (-2.25, 2.25)
                    for y in (-0.9, 0.9) for z in (-0.5, 0.5)]
            observation = {"frame": number, "time_s": p["time_s"],
                           "map_context": {"junction_id": 9}, "participants": []}
            events.append({"actor_id": 17, "original_frame": number,
                           "replay_frame": number,
                           "recording_time_s": p["time_s"],
                           "replay_simulation_time_s": p["time_s"],
                           "ego": {"position_m": [x, p["y_m"], 0.0],
                                   "heading_deg": p["heading_deg"],
                                   "speed_mps": p["speed_mps"],
                                   "speed_provenance": "synthetic_native_sample",
                                   "body_vertices_m": body},
                           "world": {"weather": {}},
                           "original_observations": observation})
            graph_path = f"graphs/base/{number:08d}.adapter.json"
            frames.append({"frame": number, "simulation_time": p["time_s"],
                           "adapter_graph": graph_path})
            graphs.append({"path": "capture/native/" + graph_path,
                           "attributes": {"frame": number,
                                          "observed_evidence": observation,
                                          "time_s": p["time_s"]},
                           "nodes": [], "edges": []})
        generated = {
            "acquisition-provenance.json": encoded({
                "diagnostic_fixture": True, "provenance_kind": "synthetic_fixture",
                "source_scope": "CPU software compatibility only"}),
            "fixture-provenance.json": encoded({
                "diagnostic_fixture": True,
                "scope": "CPU diagnostic only; camera receipt metadata has no original PNG pixels"}),
            "road.xodr": road,
            "trace.jsonl": "".join(encoded(row) for row in trace),
            "video_frames.jsonl": "".join(encoded(row) for row in video_map),
            "capture/evidence.jsonl": "".join(encoded(row) for row in events),
            "capture/native/frames.jsonl": "".join(encoded(row) for row in frames),
            "capture/recorder_info.txt": "Create 17: vehicle.diagnostic.ego (0) at (0, 0, 0)\n",
        }
        generated["capture/manifest.json"] = encoded({
            "acquisition": "diagnostic_fixture", "case_id": case_id,
            "frames": 900, "extraction_confirmed": True,
            "sources": {"road.xodr": hashlib.sha256(road.encode()).hexdigest(),
                        "trace.jsonl": hashlib.sha256(generated["trace.jsonl"].encode()).hexdigest()},
            "required_observations": [], "status": "draft"})
        videos = [{"path": name + ".mkv", "frames": 900,
                   "width": 1920 if name == "overview" else 1280,
                   "height": 1080 if name == "overview" else 720,
                   "fps": 20, "color": "black"} for name in CAMERAS]
        spec_path = folder / "diagnostic.json"
        spec_path.write_text(encoded({"files": generated, "graphs": graphs,
                                     "videos": videos}))
        sources = [{"path": rel, "source": str(path.relative_to(ROOT)),
                    "sha256": sha(path)} for rel, path in sorted(fixture_text.items())]
        recipe_path = folder / "fixture-recipe.json"
        recipe_path.write_text(encoded({"format": "worker-fixture-recipe",
                                        "generator": {"source": str(spec_path.relative_to(ROOT)),
                                                      "sha256": sha(spec_path)},
                                        "sources": sources}))
        note = {"case_id": case_id, "diagnostic_fixture": True,
                "physical_review": False, "legal_conclusion": None,
                "source_scaffold_sha256": sha(SCAFFOLD),
                "scope": "900-frame source-shaped software fixture only"}
        (folder / "diagnostic-source-note.json").write_text(encoded(note))
        print(suffix, "spec_bytes", spec_path.stat().st_size,
              "recipe_bytes", recipe_path.stat().st_size)
        if max(spec_path.stat().st_size, recipe_path.stat().st_size) > 2 * 1024 * 1024:
            raise ValueError("Diagnostic file exceeds checkpoint size limit")
        shutil.rmtree(run)


if __name__ == "__main__":
    build()
