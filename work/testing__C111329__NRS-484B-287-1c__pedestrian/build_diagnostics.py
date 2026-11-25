"""Generate bounded synthetic CPU fixture recipes for exact case parsing.

All generated sources are labelled diagnostic and cannot establish a reviewed
C111329 site, official device status or legal exception.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from delivery_audit import CASES
from site_geometry import assess_site

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
SOURCE_KEYS = ("map", "route", "devices", "markings", "highway")


def serial(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(serial(value))
    return sha(path)


def build_case(case_id, marked, operating):
    short = case_id.split("__")[-1]
    folder = ROOT / "cases" / short
    source_folder = folder / "diagnostic-sources"
    source_folder.mkdir(parents=True, exist_ok=True)
    packet = {"sources": {}, "coordinate_frame": "map_xy_m",
        "highway": {"boundary_document_id": "diagnostic-boundary",
                    "public_access_document_id": "diagnostic-access"},
        "junctions": [{"id": "west", "center": [0, 0], "envelope_radius_m": 8},
                      {"id": "east", "center": [100, 0], "envelope_radius_m": 8}],
        "between_edge": ["west", "east"], "intervening_junction_ids": [],
        "pedestrian_route": [[50, -10], [50, 10]],
        "crossing": {"entry": [50, -10], "exit": [50, 10], "time_s": [10, 35]},
        "highway_banks": [[[0, -3], [100, -3]], [[0, 3], [100, 3]]],
        "devices": [{"junction_id": junction, "device_id": junction + "-signal",
            "authority_record_id": "diagnostic-" + junction + "-authority",
            "placement_record_id": "diagnostic-" + junction + "-placement",
            "purpose_record_id": "diagnostic-" + junction + "-purpose",
            "governing_participants": ["pedestrian"], "instructions": "diagnostic state",
            "operating_intervals_s": [[0, 45]] if operating or junction == "west" else [[0, 8]]}
            for junction in ("west", "east")],
        "markings": {"survey_complete": True,
            "marked_crosswalks": [{"marking_id": "diagnostic-stripe",
                "survey_record_id": "diagnostic-marking-survey",
                "between_edge_station_fraction": [0.45, 0.55]}] if marked else []}}
    parts = {
        "map": {k: packet[k] for k in ("junctions", "between_edge", "intervening_junction_ids", "highway_banks")},
        "route": {k: packet[k] for k in ("pedestrian_route", "crossing")},
        "devices": packet["devices"], "markings": packet["markings"],
        "highway": packet["highway"],
    }
    sources = []
    for name in SOURCE_KEYS:
        path = source_folder / (name + ".json")
        digest = write(path, parts[name])
        packet["sources"][name] = {"path": str(path), "sha256": digest}
        sources.append({"path": "site-sources/" + name + ".json",
                        "source": str(path.relative_to(REPO)), "sha256": digest})
    site = assess_site(packet, require_operating=False)
    frames = []
    trace = []
    mapped = []
    evidence = []
    graph_rows = []
    graphs = []
    for index in range(900):
        frame = index + 1
        time_s = round(index * 0.05, 8)
        y = round(-10 + 20 * index / 899, 8)
        z = 0.0
        position = [50.0, y, z]
        device_rows = [{"device_id": d["device_id"], "actor_id": i + 10,
                        "state": "Green", "is_operating": bool(operating or i == 0)}
                       for i, d in enumerate(packet["devices"])]
        frames.append({"frame": frame, "time_s": time_s,
                       "walker_xyz_m": position, "devices": device_rows})
        trace.append({"frame": frame, "time_s": time_s, "position_m": position,
                      "position": {"x": position[0], "y": y, "z": z},
                      "heading_deg": 90, "velocity_mps": [0, 0.45, 0],
                      "speed_mps": 0.45, "speed_mph": 0.45 / 0.44704, "control": {}})
        mapped.append({"video_frame": index, "carla_frame": frame,
                       "native_frame": frame, "time_s": time_s})
        corners = [[49.8, y-0.2, 0], [49.8, y-0.2, 1],
                   [49.8, y+0.2, 0], [49.8, y+0.2, 1],
                   [50.2, y-0.2, 0], [50.2, y-0.2, 1],
                   [50.2, y+0.2, 0], [50.2, y+0.2, 1]]
        evidence.append({"actor_id": 7, "ego": {"body_vertices_m": corners,
            "heading_deg": 90, "position_m": position, "speed_mps": 0.45,
            "speed_provenance": "synthetic_native_sample"},
            "original_frame": frame,
            "original_observations": {"frame": frame, "time_s": time_s,
                "map_context": {"diagnostic_fixture": True}, "participants": []},
            "recording_time_s": time_s, "replay_frame": frame,
            "replay_simulation_time_s": time_s, "world": {"weather": {}}})
        graph_path = "graphs/base/" + f"{frame:08d}.adapter.json"
        graph_rows.append({"adapter_graph": graph_path, "frame": frame,
                           "simulation_time": time_s})
        graphs.append({"path": "capture/native/" + graph_path, "attributes": {"frame": frame,
            "time_s": time_s,
            "observed_evidence": {"frame": frame, "time_s": time_s,
                "map_context": {"diagnostic_fixture": True}, "participants": []}},
            "nodes": [], "edges": []})
    observation = {"format": "original-pedestrian-site-observation",
        "case_id": case_id, "packet_sha256": hashlib.sha256(serial(packet).encode()).hexdigest(),
        "source_sha256": site["source_sha256"], "frame_count": 900,
        "frames": frames, "camera_sources": {}}
    # The four encoded fixture colors are generated below. No physical camera
    # capture is claimed by this diagnostic observation.
    road = "<?xml version='1.0'?><OpenDRIVE><header revMajor='1' revMinor='4' name='diagnostic-C111329' version='1'/></OpenDRIVE>\n"
    files = {"effective-site-packet.json": serial(packet),
             "original-site-observation.json": serial(observation),
             "road.xodr": road,
             "trace.jsonl": "".join(serial(row) for row in trace),
             "video_frames.jsonl": "".join(serial(row) for row in mapped),
             "capture/evidence.jsonl": "".join(serial(row) for row in evidence),
             "capture/native/frames.jsonl": "".join(serial(row) for row in graph_rows),
             "capture/recorder_info.txt": "Create 7: walker.pedestrian.0001 (diagnostic) at (50, -10, 0)\n",
             "acquisition-provenance.json": serial({"diagnostic_fixture": True,
                                                        "provenance_kind": "synthetic_fixture"})}
    files["capture/manifest.json"] = serial({"acquisition": "synthetic_fixture",
        "case_id": case_id, "diagnostic_fixture": True,
        "extraction_confirmed": True, "frames": 900,
        "sources": {"road.xodr": hashlib.sha256(road.encode()).hexdigest(),
                    "trace.jsonl": hashlib.sha256(files["trace.jsonl"].encode()).hexdigest()}})
    videos = [{"path": name + ".mkv", "frames": 900, "width": width,
               "height": height, "fps": 20, "color": "black"}
              for name, width, height in (("overview", 1920, 1080),
                  ("approach", 1280, 720), ("reference_corner", 1280, 720),
                  ("driver_reference", 1280, 720))]
    diagnostic = {"files": files, "graphs": graphs, "videos": videos}
    diagnostic_path = folder / "diagnostic.json"
    write(diagnostic_path, diagnostic)
    write(folder / "fixture-recipe.json", {"format": "worker-fixture-recipe",
        "generator": {"source": str(diagnostic_path.relative_to(REPO)),
                      "sha256": sha(diagnostic_path)}, "sources": sources})
    return diagnostic_path.stat().st_size


if __name__ == "__main__":
    print({case_id: build_case(case_id, marked, operating)
           for case_id, (marked, operating) in CASES.items()})
