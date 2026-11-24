"""Inventory seven synthetic original-shaped saved attempts for pinned CPU conversion."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SCRATCH = REPO / ".runtime-work/c109035-delivery-proofs"
VIEWS = (("overview", 1920, 1080), ("approach", 1280, 720),
         ("reference_corner", 1280, 720), ("driver_reference", 1280, 720))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if value.endswith("\n") else value + "\n")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Returned source exceeds 2 MiB: " + str(path))


def main() -> None:
    plan = json.loads((HERE / "case-plan.json").read_text())
    example = json.loads((REPO / "runtime/fixtures/example.json").read_text())
    for case in plan["cases"]:
        case_id = case["case_id"]
        suffix = case_id.removeprefix(HERE.name + "__")
        capture = SCRATCH / suffix / "positive/capture"
        if not (capture / "capture_receipt.json").is_file():
            raise ValueError("Build original-shaped diagnostic capture first: " + suffix)
        root = HERE / "fixtures" / suffix
        root.mkdir(parents=True, exist_ok=True)
        sources = []

        def add_source(destination: str, data: bytes) -> None:
            own = root / destination
            own.parent.mkdir(parents=True, exist_ok=True)
            own.write_bytes(data)
            if own.stat().st_size > 2 * 1024 * 1024:
                raise ValueError("Returned source exceeds 2 MiB: " + str(own))
            sources.append({"path": destination,
                            "source": own.relative_to(REPO).as_posix(),
                            "sha256": sha(own)})

        for source in sorted(capture.iterdir()):
            if source.is_file():
                add_source(source.name, source.read_bytes())
        actors = [json.loads(line) for line in (capture / "actor_trace.jsonl").read_text().splitlines()]
        devices = [json.loads(line) for line in (capture / "device_trace.jsonl").read_text().splitlines()]
        if len(actors) != 900 or len(devices) != 900:
            raise ValueError("Diagnostic original rows incomplete")
        trace, frame_map, evidence, frame_index, graphs = [], [], [], [], []
        for index, (actor, device) in enumerate(zip(actors, devices)):
            frame, time_s = actor["native_frame"], index / 20
            if device["native_frame"] != frame:
                raise ValueError("Original actor/device frame differs")
            ego = actor["ego"]
            position = [ego[key] for key in ("x_m", "y_m", "z_m")]
            trace.append({"frame": frame, "time_s": time_s,
                          "position": dict(zip(("x", "y", "z"), position)),
                          "position_m": position, "heading_deg": ego["yaw_deg"],
                          "speed_mps": 85 / 45, "speed_mph": (85 / 45) / .44704,
                          "velocity_mps": [85 / 45, 0, 0],
                          "control": {"throttle": .2, "brake": 0.0,
                                      "hand_brake": False},
                          "source_frame": frame,
                          "physical_acceptance_claimed": False})
            frame_map.append({"video_frame": index, "carla_frame": frame,
                              "native_frame": frame, "time_s": time_s})
            graph_path = f"capture/native/graphs/base/{frame:08d}.adapter.json"
            graphs.append({"path": graph_path, "attributes": {"frame": frame},
                           "nodes": [], "edges": []})
            evidence.append({"original_frame": frame, "replay_frame": frame,
                             "actor_id": ego["actor_id"],
                             "recording_time_s": time_s,
                             "replay_simulation_time_s": time_s,
                             "ego": {"position_m": position,
                                     "heading_deg": ego["yaw_deg"],
                                     "speed_mps": 85 / 45,
                                     "speed_provenance": "synthetic_native_sample",
                                     "body_vertices_m": [[position[0] + dx, position[1] + dy, position[2] + dz]
                                                         for dx in (-2.4, 2.4)
                                                         for dy in (-0.9, 0.9)
                                                         for dz in (0, 1.5)]},
                             "world": {"weather": {}}, "visibility": None})
            frame_index.append({"frame": frame, "simulation_time": time_s,
                                "adapter_graph": f"graphs/base/{frame:08d}.adapter.json"})
        compact = lambda rows: "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in rows)
        add_source("trace.jsonl", compact(trace).encode())
        add_source("video_frames.jsonl", compact(frame_map).encode())
        add_source("capture/evidence.jsonl", compact(evidence).encode())
        add_source("capture/native/frames.jsonl", compact(frame_index).encode())
        add_source("capture/recorder_info.txt",
                   f"Create {actors[0]['ego']['actor_id']}: vehicle.tesla.model3\n".encode())
        add_source("road.xodr", example["files"]["road.xodr"].encode())
        manifest = {"status": "diagnostic", "acquisition": "original_live_run",
                    "case_id": case_id, "frames": 900,
                    "extraction_confirmed": True, "required_observations": [],
                    "sources": {"road.xodr": sha(root / "road.xodr"),
                                "trace.jsonl": sha(root / "trace.jsonl")}}
        add_source("capture/manifest.json", (json.dumps(manifest, separators=(",", ":")) + "\n").encode())
        spec = {"files": {}, "graphs": graphs,
                "videos": [{"path": name + ".mkv", "frames": 900,
                            "width": width, "height": height, "fps": 20,
                            "color": "black"} for name, width, height in VIEWS]}
        spec_path = root / "diagnostic.json"
        write(spec_path, json.dumps(spec, separators=(",", ":")))
        recipe = {"format": "worker-fixture-recipe", "sources": sources,
                  "generator": {"source": spec_path.relative_to(REPO).as_posix(),
                                "sha256": sha(spec_path)}}
        recipe_path = root / "recipe.json"
        write(recipe_path, json.dumps(recipe, indent=2))
        print(case_id, len(sources), recipe_path.relative_to(REPO))


if __name__ == "__main__":
    main()
