"""Build a source-shaped probe_a diagnostic without claiming original capture."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import shutil

from prove_original import fixture


ROOT = Path(__file__).resolve().parent.parent
REPO = ROOT.parent.parent
CASE = ROOT.name + "__probe_a"
DEST = ROOT / "selected/probe_a/diagnostic"
TEMP = REPO / ".runtime-work/c183370-probe-a-fixture-build"
CAMERAS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value)


def lines(rows):
    return "".join(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n"
                   for row in rows)


def main():
    if TEMP.exists():
        shutil.rmtree(TEMP)
    TEMP.mkdir(parents=True)
    fixture(TEMP, "probe_a")
    original = [json.loads(line) for line in (TEMP / "native-rows.jsonl").read_text().splitlines()]
    traces, evidence, frames, graph_specs = [], [], [], []
    for index, row in enumerate(original):
        frame, time_s = row["native_frame"], row["time_s"]
        xyz = row["motorcycle_xyz_m"]
        traces.append({"frame": frame, "time_s": time_s,
                       "position": {"x": xyz[0], "y": xyz[1], "z": xyz[2]},
                       "heading_deg": 0.0,
                       "speed_mps": row["motorcycle_speed_mps"]})
        evidence.append({"original_frame": frame, "recording_time_s": time_s,
                         "ego": {"position_m": xyz,
                                 "speed_mps": row["motorcycle_speed_mps"]}})
        graph_path = "capture/native/graphs/base/" + str(index).zfill(8) + ".adapter.json"
        frames.append({"frame": frame, "time_s": time_s,
                       "simulation_time": time_s,
                       "base": "graphs/base/" + str(index).zfill(8) + ".adapter.json",
                       "adapter_graph": "graphs/base/" + str(index).zfill(8) + ".adapter.json",
                       "nodes": 2, "edges": 0})
        graph_specs.append({"path": graph_path,
                            "attributes": {"frame": frame, "simulation_time_s": time_s,
                                           "source": "C183370 generated CPU diagnostic",
                                           "synthetic_diagnostic": True},
                            "edges": [], "nodes": [
                                {"id": "ego", "attributes": {
                                    "entity_id": 12, "sem_class": "ego", "vertex": xyz,
                                    "forward": [1, 0, 0],
                                    "threedbbox": row["motorcycle_body_vertices_m"]}},
                                {"id": "flagger", "attributes": {
                                    "entity_id": 13, "sem_class": "pedestrian",
                                    "vertex": [0, -7, 1], "forward": [0, 1, 0],
                                    "threedbbox": [[dx, -7 + dy, z]
                                                   for dx in (-0.3, 0.3)
                                                   for dy in (-0.3, 0.3)
                                                   for z in (0, 1.8)]}}]})
    native_map = [json.loads(line) for line in (TEMP / "video_frames.jsonl").read_text().splitlines()]
    for row in native_map:
        row["carla_frame"] = row["native_frame"]
    write(TEMP / "video_frames.jsonl", lines(native_map))
    write(TEMP / "trace.jsonl", lines(traces))
    write(TEMP / "capture/evidence.jsonl", lines(evidence))
    videos = []
    config = json.loads((ROOT / "native/probe_a/config.json").read_text())
    for name in CAMERAS:
        target = TEMP / (name + ".mkv")
        target.unlink()
        spec = config["cameras"][name]
        videos.append({"path": name + ".mkv", "frames": 600,
                       "width": spec["width"], "height": spec["height"],
                       "fps": 20, "color": "black"})
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                        "-f", "lavfi", "-i", "color=c=black:s=" + str(spec["width"]) +
                        "x" + str(spec["height"]) + ":r=20", "-frames:v", "600",
                        "-an", "-c:v", "ffv1", "-threads", "1", "-fflags", "+bitexact",
                        "-flags:v", "+bitexact", str(target)], check=True, timeout=120)
    seal = json.loads((TEMP / "captured-source-hashes.json").read_text())
    seal["sha256"] = {name: sha(TEMP / name) for name in seal["sha256"]}
    write(TEMP / "captured-source-hashes.json", json.dumps(seal) + "\n")
    source_names = ["road.xodr", "native-rows.jsonl", "video_frames.jsonl",
                    "original-flagger-review.json", "original-authority-source",
                    "original-zone-source", "original-signal-source",
                    "captured-source-hashes.json", "trace.jsonl", "capture/evidence.jsonl"]
    sources = []
    for name in source_names:
        target = DEST / "sources" / name
        write(target, (TEMP / name).read_text())
        sources.append({"path": name,
                        "source": str(target.relative_to(REPO)), "sha256": sha(target)})
    capture_manifest = {"extraction_confirmed": True, "frames": 600,
                        "synthetic_diagnostic": True,
                        "sources": {name: sha(TEMP / name) for name in
                                    ("road.xodr", "native-rows.jsonl", "trace.jsonl")}}
    target = DEST / "sources/capture/manifest.json"
    write(target, json.dumps(capture_manifest, separators=(",", ":")) + "\n")
    sources.append({"path": "capture/manifest.json", "source": str(target.relative_to(REPO)),
                    "sha256": sha(target)})
    spec = {"files": {"capture/native/frames.jsonl": lines(frames),
                       "capture/recorder_info.txt": "C183370 synthetic diagnostic only\n"},
            "graphs": graph_specs, "videos": videos}
    spec_path = DEST / "fixture-spec.json"
    write(spec_path, json.dumps(spec, separators=(",", ":")) + "\n")
    recipe = {"format": "worker-fixture-recipe",
              "generator": {"source": str(spec_path.relative_to(REPO)),
                            "sha256": sha(spec_path)}, "sources": sources}
    recipe_path = DEST / "fixture-recipe.json"
    write(recipe_path, json.dumps(recipe, separators=(",", ":")) + "\n")
    print(json.dumps({"case_id": CASE, "recipe_sha256": sha(recipe_path),
                      "source_count": len(sources), "graph_count": len(graph_specs)}))


if __name__ == "__main__":
    main()
