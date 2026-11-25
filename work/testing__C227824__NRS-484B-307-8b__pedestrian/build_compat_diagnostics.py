"""Build six hash-bound, explicitly synthetic compatibility fixtures."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

from build_construction import ROOT
from prove_saved_synthetic import _update_attempt

sys.path.insert(0, str(ROOT / "tests"))
from test_saved_entry import make_attempt, MODULE as saved_module


REPO = ROOT.parents[1]
PRIVATE = REPO / ".runtime-work" / "c227824-compat-build"
SIZES = {"overview": (1920, 1080), "approach": (1280, 720),
         "reference_corner": (1280, 720), "driver_reference": (1280, 720)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def media():
    output = PRIVATE / "media"
    output.mkdir(parents=True, exist_ok=True)
    videos = []
    for name in saved_module.CAMERAS:
        width, height = SIZES[name]
        spec = {"path": name + ".mkv", "frames": 3, "width": width,
                "height": height, "fps": 20, "color": "black"}
        target = output / spec["path"]
        if target.exists():
            target.unlink()
        subprocess.run(["ffmpeg", "-nostdin", "-hide_banner", "-loglevel", "error", "-n",
                        "-f", "lavfi", "-i", f"color=c=black:s={width}x{height}:r=20",
                        "-frames:v", "3", "-an", "-c:v", "ffv1", "-threads", "1",
                        "-fflags", "+bitexact", "-flags:v", "+bitexact", str(target)],
                       check=True, timeout=120)
        videos.append(spec)
    return videos


def main():
    PRIVATE.mkdir(parents=True, exist_ok=True)
    videos = media()
    template_path = REPO / "work" / "testing__C109171__NRS-484B-307-4b__pedestrian" / "cases" / "arrow_walk_wait" / "diagnostic.json"
    template = json.loads(template_path.read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    selected = {row["case_id"]: row for row in
                json.loads((ROOT / "selected-constructions.json").read_text())["cases"]}
    entries = []
    for case in plan["cases"]:
        case_id = case["case_id"]
        suffix = case_id[len(ROOT.name) + 2:]
        source = PRIVATE / suffix
        if source.exists():
            shutil.rmtree(source)
        source.mkdir()
        make_attempt(source)
        _update_attempt(source, case)
        acquisition_path = source / "acquisition.json"
        acquisition = json.loads(acquisition_path.read_text())
        for video in videos:
            acquisition[video["path"]]["sha256"] = sha(PRIVATE / "media" / video["path"])
        write(acquisition_path, acquisition)
        files = {p.name: p.read_text() for p in source.iterdir()
                 if p.is_file() and p.suffix in (".json", ".jsonl")
                 and p.name not in ("construction.json", "config.json")}
        mapping = [json.loads(line) for line in files["video_frames.jsonl"].splitlines()]
        trace = []
        evidence = []
        frames = []
        graphs = []
        for row in mapping:
            frame, when = row["carla_frame"], row["time_s"]
            x = float(frame - 1) if case["entry_request"] == "entry" else 0.0
            trace.append({"frame": frame, "time_s": when,
                          "position": {"x": x, "y": 0.0, "z": 0.0},
                          "position_m": [x, 0.0, 0.0], "heading_deg": 0.0,
                          "speed_mps": 1.0 if x else 0.0,
                          "velocity_mps": [1.0 if x else 0.0, 0.0, 0.0],
                          "speed_mph": 1.0 / .44704 if x else 0.0, "control": {}})
            observed = {"frame": frame, "time_s": when,
                        "participants": [], "map_context": {"diagnostic_fixture": True}}
            original = json.loads(template["files"]["capture/evidence.jsonl"].splitlines()[0])
            original["original_frame"] = frame
            original["replay_frame"] = frame
            original["recording_time_s"] = when
            original["replay_simulation_time_s"] = when
            original["original_observations"] = observed
            original["ego"]["position_m"] = [x, 0.0, 0.0]
            original["ego"]["speed_mps"] = 1.0 if x else 0.0
            evidence.append(original)
            graph = json.loads(json.dumps(template["graphs"][0]))
            graph["path"] = f"capture/native/graphs/base/{frame:08d}.adapter.json"
            graph["attributes"] = {"frame": frame, "time_s": when,
                                   "observed_evidence": observed}
            graphs.append(graph)
            frames.append({"adapter_graph": f"graphs/base/{frame:08d}.adapter.json",
                           "frame": frame, "simulation_time": when})
        files["trace.jsonl"] = "".join(json.dumps(row, sort_keys=True) + "\n" for row in trace)
        files["capture/evidence.jsonl"] = "".join(json.dumps(row, sort_keys=True) + "\n" for row in evidence)
        files["capture/native/frames.jsonl"] = "".join(json.dumps(row, sort_keys=True) + "\n" for row in frames)
        files["capture/recorder_info.txt"] = template["files"]["capture/recorder_info.txt"]
        map_path = ROOT / "candidate-corridor.xodr"
        files["capture/manifest.json"] = json.dumps({"acquisition": "synthetic_fixture",
                                                      "case_id": case_id,
                                                      "diagnostic_fixture": True,
                                                      "extraction_confirmed": True,
                                                      "frames": 3,
                                                      "sources": {"road.xodr": sha(map_path),
                                                                  "trace.jsonl": hashlib.sha256(files["trace.jsonl"].encode()).hexdigest()}},
                                                     sort_keys=True) + "\n"
        target = ROOT / "cases" / suffix
        generator = target / "diagnostic.json"
        write(generator, {"files": files, "graphs": graphs, "videos": videos})
        recipe = target / "fixture-recipe.json"
        write(recipe, {"format": "worker-fixture-recipe",
                       "sources": [{"path": "road.xodr",
                                    "source": str(map_path.relative_to(REPO)),
                                    "sha256": sha(map_path)}],
                       "generator": {"source": str(generator.relative_to(REPO)),
                                     "sha256": sha(generator)}})
        constructed = ROOT / selected[case_id]["construction"]
        if sha(constructed) != selected[case_id]["construction_sha256"]:
            raise ValueError("selected construction changed: " + case_id)
        entries.append({"case_id": case_id, "kind": "delivery",
                        "construction": selected[case_id]["construction"],
                        "construction_sha256": sha(constructed),
                        "measurement_contract": f"cases/{suffix}/measurement-contract.json",
                        "measurement_procedure": {"entrypoint": "analysis.py"},
                        "fixture_recipe": str(recipe.relative_to(REPO)),
                        "proof_status": "synthetic_compatibility_pending_reviewed_source"})
    manifest = ROOT / "execution-manifest.draft.json"
    write(manifest, {"format": "worker-execution-manifest",
                     "assignment_id": ROOT.name,
                     "runtime_manifest_sha256": sha(REPO / "runtime" / "SOURCE-MANIFEST.json"),
                     "status": "draft", "cases": entries})
    print(json.dumps({"cases": len(entries), "manifest": str(manifest.relative_to(REPO)),
                      "status": "draft", "synthetic_video_frames": 3}, indent=2))


if __name__ == "__main__":
    main()
