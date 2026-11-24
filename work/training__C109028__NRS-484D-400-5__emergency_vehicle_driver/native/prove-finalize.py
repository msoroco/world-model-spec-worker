"""Exercise the saved-only source join with an explicit synthetic CPU fixture."""
import json
import argparse
import base64
import hashlib
import math
import os
import shutil
import tempfile
import zlib
from array import array
from pathlib import Path

from finalize import finalize, siren_source_measurement
from source_acquisition import sha

HERE = Path(__file__).resolve().parent
SCRATCH = HERE.parents[2] / ".runtime-work"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")


def rows(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row) + "\n" for row in value))


def rejected(command, phrase):
    try:
        command()
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
        return str(exc)
    raise AssertionError("Missing original source passed")


POLICIES = {
    "probe_a": (True, False, True),
    "probe_b": (False, False, True),
    "pursuit": (False, True, True),
    "call_lamps_only": (True, False, False),
    "ordinary_lamps_only": (False, False, False),
    "sweep_0": (False, True, True),
    "sweep_1": (False, True, True),
    "sweep_2": (False, True, True),
    "sweep_3": (False, True, True),
}

SWEEP = {"sweep_0": (500, 10), "sweep_1": (500, 20),
         "sweep_2": (600, 10), "sweep_3": (600, 20)}


def run(emit=False, case="probe_a"):
    if case not in POLICIES:
        raise ValueError("Unknown exact branch")
    call, pursuit, siren = POLICIES[case]
    observer_distance, approach_distance = SWEEP.get(case, (500, 10))
    SCRATCH.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=SCRATCH, prefix="c109028-finalize-") as temp:
        base = Path(temp)
        config = json.loads((HERE / "config.json").read_text())
        config["case_id"] = HERE.parent.name + "__" + case
        config["selected_case_id"] = config["case_id"]
        config["case"]["case_id"] = config["case_id"]
        config["emergency_call_requested"] = call
        config["immediate_pursuit_requested"] = pursuit
        config["siren_requested"] = siren
        config["observer_distance_ft"] = observer_distance
        config["other_approach_distance_m"] = approach_distance
        config["other_spawn_s_m"] = 15 if approach_distance == 10 else 25
        write(base / "config.json", config)
        samples = array("h", [0]) * (48000 * 30)
        if siren:
            for sample in range(100 * 2400, 300 * 2400):
                samples[sample] = round(5000 * math.sin(2 * math.pi * 800 * sample / 48000))
        pcm = samples.tobytes()
        write(base / "microphone-pcm16.json", {
            "format": "c109028-pcm16-zlib-base64-v1",
            "source_kind": "independent_microphone_pcm", "rate_hz": 48000,
            "channels": 1, "sample_width_bytes": 2, "samples": 48000 * 30,
            "pcm_sha256": hashlib.sha256(pcm).hexdigest(),
            "payload": base64.b64encode(zlib.compress(pcm)).decode()})
        audio_hash = sha(base / "microphone-pcm16.json")
        write(base / "dispatch-source.json", {"source_kind": "synthetic_cpu_fixture"})
        write(base / "vehicle-authorization.json", {
            "source_kind": "original_authorization_document", "vehicle_actor_id": 205,
            "vehicle_blueprint_id": "vehicle.ford.ambulance",
            "authority_name": "synthetic fixture", "document_identifier": "fixture"})
        write(base / "acoustic-report.json", {
            "method": "synthetic fixture", "normal_conditions": True,
            "distance_ft": observer_distance, "observer": "synthetic fixture",
            "source_audio_sha256": audio_hash, "audibility_assessment": "uncertain",
            "calibration_source": "synthetic fixture"})
        write(base / "capture/manifest.json", {"frames": 600,
                                                "extraction_confirmed": True})
        native, mapping, trace, evidence, audio, dispatch = [], [], [], [], [], []
        for i in range(600):
            frame, t = i + 1000, (i + 1) / 20
            center = [5 + 2 * t, 0.0]
            body = [[center[0] + dx, dy, z] for dx in (-1, 1)
                    for dy in (-1, 1) for z in (0, 1)]
            other_center = [50 - approach_distance, 0.0]
            other_body = [[other_center[0] + dx, dy, z] for dx in (-1, 1)
                          for dy in (-1, 1) for z in (0, 1)]
            native.append({"source_kind": "original_native", "native_frame": frame,
                           "time_s": t, "ego": {"actor_id": 205,
                           "blueprint_id": "vehicle.ford.ambulance",
                           "center_xy_m": center, "body_vertices_m": body,
                           "speed_mps": 2},
                           "other": {"actor_id": 202,
                                     "blueprint_id": "vehicle.lincoln.mkz_2020",
                                     "body_vertices_m": other_body},
                           "special1_native_readback": 80 <= i < 330})
            mapping.append({"video_frame": i, "carla_frame": frame,
                            "native_frame": frame, "time_s": t})
            trace.append({"frame": frame, "time_s": t, "position_m": center,
                          "position": {"x": center[0], "y": center[1], "z": 0},
                          "heading_deg": 0, "speed_mps": 2,
                          "velocity_mps": [2, 0, 0],
                          "control": {"throttle": .2, "steer": 0,
                                      "brake": 0, "hand_brake": False,
                                      "reverse": False, "manual_gear_shift": False,
                                      "gear": 1}})
            evidence.append({"original_frame": frame})
            audio.append({"source_kind": "independent_microphone_review",
                          "audio_sha256": audio_hash, "native_frame": frame,
                          "time_s": t, "reviewer": "synthetic fixture",
                          "siren_audible": siren and 100 <= i < 300})
            dispatch.append({"source_kind": "original_dispatch_record",
                             "document_sha256": sha(base / "dispatch-source.json"),
                             "native_frame": frame, "time_s": t,
                             "emergency_call_documented": call,
                             "immediate_pursuit_documented": pursuit})
        for name, value in (("native_samples.jsonl", native),
                            ("video_frames.jsonl", mapping), ("trace.jsonl", trace),
                            ("capture/evidence.jsonl", evidence),
                            ("audio_observations.jsonl", audio),
                            ("dispatch.jsonl", dispatch)):
            rows(base / name, value)
        if emit:
            selected = HERE.parent / "selected-fixture" / case
            selected.mkdir(parents=True, exist_ok=True)
            example = json.loads((HERE.parents[2] / "runtime/fixtures/example.json").read_text())
            preserved = {name: value for name, value in example["files"].items()
                         if name not in {"trace.jsonl", "video_frames.jsonl",
                                         "capture/evidence.jsonl", "capture/manifest.json",
                                         "capture/native/frames.jsonl",
                                         "alley_context.json", "body_history.jsonl",
                                         "speed_samples.jsonl"}}
            names = ("trace.jsonl", "video_frames.jsonl", "capture/evidence.jsonl",
                     "capture/manifest.json", "native_samples.jsonl",
                     "microphone-pcm16.json", "audio_observations.jsonl",
                     "dispatch.jsonl", "dispatch-source.json",
                     "vehicle-authorization.json", "acoustic-report.json")
            preserved.update({name: (base / name).read_text() for name in names
                              if name not in {"capture/evidence.jsonl", "capture/manifest.json"}})
            original = json.loads(example["files"]["capture/evidence.jsonl"].splitlines()[0])
            generated_evidence, graph_frames = [], []
            graph_paths = [f"graphs/base/{i + 1000:08d}.adapter.json"
                           for i in range(600)]
            for i, (sample, scene) in enumerate(zip(native, trace)):
                frame, t = sample["native_frame"], sample["time_s"]
                event = {key: original[key] for key in
                         ("world", "timing", "visibility", "supporting_only")}
                event.update(original_frame=frame, replay_frame=frame, actor_id=205,
                             recording_time_s=t,
                             replay_simulation_time_s=13.5175311319 + t,
                             ego={"position_m": scene["position_m"] + [0],
                                  "heading_deg": 0, "speed_mps": 2,
                                  "speed_provenance": "synthetic_native_sample",
                                  "body_vertices_m": sample["ego"]["body_vertices_m"]},
                             original_observations={
                                 "rgb_sensors": [{"actor_id": 301,
                                     "blueprint": "sensor.camera.rgb",
                                     "parent_actor_id": 205,
                                     "attributes": {"image_size_x": "1920",
                                                    "image_size_y": "1080"}}],
                                 "world_settings": {"no_rendering_mode": False},
                                 "frame": frame, "time_s": t, "devices": [],
                                 "participants": [], "relations": [],
                                 "participant_inventory": "synthetic fixture",
                                 "map_context": original["original_observations"]["map_context"]})
                generated_evidence.append(event)
                graph_frames.append({"frame": frame,
                                     "simulation_time": event["replay_simulation_time_s"],
                                     "abstract": None, "base": None,
                                     "nodes": 4, "edges": 7,
                                     "extraction_seconds": 0,
                                     "capture_seconds": 0,
                                     "adapter_graph": graph_paths[i]})
                scene["speed_mph"] = 2 / .44704
            preserved["trace.jsonl"] = "".join(json.dumps(r) + "\n" for r in trace)
            preserved["capture/evidence.jsonl"] = "".join(
                json.dumps(r, separators=(",", ":")) + "\n" for r in generated_evidence)
            preserved["capture/native/frames.jsonl"] = "".join(
                json.dumps(r, separators=(",", ":")) + "\n" for r in graph_frames)
            manifest = json.loads(example["files"]["capture/manifest.json"])
            manifest.update(case_id=config["case_id"], frames=600)
            manifest["sources"]["trace.jsonl"] = hashlib.sha256(
                preserved["trace.jsonl"].encode()).hexdigest()
            preserved["capture/manifest.json"] = json.dumps(manifest) + "\n"
            spec = {"files": preserved, "graphs": [],
                    "videos": [dict(video, frames=600) for video in example["videos"]]}
            path = selected / "diagnostic.json"
            path.write_text(json.dumps(spec, separators=(",", ":")) + "\n")
            source = str(path.relative_to(HERE.parents[2]))
            note = selected / "source-note.json"
            write(note, {"scope": "synthetic CPU compatibility fixture only",
                         "original_microphone_or_dispatch_acquired": False})
            note_source = str(note.relative_to(HERE.parents[2]))
            sources = [{"path": "source-note.json", "source": note_source,
                        "sha256": sha(note)}]
            graph_dir = HERE.parent / "selected-fixture/probe_a/graph-sources"
            if case == "probe_a":
                from worker_exchange.fixture_generator import _graph
                from traffic_spec_adapter.adapter import write_adapter_graph
                with tempfile.TemporaryDirectory(dir=SCRATCH, prefix="c109028-graphs-") as stage:
                    staging = Path(stage) / "graph-sources"
                    staging.mkdir()
                    for i, graph_path in enumerate(graph_paths):
                        source_graph = example["graphs"][i % len(example["graphs"])]
                        graph_target = staging / Path(graph_path).name
                        graph = _graph(source_graph)
                        graph.graph["frame"] = i + 1000
                        graph.graph["simulation_time_s"] = 13.5175311319 + (i + 1) / 20
                        graph.graph["observed_evidence"] = generated_evidence[i]["original_observations"]
                        write_adapter_graph(graph, graph_target)
                    if graph_dir.exists():
                        shutil.rmtree(graph_dir)
                    os.replace(staging, graph_dir)
            for graph_path in graph_paths:
                graph_target = graph_dir / Path(graph_path).name
                sources.append({"path": "capture/native/" + graph_path,
                                "source": str(graph_target.relative_to(HERE.parents[2])),
                                "sha256": sha(graph_target)})
            write(selected / "recipe.json", {
                "format": "worker-fixture-recipe", "sources": sources,
                "generator": {"source": source, "sha256": sha(path)}})
        measurement = siren_source_measurement(base)
        assert measurement["frames"] == 600
        assert measurement["observed_siren_frames"] == (200 if siren else 0)
        assert measurement["legal_siren_use_conclusion"] is None
        missing = base / "audio_observations.jsonl"
        saved = missing.read_bytes()
        missing.unlink()
        negative = rejected(lambda: siren_source_measurement(base),
                            "Missing required source: audio_observations.jsonl")
        missing.write_bytes(saved)
        for video in ("overview.mkv", "approach.mkv", "reference_corner.mkv",
                      "driver_reference.mkv"):
            (base / video).write_bytes(b"synthetic-only-video-placeholder")
        finalize(base, base / "analysis-report.json")
        assert (base / "result.json").is_file()
        receipt = {"format": "c109028-saved-finalizer-cpu-fixture-v1",
                   "case": case,
                   "positive": "600 source-joined frames, reviewed audible frames match the selected branch",
                   "negative": negative, "physical_or_legal_success_claimed": False,
                   "original_audio_acquired": False}
    write(HERE / f"{case}-finalizer-cpu-proof.json", receipt)
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--emit-spec", action="store_true")
    parser.add_argument("--case", choices=sorted(POLICIES), default="probe_a")
    args = parser.parse_args()
    print(json.dumps(run(args.emit_spec, args.case), sort_keys=True))
