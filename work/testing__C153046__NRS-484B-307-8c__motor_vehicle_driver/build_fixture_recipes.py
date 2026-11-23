"""Inventory source-bound, text-generated CPU diagnostics for all exact cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import copy

from build_case_plan import KINDS
from tests.test_saved_finalizer import attempt

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CAMERAS = (("overview", 1920, 1080, "red"),
           ("approach", 1280, 720, "green"),
           ("reference_corner", 1280, 720, "blue"),
           ("driver_reference", 1280, 720, "white"))


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build() -> None:
    private = REPO / ".runtime-work" / "c153046-fixture-source-build"
    private.mkdir(parents=True, exist_ok=True)
    example = json.loads((REPO / "runtime" / "fixtures" / "example.json").read_text())
    source_events = [json.loads(line) for line in example["files"]["capture/evidence.jsonl"].splitlines() if line]
    source_frames = [json.loads(line) for line in example["files"]["capture/native/frames.jsonl"].splitlines() if line]
    for suffix in KINDS:
        folder = ROOT / "diagnostics" / suffix
        folder.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=private) as temporary:
            fixture = Path(temporary)
            case_id = attempt(fixture, suffix=suffix)
            generated = {path.name: path.read_text(encoding="utf-8")
                         for path in sorted(fixture.iterdir())
                         if path.suffix in (".txt", ".json", ".jsonl") and
                         path.name != "config.json"}
        # Rebuild a Native-shaped diagnostic acquisition around the exact case
        # trace. The supplied example is a schema seed only; these generated
        # bytes never claim original motion or source authority.
        generated["opendrive.txt"] = example["files"]["road.xodr"]
        site = json.loads(generated["site.json"])
        site["sources"]["opendrive"]["sha256"] = hashlib.sha256(
            generated["opendrive.txt"].encode()).hexdigest()
        generated["site.json"] = json.dumps(site)
        site_hash = hashlib.sha256(generated["site.json"].encode()).hexdigest()
        trace = [json.loads(line) for line in generated["trace.jsonl"].splitlines() if line]
        events = []
        frames = []
        graphs = []
        for index, row in enumerate(trace):
            row["source_packet_sha256"] = site_hash
            frame = row["native_frame"]
            ego = frame["ego"]
            center = ego["location_xyz_m"]
            row["position_m"] = center
            row["speed_mph"] = row["speed_mps"] / .44704
            row["velocity_mps"] = ego["velocity_xyz_mps"]
            row["control"] = row["control_request"]
            sample = min(index, len(source_events) - 1)
            event = copy.deepcopy(source_events[sample])
            event.update(original_frame=index, replay_frame=index,
                         recording_time_s=row["time_s"],
                         replay_simulation_time_s=row["time_s"],
                         actor_id=205)
            event["ego"].update(position_m=center, speed_mps=row["speed_mps"],
                                speed_provenance="synthetic_native_sample",
                                velocity_mps=ego["velocity_xyz_mps"],
                                body_vertices_m=ego["body_vertices_xyz_m"])
            observed = event["original_observations"]
            observed.update(frame=index, time_s=row["time_s"])
            observed["participants"][0].update(position_m=center,
                speed_mps=row["speed_mps"],
                velocity_mps=ego["velocity_xyz_mps"],
                body_vertices_m=ego["body_vertices_xyz_m"])
            events.append(event)
            graph = copy.deepcopy(example["graphs"][sample])
            graph["path"] = f"capture/native/graphs/base/{index:08d}.adapter.json"
            graph["attributes"].update(frame=index, time_s=row["time_s"])
            graph["attributes"]["observed_evidence"] = copy.deepcopy(observed)
            for node in graph["nodes"]:
                if node["id"] == "ego":
                    attrs = node["attributes"]
                    attrs.update(vertex=center, threedbbox=ego["body_vertices_xyz_m"],
                                 carla_speed=row["speed_mps"],
                                 carla_vel_x=ego["velocity_xyz_mps"][0],
                                 carla_vel_y=ego["velocity_xyz_mps"][1],
                                 carla_vel_z=ego["velocity_xyz_mps"][2],
                                 original_observation=copy.deepcopy(observed["participants"][0]))
            graphs.append(graph)
            native = copy.deepcopy(source_frames[sample])
            native.update(frame=index, simulation_time=row["time_s"],
                          adapter_graph=f"graphs/base/{index:08d}.adapter.json")
            frames.append(native)
        generated["trace.jsonl"] = "".join(json.dumps(row) + "\n" for row in trace)
        generated["road.xodr"] = generated["opendrive.txt"]
        generated["capture/evidence.jsonl"] = "".join(json.dumps(row) + "\n" for row in events)
        generated["capture/native/frames.jsonl"] = "".join(json.dumps(row) + "\n" for row in frames)
        for name in ("capture/native_map_facts.json", "capture/recorder_info.txt",
                     "fixture-provenance.json"):
            generated[name] = example["files"][name]
        capture_manifest = json.loads(example["files"]["capture/manifest.json"])
        capture_manifest.update(case_id=case_id, frames=len(trace),
                                source_run="c153046:synthetic-cpu-diagnostic")
        capture_manifest["sources"]["road.xodr"] = hashlib.sha256(generated["road.xodr"].encode()).hexdigest()
        capture_manifest["sources"]["trace.jsonl"] = hashlib.sha256(generated["trace.jsonl"].encode()).hexdigest()
        generated["capture/manifest.json"] = json.dumps(capture_manifest)
        note_path = folder / "diagnostic-source-note.json"
        note_path.write_text(json.dumps({
            "case_id": case_id,
            "kind": "synthetic_cpu_protocol",
            "original_native_acquisition": False,
            "physical_acceptance_claimed": False,
        }, indent=2) + "\n")
        specification = {
            "files": generated,
            "graphs": graphs,
            "videos": [{"path": name + ".mkv", "frames": 13,
                        "width": width, "height": height, "fps": 20, "color": color}
                       for name, width, height, color in CAMERAS],
        }
        spec_path = folder / "diagnostic.json"
        spec_path.write_text(json.dumps(specification, separators=(",", ":")) + "\n")
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": note_path.name,
                               "source": str(note_path.relative_to(REPO)),
                               "sha256": sha(note_path)}],
                  "generator": {"source": str(spec_path.relative_to(REPO)),
                                "sha256": sha(spec_path)}}
        (folder / "fixture-recipe.json").write_text(json.dumps(recipe, indent=2) + "\n")
        print("inventoried diagnostic source recipe", suffix)


if __name__ == "__main__":
    build()
