"""Build a source-hashed, generated diagnostic fixture for the reference case.

The videos are synthetic solid colors. This checks saved source joins and the
fixture protocol; it does not represent Native capture or participant pixels.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

from native_camera import VIEWS
from saved_measurement import sha
from tests.test_saved_measurement import fixture
from tests.test_native_scene import packet

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUTPUT_ROOT = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ""))
if not OUTPUT_ROOT.is_absolute() or not OUTPUT_ROOT.is_relative_to(ROOT / ".runtime-work"):
    raise SystemExit("Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work first")


def adapt_attempt(attempt: Path, case_id: str, variables: dict):
    setup_path = attempt / "authored-setup.json"
    setup = json.loads(setup_path.read_text(encoding="utf-8"))
    setup.update(case_id=case_id, variables=variables)
    setup_path.write_text(json.dumps(setup), encoding="utf-8")
    setup_seal = attempt / "authored-setup-seal.json"
    setup_seal.write_text(json.dumps({"format": "c179789-authored-setup-v1",
                                      "case_id": case_id, "sha256": sha(setup_path)}),
                          encoding="utf-8")
    conditions_path = attempt / "original-conditions.jsonl"
    rows = [json.loads(line) for line in conditions_path.read_text(encoding="utf-8").splitlines()]
    for row in rows:
        row.update(ego_speed_mps=float(variables["ego_speed_request_mps"]),
                   leader_gap_m=float(variables["leader_initial_gap_m"]),
                   highway_width_m=float(variables["highway_width_m"]),
                   roadway_driving_width_m=float(variables["highway_width_m"]),
                   surface_wetness=float(variables["surface_wetness_request"]),
                   precipitation_strength=float(variables["native_precipitation_request"]),
                   fog_density=float(variables["native_fog_request"]))
    conditions_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
                               encoding="utf-8")
    condition_seal = attempt / "original-conditions-seal.json"
    seal = json.loads(condition_seal.read_text(encoding="utf-8"))
    seal.update(case_id=case_id, sha256=sha(conditions_path))
    condition_seal.write_text(json.dumps(seal), encoding="utf-8")
    status_path = attempt / "native-run-status.json"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    status["case_id"] = case_id
    status_path.write_text(json.dumps(status), encoding="utf-8")
    trace_path = attempt / "trace.jsonl"
    trace_rows = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
    for row in trace_rows:
        x, y, z = row["position_m"]
        row["position"] = {"x": x, "y": y, "z": z}
        row["heading_deg"] = 0.0
        row["speed_mps"] = float(variables["ego_speed_request_mps"])
        row["speed_mph"] = row["speed_mps"] / 0.44704
        row["velocity_mps"] = [row["speed_mps"], 0.0, 0.0]
    trace_path.write_text("".join(json.dumps(row, sort_keys=True) + "\n"
                                  for row in trace_rows), encoding="utf-8")


def build():
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=OUTPUT_ROOT) as temporary:
        attempt = Path(temporary) / "attempt"
        fixture(attempt)
        videos = []
        video_hashes = {}
        for name, width, height in VIEWS:
            path = attempt / (name + ".mkv")
            path.unlink()
            subprocess.run([
                "ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r=20",
                "-frames:v", "900", "-an", "-c:v", "ffv1", "-threads", "1",
                "-fflags", "+bitexact", "-flags:v", "+bitexact", str(path),
            ], check=True, timeout=120)
            videos.append({"path": path.name, "frames": 900, "width": width,
                           "height": height, "fps": 20, "color": "black"})
            video_hashes[name] = sha(path)
        note_path = HERE / "diagnostic-origin.txt"
        note_path.write_text("Synthetic seven-case source-join protocol; no physical or legal acceptance.\n",
                             encoding="utf-8")
        source = packet()
        example_files = json.loads((ROOT / "runtime/fixtures/example.json").read_text(encoding="utf-8"))["files"]
        for case_id, case in source["cases"].items():
            suffix = case_id.rsplit("__", 1)[-1]
            adapt_attempt(attempt, case_id, case["variables"])
            receipt = attempt / "media-receipt.json"
            document = json.loads(receipt.read_text(encoding="utf-8"))
            document["video_sha256"] = video_hashes
            document["trace_sha256"] = sha(attempt / "trace.jsonl")
            receipt.write_text(json.dumps(document), encoding="utf-8")
            files = {path.name: path.read_text(encoding="utf-8") for path in attempt.iterdir()
                     if path.is_file() and path.suffix != ".mkv"}
            trace_rows = [json.loads(line) for line in files["trace.jsonl"].splitlines()]
            evidence = []
            frame_index = []
            graphs = []
            for row in trace_rows:
                frame = row["frame"]
                stamp = row["time_s"]
                graph_path = f"capture/native/graphs/base/{frame:08d}.adapter.json"
                graphs.append({"path": graph_path, "attributes": {"frame": frame},
                               "nodes": [], "edges": []})
                evidence.append({"original_frame": frame, "replay_frame": frame,
                                 "actor_id": 205, "recording_time_s": stamp,
                                 "replay_simulation_time_s": stamp,
                                 "ego": {"position_m": row["position_m"],
                                         "heading_deg": row["heading_deg"],
                                         "speed_mps": row["speed_mps"],
                                         "speed_provenance": "synthetic_native_sample",
                                         "body_vertices_m": [[-2.4,-0.9,0],[-2.4,-0.9,1.5],
                                                             [-2.4,0.9,0],[-2.4,0.9,1.5],
                                                             [2.4,-0.9,0],[2.4,-0.9,1.5],
                                                             [2.4,0.9,0],[2.4,0.9,1.5]]},
                                 "world": {"weather": {}}, "visibility": None})
                frame_index.append({"frame": frame, "simulation_time": stamp,
                                    "adapter_graph": f"graphs/base/{frame:08d}.adapter.json"})
            files["capture/evidence.jsonl"] = "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in evidence)
            files["capture/native/frames.jsonl"] = "".join(json.dumps(row, separators=(",", ":")) + "\n" for row in frame_index)
            files["capture/recorder_info.txt"] = "Create 205: vehicle.tesla.model3\n"
            files["road.xodr"] = example_files["road.xodr"]
            files["capture/manifest.json"] = json.dumps({
                "status": "diagnostic", "acquisition": "original_live_run",
                "case_id": case_id, "frames": len(trace_rows),
                "extraction_confirmed": True, "required_observations": [],
                "sources": {"road.xodr": hashlib.sha256(files["road.xodr"].encode()).hexdigest(),
                            "trace.jsonl": hashlib.sha256(files["trace.jsonl"].encode()).hexdigest()},
            }, separators=(",", ":"))
            folder = HERE if suffix == "reference" else HERE / "diagnostics" / suffix
            folder.mkdir(parents=True, exist_ok=True)
            extra_sources = []
            for destination in ("capture/evidence.jsonl", "capture/native/frames.jsonl",
                                "capture/manifest.json", "capture/recorder_info.txt", "road.xodr"):
                name = "source-" + destination.replace("/", "-")
                path = folder / name
                path.write_text(files.pop(destination), encoding="utf-8")
                if path.stat().st_size > 2 * 1024 * 1024:
                    raise ValueError("diagnostic source exceeds returned-file limit")
                extra_sources.append({"path": destination,
                                      "source": path.relative_to(ROOT).as_posix(),
                                      "sha256": sha(path)})
            specification = {"files": files, "graphs": graphs, "videos": videos}
            specification_path = folder / "diagnostic.json"
            specification_text = json.dumps(specification, sort_keys=True,
                                             separators=(",", ":")) + "\n"
            if len(specification_text.encode()) > 2 * 1024 * 1024:
                raise ValueError("diagnostic specification exceeds returned-file limit")
            specification_path.write_text(specification_text, encoding="utf-8")
            relative = "work/" + HERE.name + "/"
            recipe = {"format": "worker-fixture-recipe", "sources": [{
                "path": "diagnostic-origin.txt", "source": relative + note_path.name,
                "sha256": hashlib.sha256(note_path.read_bytes()).hexdigest(),
            }] + extra_sources, "generator": {"source": str(specification_path.relative_to(ROOT)),
                              "sha256": hashlib.sha256(specification_path.read_bytes()).hexdigest()}}
            (folder / "diagnostic-recipe.json").write_text(
                json.dumps(recipe, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            print(json.dumps({"case_id": case_id, "source_files": len(files),
                              "videos": len(videos),
                              "specification_bytes": len(specification_text.encode())},
                             sort_keys=True))


if __name__ == "__main__":
    build()
