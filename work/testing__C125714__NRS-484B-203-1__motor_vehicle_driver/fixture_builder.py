"""Build labeled three-frame software fixtures; never original Native evidence."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import shutil

from PIL import Image

from native_history import CAMERA_DIMENSIONS, capture
from opposing_pass import VARIANTS

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work" / "c125714-2031" / "fixture-builder"
ASSIGNMENT = HERE.name


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n"


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def map_packet():
    return {
        "source_kind": "original_native_map_geometry", "layout": "median_opening",
        "public_highway": True, "encounter_on_undivided_approach": True,
        "opposing_lane_directions": [1, -1],
        "traffic_line_capacity_each_direction": [1, 1],
        "capacity_source": "synthetic diagnostic lane review",
        "paved_boundary_source": "synthetic diagnostic edge",
        "paved_y_bounds_m": [-3.5, 3.5], "ego_half_width_m": 0.6,
        "other_half_width_m": 0.6,
        "native_road_frame": {"source_id": "synthetic diagnostic axis",
                              "origin_xyz_m": [0, 0, 0], "forward_xy": [1, 0]},
        "cross_sections": [{"s_m": s, "source": "native_map",
                            "undivided": True, "paved_y_bounds_m": [-3.5, 3.5]}
                           for s in range(-25, 26, 5)],
        "verified_centers_y_m": {
            "right_half": {"ego": -1.7, "other": 1.7},
            "wrong_side": {"ego": 1.7, "other": -1.7},
            "left_encroachment": {"ego": -0.7, "other": 1.7},
            "right_constrained": {"ego": -1.5, "other": 1.7}},
        "physical_constraint": {"source_kind": "original_native_map_geometry",
                                "source_id": "synthetic diagnostic right-edge feature",
                                "station_range_m": [-4, 4],
                                "lateral_range_m": [-3.5, -2.4]}}


def vertices(station, lateral):
    return [[station + ds, lateral + dy, z]
            for ds in (-.8, .8) for dy in (-.6, .6) for z in (0, 1.5)]


class DiagnosticAdapter:
    def __init__(self, map_sha256, variant):
        self.map_sha256, self.variant, self.index = map_sha256, variant, 0
        self.images = {}
        for name, dimensions in CAMERA_DIMENSIONS.items():
            stream = io.BytesIO()
            Image.new("RGB", dimensions, (10, 20, 30)).save(stream, format="PNG")
            self.images[name] = stream.getvalue()

    def source_attestation(self):
        return {"native_origin": True, "map_sha256": self.map_sha256,
                "source_ref": "explicitly synthetic diagnostic fixture"}

    def tick(self):
        i = self.index
        self.index += 1
        centers = map_packet()["verified_centers_y_m"][self.variant]
        return {"native_frame": 100 + i, "native_elapsed_s": 20 + i/20,
                "ego": {"actor_id": "diagnostic-ego",
                        "vertices_world_xyz_m": vertices(-1+i, centers["ego"]),
                        "velocity_world_xyz_mps": [6, 0, 0]},
                "other": {"actor_id": "diagnostic-other",
                          "vertices_world_xyz_m": vertices(1-i, centers["other"]),
                          "velocity_world_xyz_mps": [-6, 0, 0]},
                "cameras": self.images}


def build(variant):
    case = ASSIGNMENT + "__" + variant
    working = SCRATCH / variant
    if working.exists():
        shutil.rmtree(working)
    working.mkdir(parents=True)
    packet = map_packet()
    reviewed = working / "reviewed-map.json"
    reviewed.write_text(encoded(packet))
    map_sha = digest(reviewed)
    receipt = capture(DiagnosticAdapter(map_sha, variant), reviewed, map_sha,
                      variant, working / "opposing-actor-trace.json",
                      frames=3, diagnostic_fixture=True,
                      media_output=working / "opposing-camera-frames")
    receipt["path"] = "opposing-actor-trace.json"
    receipt["camera_manifest"]["path"] = "opposing-camera-frames/camera-manifest.json"
    original_rows = json.loads((working / "opposing-camera-frames/camera-manifest.json").read_text())
    video_manifest = {"format": "diagnostic-video-join",
                      "rows": [{key: row[key] for key in
                                ("frame", "time_s", "native_frame", "native_elapsed_s")}
                               for row in original_rows],
                      "videos": {name: name + ".mkv" for name in CAMERA_DIMENSIONS}}
    camera_manifest = working / "opposing-camera-frames/camera-manifest.json"
    camera_manifest.write_text(encoded(video_manifest))
    receipt["camera_manifest"]["sha256"] = digest(camera_manifest)
    (working / "opposing-capture-receipt.json").write_text(encoded(receipt))
    (working / "acquisition-provenance.json").write_text(encoded({
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
        "method": "three-frame CPU fixture; no physical or legal acceptance"}))
    frames = []
    mapping = []
    evidence = []
    native = []
    graphs = []
    for i in range(3):
        frame, time_s = 100+i, i/20
        frames.append({"frame": frame, "time_s": time_s,
                       "position": {"x": float(i), "y": 0.0, "z": 0.0},
                       "position_m": [float(i), 0.0, 0.0],
                       "heading_deg": 0.0, "speed_mps": 6.0,
                       "speed_mph": 6.0/.44704, "velocity_mps": [6.0, 0.0, 0.0],
                       "control": {}})
        mapping.append({"video_frame": i, "carla_frame": frame,
                        "native_frame": frame, "time_s": time_s})
        observed = {"frame": frame, "time_s": time_s,
                    "map_context": {"diagnostic_fixture": True}, "participants": []}
        native.append({"frame": frame, "time_s": time_s,
                       "simulation_time": time_s,
                       "adapter_graph": f"graphs/base/{frame:08d}.adapter.json",
                       "observed_evidence": observed})
        evidence.append({"actor_id": 7, "ego": {
            "body_vertices_m": vertices(float(i), 0.0), "heading_deg": 0,
            "position_m": [float(i), 0.0, 0.0], "speed_mps": 6,
            "speed_provenance": "synthetic_native_sample"},
            "original_frame": frame, "recording_time_s": time_s,
            "replay_frame": frame, "replay_simulation_time_s": time_s,
            "original_observations": observed, "world": {"weather": {}}})
        graphs.append({"path": f"capture/native/graphs/base/{frame:08d}.adapter.json",
                       "attributes": {"frame": frame, "time_s": time_s,
                                      "observed_evidence": observed},
                       "nodes": [], "edges": []})
    def lines(rows):
        return "".join(encoded(row) for row in rows)
    files = {"trace.jsonl": lines(frames), "video_frames.jsonl": lines(mapping),
             "capture/evidence.jsonl": lines(evidence),
             "capture/native/frames.jsonl": lines(native),
             "capture/recorder_info.txt": "Frame 1\nCreate 7: vehicle.tesla.model3 (7) at (0, 0, 0)\nsynthetic diagnostic fixture only\n",
             "road.xodr": "<OpenDRIVE><header name=\"synthetic diagnostic\"/></OpenDRIVE>\n"}
    files["capture/manifest.json"] = encoded({"acquisition": "synthetic_fixture",
        "case_id": case, "diagnostic_fixture": True,
        "extraction_confirmed": True, "frames": 3,
        "sources": {key: hashlib.sha256(files[key].encode()).hexdigest()
                    for key in ("road.xodr", "trace.jsonl")}})
    videos = [{"path": name + ".mkv", "frames": 3, "width": width,
               "height": height, "fps": 20, "color": "black"}
              for name, (width, height) in CAMERA_DIMENSIONS.items()]
    spec = {"files": files, "graphs": graphs, "videos": videos}
    destination = HERE / "cases" / variant / "diagnostic-sources"
    destination.mkdir(parents=True, exist_ok=True)
    copied = []
    for source in working.rglob("*"):
        if source.is_file() and source.suffix != ".png":
            relative = source.relative_to(working)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            copied.append(relative.as_posix())
    spec_path = HERE / "cases" / variant / "diagnostic.json"
    spec_path.write_text(json.dumps(spec, sort_keys=True, separators=(",", ":")) + "\n")
    sources = [{"path": relative, "source": str((destination / relative).relative_to(REPO)),
                "sha256": digest(destination / relative)} for relative in sorted(copied)]
    recipe = {"format": "worker-fixture-recipe", "sources": sources,
              "generator": {"source": str(spec_path.relative_to(REPO)),
                            "sha256": digest(spec_path)}}
    (HERE / "cases" / variant / "fixture-recipe.json").write_text(
        json.dumps(recipe, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    SCRATCH.mkdir(parents=True, exist_ok=True)
    for selected in VARIANTS:
        build(selected)
