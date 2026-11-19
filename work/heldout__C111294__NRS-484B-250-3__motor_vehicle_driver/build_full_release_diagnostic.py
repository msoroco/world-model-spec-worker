"""Expand the three synthetic release diagnostics to complete original windows.

This builds CPU diagnostic specifications only. It does not replay or acquire a
CARLA recording. The output remains under .runtime-work until pinned exact
compatibility proves that every source channel is consistent.
"""

import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from build_release_window import DELAYS, FRAME_COUNT, HERE, build


def compact(rows):
    return "".join(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n"
                   for row in rows)


def expand(output):
    output = Path(output)
    source_root = output / "originals"
    build(source_root)
    baseline = json.loads((HERE / "diagnostic-yield-sweep-0000.json").read_text())
    baseline_files = baseline["files"]
    summaries = []
    # The frozen selected constructions order their later points as 160, 80.
    # Read that order explicitly so source motion follows each exact case's
    # controller setpoint rather than the helper's numerical sweep order.
    source_ranks = (0, 2, 1)
    for rank, source_rank in enumerate(source_ranks):
        delay = DELAYS[source_rank]
        short = f"yield_release_delay-{rank:04d}"
        original = source_root / f"yield_release_delay-{source_rank:04d}"
        source = json.loads((HERE / f"diagnostic-yield-sweep-{rank:04d}.json").read_text())
        selected = next(entry for entry in json.loads((HERE / "execution-manifest.json").read_text())["cases"]
                        if entry["case_id"].endswith("__" + short))
        construction = json.loads((HERE / selected["construction"]).read_text())
        config = json.loads(next(item["content"] for item in construction["files"]
                                 if item["path"] == "config.json"))
        if config.get("release_delay_frames") != delay:
            raise ValueError("Diagnostic release delay differs from selected construction")
        rows = [json.loads(line) for line in (original / "intersection_participants.jsonl").read_text().splitlines()]
        frames = [json.loads(line) for line in (original / "video_frames.jsonl").read_text().splitlines()]
        trace_join = [json.loads(line) for line in (original / "trace.jsonl").read_text().splitlines()]
        if len(rows) != FRAME_COUNT or len(frames) != FRAME_COUNT or len(trace_join) != FRAME_COUNT:
            raise ValueError("Full original release window is incomplete")
        for name in ("intersection_topology.json", "intersection_participants.jsonl",
                     "video_frames.jsonl", "trace.jsonl"):
            source["files"][name] = (original / name).read_text()

        seed_motion = [json.loads(line) for line in baseline_files["trace.jsonl"].splitlines()][:9]
        seed_evidence = [json.loads(line) for line in baseline_files["capture/evidence.jsonl"].splitlines()][:9]
        seed_native = [json.loads(line) for line in baseline_files["capture/native/frames.jsonl"].splitlines()][:9]
        if any(len(seed) != 9 for seed in (seed_motion, seed_evidence, seed_native)):
            raise ValueError("Expected nine baseline source-shaped seed frames")
        motion, evidence, native = [], [], []
        for index, (participant, mapping) in enumerate(zip(rows, frames)):
            frame, time_s = mapping["carla_frame"], mapping["time_s"]
            seed_index = min(8, max(0, index - delay))
            motion_row = deepcopy(seed_motion[seed_index])
            motion_row.update(frame=frame, time_s=time_s)
            motion.append(motion_row)
            event = deepcopy(seed_evidence[seed_index])
            event.update(original_frame=frame, replay_frame=frame,
                         recording_time_s=time_s,
                         replay_simulation_time_s=time_s + 13.517531131161377)
            observed = event["original_observations"]
            observed.update(frame=frame, time_s=time_s)
            # Retain sensor identity and mount while excluding camera tuning
            # defaults that do not vary over the original tick window.
            observed["rgb_sensors"] = [
                {key: sensor[key] for key in ("actor_id", "blueprint") if key in sensor}
                for sensor in observed.get("rgb_sensors", [])
            ]
            for actor in observed.get("participants", []):
                actor.pop("blueprint_attributes", None)
                actor.pop("light_attributes", None)
            evidence.append(event)
            native_row = deepcopy(seed_native[seed_index])
            native_row.update(frame=frame, simulation_time=event["replay_simulation_time_s"],
                              abstract=f"graphs/abstract/{frame:08d}.pkl",
                              base=f"graphs/base/{frame:08d}.pkl")
            native.append(native_row)
            if participant["frame"] != frame or trace_join[index]["frame"] != frame:
                raise ValueError("Original release frame join differs")
        for name in ("speed_samples.jsonl", "body_history.jsonl"):
            source["files"].pop(name, None)
        source["files"]["trace.jsonl"] = compact(motion)
        for name, value in (("capture/evidence.jsonl", evidence),
                            ("capture/native/frames.jsonl", native)):
            source["files"][name] = compact(value)
        manifest = json.loads(source["files"]["capture/manifest.json"])
        manifest["frames"] = FRAME_COUNT
        manifest["sources"]["trace.jsonl"] = sha256(source["files"]["trace.jsonl"].encode()).hexdigest()
        source["files"]["capture/manifest.json"] = json.dumps(manifest, separators=(",", ":"))
        # The map is retained in road.xodr. For each tick, the source-shaped
        # graph carries that tick's original observation packet; it cannot be
        # replaced by a stale nine-frame graph from the seed diagnostic.
        graphs = []
        for event in evidence:
            frame = event["original_frame"]
            for kind in ("abstract", "base"):
                attributes = {"frame": frame}
                if kind == "base":
                    attributes.update(simulation_time_s=event["replay_simulation_time_s"],
                                      observed_evidence=event["original_observations"])
                graphs.append({"path": f"capture/native/graphs/{kind}/{frame:08d}.pkl",
                               "attributes": attributes, "nodes": [], "edges": []})
        source["graphs"] = graphs
        for video in source["videos"]:
            video["frames"] = FRAME_COUNT
        destination = output / f"{short}-candidate.json"
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(source, separators=(",", ":")) + "\n")
        summaries.append({"case": short, "release_delay_frames": delay,
                          "frames": FRAME_COUNT,
                          "graph_packets": len(source["graphs"]),
                          "bytes": destination.stat().st_size,
                          "source_sha256": sha256(destination.read_bytes()).hexdigest()})
    return summaries


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    print(json.dumps(expand(args.output), indent=2))


if __name__ == "__main__":
    main()
