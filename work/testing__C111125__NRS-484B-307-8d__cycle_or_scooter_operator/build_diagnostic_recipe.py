"""Build a source-hashed, 900-frame bicycle software fixture for one exact case."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
sys.path.insert(0, str(HERE / "tests"))
import test_analysis


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(",", ":"), allow_nan=False) + "\n", encoding="utf-8")


def build(suffix="two_cycles_failed_detection"):
    allowed = {"two_cycles_failed_detection", "one_cycle", "three_cycles",
               "signal_changes", "no_prior_stop", "fails_to_yield"}
    if suffix not in allowed:
        raise ValueError("Unknown exact bicycle diagnostic case")
    fixture = test_analysis.AnalysisTests("test_900_frame_finalizer_joins_originals_and_writes_native_result")
    fixture.setUp()
    try:
        fixture.prepare_900_frame_fixture()
        root = fixture.root
        packet_path = root / "packet.json"
        packet = json.loads(packet_path.read_text(encoding="utf-8"))
        packet["case_suffix"] = suffix
        frames = packet["frames"]
        if suffix == "one_cycle":
            for row in frames[400:600]:
                row["cross_signal"] = "red"
        if suffix == "three_cycles":
            for row in frames[650:700]:
                row["cross_signal"] = "green"
            for row in frames[700:750]:
                row["cross_signal"] = "yellow"
            for row in frames[750:800]:
                row["cross_signal"] = "red"
            for row in frames[600:900]:
                row["ego_station_m"] = 0.0 if row["frame"] < 800 else min(10.0, (row["frame"] - 800) / 10)
                row["ego_speed_mps"] = 0.0 if row["frame"] < 800 else 1.0
        if suffix == "signal_changes":
            for row in frames:
                row["detector_output"] = True
                if row["frame"] >= 690:
                    row["subject_signal"] = "green"
        if suffix == "no_prior_stop":
            for row in frames:
                row["ego_speed_mps"] = 0.5
                row["ego_station_m"] = min(10.0, row["frame"] / 70)
        if suffix == "fails_to_yield":
            frames[690]["directed_participant_conflict"] = True
        streams = {
            "native": {"frames": frames, "blueprint_class": "bicycle"},
            "device": {"frames": [{"frame": row["frame"], "subject_signal": row["subject_signal"],
                                   "cross_signal": row["cross_signal"]} for row in frames]},
            "detector": {"frames": [{"frame": row["frame"], "occupied": row["detector_occupied"],
                                     "output": row["detector_output"]} for row in frames]},
        }
        for name, value in streams.items():
            path = root / (name + ".json")
            write(path, value)
            packet[name + "_trace_ref"]["sha256"] = sha(path)
        write(packet_path, packet)
        site_path = root / "native-site.json"
        site = json.loads(site_path.read_text(encoding="utf-8"))
        site["case_id"] = AID + "__" + suffix
        write(site_path, site)
        trace_path = root / "trace.jsonl"
        trace_path.write_text("".join(json.dumps({"frame": row["frame"], "time_s": row["timestamp_s"],
                       "position": {"x": row["ego_station_m"], "y": 0, "z": 0},
                       "heading_deg": 0, "speed_mps": row["ego_speed_mps"]}) + "\n" for row in frames), encoding="utf-8")
        destination = HERE / "diagnostics" / suffix
        destination.mkdir(parents=True, exist_ok=True)
        source_names = (*test_analysis.analysis.SOURCE_NAMES, "trace.jsonl",
                        "video_frames.jsonl", "acquisition-provenance.json")
        sources = []
        for name in source_names:
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((root / name).read_bytes())
            sources.append({"path": name, "source": str(target.relative_to(REPO)),
                            "sha256": sha(target)})
        example = json.loads((REPO / "runtime/fixtures/example.json").read_text(encoding="utf-8"))
        row_template = json.loads(example["files"]["capture/evidence.jsonl"].splitlines()[0])
        frame_template = json.loads(example["files"]["capture/native/frames.jsonl"].splitlines()[0])
        graph_template = example["graphs"][0]
        original = next(node for node in graph_template["nodes"] if node["id"] == "ego")["attributes"]["original_observation"]
        packet = json.loads((root / "packet.json").read_text(encoding="utf-8"))
        trace = [json.loads(line) for line in (root / "trace.jsonl").read_text(encoding="utf-8").splitlines()]
        evidence, native_frames, graphs = [], [], []
        for item, motion in zip(packet["frames"], trace):
            frame, time = item["frame"], item["timestamp_s"]
            position = [motion["position"]["x"], 0, 0]
            velocity = [motion["speed_mps"], 0, 0]
            row = json.loads(json.dumps(row_template))
            row.update(original_frame=frame, replay_frame=frame,
                       recording_time_s=time, replay_simulation_time_s=time)
            row["ego"].update(position_m=position, speed_mps=motion["speed_mps"])
            row["original_observations"].update(frame=frame, time_s=time,
                 rgb_sensors=[{"actor_id": "diagnostic-rgb-1", "blueprint": "sensor.camera.rgb",
                               "source_kind": "synthetic_fixture"}], participants=[])
            evidence.append(json.dumps(row, separators=(",", ":")))
            native = dict(frame_template, frame=frame, simulation_time=time,
                          adapter_graph=f"graphs/base/{frame:08d}.adapter.json")
            native_frames.append(json.dumps(native, separators=(",", ":")))
            observation = {key: original[key] for key in ("actor_id", "blueprint", "heading_deg", "body_vertices_m")}
            observation.update(position_m=position, speed_mps=motion["speed_mps"],
                               velocity_mps=velocity)
            graphs.append({"path": f"capture/native/graphs/base/{frame:08d}.adapter.json",
                           "attributes": {"frame": frame, "bbox": {}, "observed_evidence": row["original_observations"]},
                           "nodes": [{"id": "ego", "attributes": {"vertex": position,
                                      "sem_class": "ego", "entity_id": original["actor_id"],
                                      "original_observation": observation}}], "edges": []})
        for name, lines in (("capture/evidence.jsonl", evidence),
                            ("capture/native/frames.jsonl", native_frames)):
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("\n".join(lines) + "\n", encoding="utf-8")
            sources.append({"path": name, "source": str(target.relative_to(REPO)),
                            "sha256": sha(target)})
        road = example["files"]["road.xodr"]
        manifest = json.loads(example["files"]["capture/manifest.json"])
        manifest["case_id"] = AID + "__" + suffix
        manifest["frames"] = 900
        manifest["sources"]["road.xodr"] = hashlib.sha256(road.encode()).hexdigest()
        manifest["sources"]["trace.jsonl"] = sha(root / "trace.jsonl")
        manifest["required_observations"] = []
        manifest["observation_contract_version"] = 2
        files = {"road.xodr": road,
                 "capture/manifest.json": json.dumps(manifest, sort_keys=True) + "\n",
                 "capture/native_map_facts.json": example["files"]["capture/native_map_facts.json"],
                 "capture/recorder_info.txt": example["files"]["capture/recorder_info.txt"]}
        videos = [{"path": name + ".mkv", "frames": 900, "width": width,
                   "height": height, "fps": 20, "color": "black"}
                  for name, width, height in (("overview", 1920, 1080), ("approach", 1280, 720),
                                               ("reference_corner", 1280, 720),
                                               ("driver_reference", 1280, 720))]
        spec_path = HERE / "diagnostics" / (suffix + "-generator.json")
        write(spec_path, {"files": files, "graphs": graphs, "videos": videos})
        recipe_path = HERE / "diagnostics" / (suffix + "-recipe.json")
        write(recipe_path, {"format": "worker-fixture-recipe", "sources": sources,
                            "generator": {"source": str(spec_path.relative_to(REPO)),
                                          "sha256": sha(spec_path)}})
        print(recipe_path.relative_to(REPO))
    finally:
        fixture.doCleanups()


if __name__ == "__main__":
    build(sys.argv[1] if len(sys.argv) > 1 else "two_cycles_failed_detection")
