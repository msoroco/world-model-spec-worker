"""Build current source-hashed 480-frame speed diagnostic recipes."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NATIVE = HERE / "native"
SUFFIXES = ("below_80_mph", "inside_80_mph", "at_80_mph", "above_80_mph")
FILES = ("native_samples.jsonl", "trace.jsonl", "capture/evidence.jsonl",
         "video_frames.jsonl", "body_history.jsonl", "capture/native/frames.jsonl",
         "capture/manifest.json", "capture/recorder_info.txt", "context.json", "road.xodr")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def load_fixture():
    spec = importlib.util.spec_from_file_location("c111294_saved_fixture",
                                              HERE / "probe-saved-integration.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build() -> list[dict]:
    fixture = load_fixture()
    sys.path.insert(0, str(NATIVE))
    from cameras import camera_plan
    summary = []
    for suffix in SUFFIXES:
        with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work",
                                         prefix="c111294-recipe-") as temporary:
            attempt = Path(temporary) / "attempt"
            fixture.make_attempt(attempt, suffix)
            native = rows(attempt / "native_samples.jsonl")
            evidence = rows(attempt / "capture/evidence.jsonl")
            if len(native) != 480 or len(evidence) != 480 or (attempt / "channels").exists():
                raise ValueError("Raw speed fixture differs or supplies derived channels")
            graphs = []
            for sample, captured in zip(native, evidence):
                frame = sample["native_frame"]
                time_s = sample["time_s"]
                x, y, z = sample["ego_position_m"]
                ox, oy, oz = sample["other_position_m"]
                graphs.append({"path": f"capture/native/graphs/base/{frame:08d}.pkl",
                    "attributes": {"frame": frame, "simulation_time_s": time_s,
                                   "synthetic_diagnostic": True},
                    "nodes": [
                        {"id": "ego", "attributes": {"sem_class": "ego", "entity_id": 101,
                            "vertex": [x, y, z], "forward": [0, 1, 0],
                            "velocity": sample["ego_velocity_mps"],
                            "threedbbox": captured["ego"]["body_vertices_m"]}},
                        {"id": "other", "attributes": {"sem_class": "vehicle", "entity_id": 202,
                            "vertex": [ox, oy, oz], "forward": [0, -1, 0],
                            "velocity": [0, -10, 0],
                            "threedbbox": sample["other_body_vertices_m"]}}],
                    "edges": []})
            files = {name: (attempt / name).read_text() for name in FILES}
            files["acquisition-provenance.json"] = json.dumps({
                "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True}) + "\n"
            videos = [{"path": camera["name"] + ".mkv", "frames": 480,
                       "width": camera["width"], "height": camera["height"],
                       "fps": 20, "color": "black"} for camera in camera_plan()]
            diagnostic = HERE / f"update015-{suffix}-diagnostic.json"
            diagnostic.write_text(json.dumps({"files": files, "graphs": graphs,
                                             "videos": videos}, separators=(",", ":"),
                                            allow_nan=False) + "\n")
            if diagnostic.stat().st_size >= 2 * 1024 * 1024:
                raise ValueError("Speed diagnostic spec exceeds text return limit")
            relative = diagnostic.relative_to(ROOT).as_posix()
            digest = sha(diagnostic)
            recipe = {"format": "worker-fixture-recipe",
                      "sources": [{"path": "diagnostic-input.json", "source": relative,
                                   "sha256": digest}],
                      "generator": {"source": relative, "sha256": digest}}
            recipe_path = HERE / f"update015-{suffix}-recipe.json"
            recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
            summary.append({"suffix": suffix, "frames": 480,
                            "spec_bytes": diagnostic.stat().st_size,
                            "spec_sha256": digest, "recipe_sha256": sha(recipe_path)})
    (HERE / "update015-recipe-summary.json").write_text(json.dumps({
        "format": "c111294-update015-recipes", "synthetic_diagnostic": True,
        "selected": False, "cases": summary}, indent=2) + "\n")
    return summary


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
