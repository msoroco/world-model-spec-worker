"""Build a source-hashed two-cycle software fixture from the tested event shape."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE / "tests"))
import test_analysis


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build():
    fixture = test_analysis.AnalysisTests("test_saved_analyzer_emits_canonical_result_from_originals")
    fixture.setUp()
    try:
        root = fixture.root
        trace_path = root / "trace.jsonl"
        trace = [json.loads(line) for line in trace_path.read_text(encoding="utf-8").splitlines()]
        for row in trace:
            row.update(heading_deg=0.0, velocity_mps=[row["speed_mps"], 0, 0],
                       position={"x": row["position_m"][0], "y": 0, "z": 0},
                       speed_mph=row["speed_mps"] / .44704)
        trace_path.write_text("".join(json.dumps(row) + "\n" for row in trace), encoding="utf-8")
        saved = json.loads((root / "saved-manifest.json").read_text(encoding="utf-8"))
        videos = []
        dimensions = {"overview": (1920, 1080), "approach": (1280, 720),
                      "reference_corner": (1280, 720), "driver_reference": (1280, 720)}
        for name, view in saved["camera_views"].items():
            video = root / (name + ".mkv")
            video.unlink()
            width, height = dimensions[name]
            subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error",
                            "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r=20",
                            "-frames:v", "900", "-an", "-c:v", "ffv1", "-threads", "1",
                            "-fflags", "+bitexact", "-flags:v", "+bitexact", str(video)], check=True)
            view["source"]["sha256"] = sha(video)
            view["width"], view["height"] = width, height
            videos.append({"path": video.name, "frames": 900, "width": width,
                           "height": height, "fps": 20, "color": "black"})
        write(root / "saved-manifest.json", saved)
        example = json.loads((REPO / "runtime/fixtures/example.json").read_text(encoding="utf-8"))
        template = json.loads(example["files"]["capture/evidence.jsonl"].splitlines()[0])
        native_frame = json.loads(example["files"]["capture/native/frames.jsonl"].splitlines()[0])
        mapping = [json.loads(line) for line in (root / "video_frames.jsonl").read_text().splitlines()]
        evidence = []
        frames = []
        for item, motion in zip(mapping, trace):
            row = json.loads(json.dumps(template))
            row.update(original_frame=item["carla_frame"], replay_frame=item["carla_frame"],
                       recording_time_s=item["time_s"], replay_simulation_time_s=item["time_s"])
            row["ego"]["position_m"] = motion["position_m"]
            row["ego"]["speed_mps"] = motion["speed_mps"]
            row["original_observations"].update(frame=item["carla_frame"], time_s=item["time_s"],
                                                rgb_sensors=[{"actor_id": "diagnostic-rgb-1",
                                                              "blueprint": "sensor.camera.rgb",
                                                              "source_kind": "synthetic_fixture"}])
            row["original_observations"]["participants"] = []
            evidence.append(json.dumps(row, separators=(",", ":")))
            frame = dict(native_frame, frame=item["carla_frame"], simulation_time=item["time_s"])
            frame["adapter_graph"] = f"graphs/base/{item['carla_frame']:08d}.adapter.json"
            frames.append(json.dumps(frame, separators=(",", ":")))
        road = example["files"]["road.xodr"]
        capture_manifest = json.loads(example["files"]["capture/manifest.json"])
        capture_manifest["case_id"] = saved["case_id"]
        capture_manifest["frames"] = 900
        capture_manifest["sources"]["road.xodr"] = hashlib.sha256(road.encode()).hexdigest()
        capture_manifest["sources"]["trace.jsonl"] = sha(trace_path)
        capture_manifest["required_observations"] = []
        capture_manifest["observation_contract_version"] = 2
        generator_files = {
            "road.xodr": road,
            "capture/manifest.json": json.dumps(capture_manifest, sort_keys=True) + "\n",
            "capture/native_map_facts.json": example["files"]["capture/native_map_facts.json"],
            "capture/recorder_info.txt": example["files"]["capture/recorder_info.txt"],
        }
        ego = next(item for item in example["graphs"][0]["nodes"] if item["id"] == "ego")
        original = ego["attributes"]["original_observation"]
        graphs = []
        for item, motion in zip(mapping, trace):
            observation = {key: original[key] for key in ("actor_id", "blueprint",
                           "heading_deg", "body_vertices_m")}
            observation.update(position_m=motion["position_m"],
                               speed_mps=motion["speed_mps"],
                               velocity_mps=motion["velocity_mps"])
            attrs = {"vertex": motion["position_m"], "sem_class": "ego",
                     "entity_id": original["actor_id"],
                     "original_observation": observation}
            graphs.append({"path": f"capture/native/graphs/base/{item['carla_frame']:08d}.adapter.json",
                           "attributes": {"frame": item["carla_frame"], "bbox": {}},
                           "nodes": [{"id": "ego", "attributes": attrs}], "edges": []})
        destination = HERE / "diagnostics" / "two_cycles_clear"
        destination.mkdir(parents=True, exist_ok=True)
        files = ("native-site.json", "saved-manifest.json", "original-events.json",
                 "video_frames.jsonl", "trace.jsonl", "media-receipt.json",
                 "acquisition-provenance.json", "map_ref.json", "route_ref.json",
                 "signal_ref.json", "stop_ref.json", "crosswalk_ref.json", "cause.json")
        sources = []
        for name, content in (("capture/evidence.jsonl", "\n".join(evidence) + "\n"),
                              ("capture/native/frames.jsonl", "\n".join(frames) + "\n")):
            target = HERE / "diagnostics" / "two_cycles_clear" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
            sources.append({"path": name, "source": str(target.relative_to(REPO)),
                            "sha256": sha(target)})
        for name in files:
            source = root / name
            target = destination / name
            target.write_bytes(source.read_bytes())
            sources.append({"path": name, "source": str(target.relative_to(REPO)),
                            "sha256": sha(target)})
        spec_path = HERE / "diagnostics" / "two_cycles_clear-generator.json"
        spec_path.write_text(json.dumps({"files": generator_files, "graphs": graphs,
                                         "videos": videos}, separators=(",", ":")) + "\n",
                             encoding="utf-8")
        recipe = {"format": "worker-fixture-recipe", "sources": sources,
                  "generator": {"source": str(spec_path.relative_to(REPO)),
                                "sha256": sha(spec_path)}}
        recipe_path = HERE / "diagnostics" / "two_cycles_clear-recipe.json"
        write(recipe_path, recipe)
        print("two-cycle source-hashed diagnostic recipe", recipe_path.relative_to(REPO))
    finally:
        fixture.doCleanups()


if __name__ == "__main__":
    build()
