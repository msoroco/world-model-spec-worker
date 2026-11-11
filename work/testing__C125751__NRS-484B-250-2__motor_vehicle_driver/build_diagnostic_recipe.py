"""Freeze original-source synthetic fixture text and four generated videos.

The saved-source proof must have been run first. No derived channels or results
are included; the finalizer must recreate them from the retained sources.
"""
import hashlib
import copy
import json
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
from worker_exchange.fixture_generator import generate, inspect

ATTEMPT = ROOT / ".runtime-work/c125751-two-signal-saved-source-55s-v3/operative"
SOURCE_NAMES = ("road_geometry.json", "crossing_history.jsonl", "signal_context.json",
                "signal_history.jsonl", "stop_context.json", "stop_history.jsonl",
                "video_frames.jsonl", "trace.jsonl",
                "head_visibility_review.json", "other_head_visibility_review.json")
VIDEO_SIZES = {"overview.mkv": (1920, 1080), "approach.mkv": (1280, 720),
               "reference_corner.mkv": (1280, 720), "driver_reference.mkv": (1280, 720)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(text):
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def _lines(items):
    return "".join(json.dumps(item, separators=(",", ":"), allow_nan=False) + "\n" for item in items)


def _body3(vertices):
    return [[x, y, z] for x, y in vertices for z in (0, 1.5)]


def converter_envelope(sources, trace, stops):
    """Make original-frame diagnostic converter inputs for every saved frame."""
    reference = json.loads((ROOT / "work/testing__C125714__NRS-484B-250-2__motor_vehicle_driver/diagnostic.json").read_text())
    reference_files = reference["files"]
    template = _rows(reference_files["capture/evidence.jsonl"])[0]
    crossings = _rows(sources["crossing_history.jsonl"])
    if len(crossings) != len(trace):
        raise ValueError("Crossing and trace counts differ")
    evidence, frames, graphs = [], [], []
    for row, stop, crossing in zip(trace, stops, crossings):
        frame, time_s = row["frame"], row["time_s"]
        if frame != crossing["frame"] or frame != stop["frame"]:
            raise ValueError("Original frame histories differ")
        ego = crossing["ego"]
        other = crossing["other"]
        speed = row["speed_mps"]
        row.update(speed_mph=speed / .44704, velocity_mps=[speed, 0, 0],
                   control={"throttle": 0, "steer": 0, "brake": 1 if speed == 0 else 0,
                            "hand_brake": False, "reverse": False})
        event = copy.deepcopy(template)
        event.update(original_frame=frame, replay_frame=frame,
                     recording_time_s=time_s, replay_simulation_time_s=time_s)
        event["ego"].update(position_m=row["position_m"], speed_mps=speed,
                            heading_deg=0, body_vertices_m=_body3(ego["body_vertices_xy_m"]))
        event["original_observations"].update(frame=frame, time_s=time_s)
        for actor, state, actor_id, heading in zip(
                event["original_observations"]["participants"], (ego, other), (101, 102), (0, 90)):
            actor.update(actor_id=actor_id, position_m=[*state["position_xy_m"], 0],
                         body_vertices_m=_body3(state["body_vertices_xy_m"]),
                         heading_deg=heading, speed_mps=stop["ego" if actor_id == 101 else "other"]["speed_mps"])
        evidence.append(event)
        base = f"graphs/base/{frame:08d}.pkl"
        abstract = f"graphs/abstract/{frame:08d}.pkl"
        frames.append({"frame": frame, "simulation_time": time_s, "base": base,
                       "abstract": abstract, "nodes": 0, "edges": 0,
                       "extraction_seconds": 0, "capture_seconds": 0})
        for graph_path in (base, abstract):
            attributes = {"frame": frame, "simulation_time_s": time_s,
                          "units": {"position": "m"}}
            if graph_path == base:
                attributes["observed_evidence"] = event["original_observations"]
            graphs.append({"path": "capture/native/" + graph_path,
                           "attributes": attributes,
                           "nodes": [], "edges": []})
    sources["trace.jsonl"] = _lines(trace)
    sources["capture/evidence.jsonl"] = _lines(evidence)
    sources["capture/native/frames.jsonl"] = _lines(frames)
    sources["capture/recorder_info.txt"] = reference_files["capture/recorder_info.txt"]
    sources["road.xodr"] = reference_files["road.xodr"]
    manifest = {"status": "draft", "acquisition": "synthetic_diagnostic",
                "case_id": "testing__C125751__NRS-484B-250-2__motor_vehicle_driver__signal_operative",
                "map": "Carla/Maps/OpenDriveMap", "frames": len(frames),
                "required_observations": [], "extraction_confirmed": True,
                "sources": {"road.xodr": hashlib.sha256(sources["road.xodr"].encode()).hexdigest(),
                            "trace.jsonl": hashlib.sha256(sources["trace.jsonl"].encode()).hexdigest()}}
    sources["capture/manifest.json"] = json.dumps(manifest, indent=2) + "\n"
    return graphs


def build():
    sources = {name: (ATTEMPT / name).read_text() for name in SOURCE_NAMES}
    trace = [json.loads(line) for line in sources["trace.jsonl"].splitlines() if line.strip()]
    stops = [json.loads(line) for line in sources["stop_history.jsonl"].splitlines() if line.strip()]
    if len(trace) != len(stops):
        raise ValueError("Diagnostic trace and speed histories differ")
    for row, stop in zip(trace, stops):
        x, y, z = row["position_m"]
        row["position"] = {"x": x, "y": y, "z": z}
        row["heading_deg"] = 0
        row["speed_mps"] = stop["ego"]["speed_mps"]
    graphs = converter_envelope(sources, trace, stops)
    spec = {"files": {}, "graphs": graphs,
            "videos": [{"path": name, "frames": 1100, "width": size[0],
                        "height": size[1], "fps": 20, "color": "black"}
                       for name, size in VIDEO_SIZES.items()]}
    inspect(spec)
    with tempfile.TemporaryDirectory(dir=ROOT / ".runtime-work") as temp:
        generated = Path(temp)
        generate(spec, generated)
        for role, camera in (("head_visibility_review.json", "approach.mkv"),
                             ("other_head_visibility_review.json", "reference_corner.mkv")):
            review = json.loads(sources[role])
            review["source_video_sha256"] = sha(generated / camera)
            sources[role] = json.dumps(review, indent=2) + "\n"
    source_dir = HERE / "diagnostic-sources"
    source_dir.mkdir(exist_ok=True)
    items = []
    for name, content in sorted(sources.items()):
        path = source_dir / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        items.append({"path": name, "source": str(path.relative_to(ROOT)), "sha256": sha(path)})
    path = HERE / "diagnostic.json"
    path.write_text(json.dumps(spec, separators=(",", ":")) + "\n")
    if path.stat().st_size > 2 * 1024 * 1024:
        raise ValueError("Diagnostic source spec exceeds worker file size limit")
    relative = str(path.relative_to(ROOT))
    recipe = {"format": "worker-fixture-recipe",
              "sources": items + [{"path": "diagnostic-input.json", "source": relative, "sha256": sha(path)}],
              "generator": {"source": relative, "sha256": sha(path)}}
    (HERE / "diagnostic-recipe.json").write_text(json.dumps(recipe, indent=2) + "\n")
    return {"source_spec": relative, "size_bytes": path.stat().st_size,
            "source_sha256": sha(path), "recipe_sha256": sha(HERE / "diagnostic-recipe.json")}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
