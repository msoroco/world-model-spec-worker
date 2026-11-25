"""Rebuild current selected crosswalk diagnostics at full 900-frame duration."""

import copy
import hashlib
import json
import shutil
from pathlib import Path


REPO = Path(__file__).resolve().parents[3]
PACKAGE = Path(__file__).resolve().parents[1]
STAGE = REPO / ".runtime-work/c215286-current-full-stage"
STAGED_PACKAGE = STAGE / "work" / PACKAGE.name


def rows(files, name):
    return [json.loads(line) for line in files[name].splitlines() if line.strip()]


def write_rows(files, name, items):
    files[name] = "".join(json.dumps(item, separators=(",", ":")) + "\n" for item in items)


def build(kind):
    if kind not in ("over", "short"):
        raise ValueError("Choose over or short")
    STAGED_PACKAGE.parent.mkdir(parents=True, exist_ok=True)
    if not STAGED_PACKAGE.exists():
        shutil.copytree(PACKAGE, STAGED_PACKAGE, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    (STAGE / ".runtime-work").mkdir(exist_ok=True)
    relative = "diagnostic.json" if kind == "over" else "cases/reverse_stops_before_crosswalk-diagnostic.json"
    recipe_relative = "diagnostic-recipe.json" if kind == "over" else "cases/reverse_stops_before_crosswalk-recipe.json"
    spec = json.loads((PACKAGE / relative).read_text())
    files = spec["files"]
    names = ["reverse_history.jsonl", "video_frames.jsonl", "trace.jsonl",
             "capture/evidence.jsonl", "capture/native/frames.jsonl"]
    base = {name: rows(files, name) for name in names}
    for name, items in base.items():
        for index in range(len(items), 900):
            row = copy.deepcopy(items[-1])
            frame = 100 + index
            time_s = round((index + 1) / 20, 9)
            if name == "reverse_history.jsonl":
                row.update(frame=frame, time_s=time_s, velocity_mps=[0, 0])
            elif name == "video_frames.jsonl":
                row.update(video_frame=index, carla_frame=frame, native_frame=frame, time_s=time_s)
            elif name == "trace.jsonl":
                row.update(frame=frame, time_s=time_s, speed_mps=0,
                           velocity_mps=[0, 0, 0], speed_mph=0)
            elif name == "capture/evidence.jsonl":
                row.update(original_frame=frame, replay_frame=frame, recording_time_s=time_s,
                           replay_simulation_time_s=time_s)
                row["ego"]["speed_mps"] = 0
                observation = row["original_observations"]
                observation.update(frame=frame, time_s=time_s)
                observation["participants"][0].update(speed_mps=0, velocity_mps=[0, 0, 0])
            else:
                graph = f"{frame:08d}.adapter.json"
                row.update(frame=frame, simulation_time=time_s,
                           base=f"graphs/base/{graph}", abstract=f"graphs/abstract/{graph}",
                           adapter_graph=f"graphs/base/{graph}")
            items.append(row)
        write_rows(files, name, items)
    original_graphs = copy.deepcopy(spec["graphs"][-2:])
    for index in range(9, 900):
        frame = 100 + index
        time_s = round((index + 1) / 20, 9)
        for original in original_graphs:
            graph = copy.deepcopy(original)
            level = "base" if "/base/" in graph["path"] else "abstract"
            graph["path"] = f"capture/native/graphs/{level}/{frame:08d}.adapter.json"
            graph["attributes"].update(frame=frame, simulation_time_s=time_s)
            observation = graph["attributes"]["observed_evidence"]
            observation.update(frame=frame, time_s=time_s)
            observation["participants"][0].update(speed_mps=0, velocity_mps=[0, 0, 0])
            spec["graphs"].append(graph)
    for video in spec["videos"]:
        video["frames"] = 900
    capture_manifest = json.loads(files["capture/manifest.json"])
    capture_manifest["frames"] = 900
    capture_manifest["sources"]["trace.jsonl"] = hashlib.sha256(files["trace.jsonl"].encode()).hexdigest()
    files["capture/manifest.json"] = json.dumps(capture_manifest, indent=2) + "\n"
    target = STAGED_PACKAGE / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(spec, separators=(",", ":")) + "\n")
    checksum = hashlib.sha256(target.read_bytes()).hexdigest()
    recipe_path = STAGED_PACKAGE / recipe_relative
    recipe = json.loads(recipe_path.read_text())
    recipe["sources"][0]["sha256"] = checksum
    recipe["generator"]["sha256"] = checksum
    recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
    print(json.dumps({"kind": kind, "stage": str(STAGE), "spec_sha256": checksum,
                      "spec_bytes": target.stat().st_size, "graphs": len(spec["graphs"]),
                      "frames": len(base["trace.jsonl"])}))


if __name__ == "__main__":
    for selected in ("over", "short"):
        build(selected)
