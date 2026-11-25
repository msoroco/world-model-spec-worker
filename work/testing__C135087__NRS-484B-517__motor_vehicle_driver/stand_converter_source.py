"""Fail-closed audit of the original Native converter packet.

The adapter exports this packet from the same live run as the actor and camera
sources. This audit checks source identity and shape; it cannot decide whether
the stand sign is adequate or whether loading is expeditious.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from stand import SourceError


REQUIRED = ("road.xodr", "trace.jsonl", "capture/manifest.json",
            "capture/native_map_facts.json", "capture/recorder_info.txt",
            "capture/evidence.jsonl", "capture/native/frames.jsonl")


def _source(root, name):
    path = root / name
    if path.is_symlink() or not path.is_file() or not path.stat().st_size:
        raise SourceError("missing original converter source: " + name)
    if root not in path.resolve().parents:
        raise SourceError("converter source escapes attempt: " + name)
    return path


def _sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(path):
    try:
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    except (UnicodeError, ValueError) as error:
        raise SourceError("invalid original converter rows: " + path.name) from error


def audit(output, attempt):
    root = Path(output).resolve()
    sources = {name: _sha(_source(root, name)) for name in REQUIRED}
    try:
        manifest = json.loads((root / "capture/manifest.json").read_text(encoding="utf-8"))
    except (UnicodeError, ValueError) as error:
        raise SourceError("invalid original capture manifest") from error
    if (manifest.get("acquisition") != "original_live_run" or
            manifest.get("diagnostic_fixture") is not False or
            manifest.get("extraction_confirmed") is not True or
            manifest.get("frames") != 900):
        raise SourceError("converter packet lacks physical original-run declaration")
    if any(manifest.get("sources", {}).get(name) != sources[name]
           for name in ("road.xodr", "trace.jsonl")):
        raise SourceError("converter source manifest hash mismatch")
    native = manifest.get("native_map_facts", {})
    if (native.get("path") != "native_map_facts.json" or
            native.get("sha256") != sources["capture/native_map_facts.json"]):
        raise SourceError("original Native map facts are unbound")
    evidence = _rows(root / "capture/evidence.jsonl")
    frames = _rows(root / "capture/native/frames.jsonl")
    trace = _rows(root / "trace.jsonl")
    actor_rows = json.loads(_source(root, "actor-rows.json").read_text(encoding="utf-8"))
    frame_map = json.loads(_source(root, "frame-map.json").read_text(encoding="utf-8"))
    if any(len(rows) != 900 for rows in (evidence, frames, trace, actor_rows, frame_map)):
        raise SourceError("original converter packet lost a frame")
    graphs = {}
    for index, (event, frame, motion, actor, mapped) in enumerate(
            zip(evidence, frames, trace, actor_rows, frame_map)):
        number = attempt["first_frame"] + index
        stamps = (event.get("recording_time_s"), event.get("replay_simulation_time_s"),
                  frame.get("simulation_time"), motion.get("time_s"),
                  actor.get("time_s"), mapped.get("time_s"))
        if (event.get("original_frame") != number or event.get("replay_frame") != number or
                frame.get("frame") != number or motion.get("frame") != number or
                actor.get("frame") != number or mapped.get("frame") != number or
                any(type(value) not in (int, float) for value in stamps) or
                max(stamps) - min(stamps) > 1e-4):
            raise SourceError("original converter and actor frame/time join differs")
        relative = frame.get("adapter_graph")
        if not isinstance(relative, str) or not relative.startswith("graphs/"):
            raise SourceError("original Native graph reference missing")
        graph = _source(root, "capture/native/" + relative)
        if graph.suffix != ".json" or graph in graphs:
            raise SourceError("duplicate or unsupported original Native graph")
        graphs[graph] = _sha(graph)
        observations = event.get("original_observations", {})
        if not isinstance(observations.get("participants"), list):
            raise SourceError("original participant inventory missing")
        observed_ids = {item.get("actor_id") for item in observations["participants"]
                        if isinstance(item, dict)}
        if not {attempt["entrant_id"], attempt["passenger_id"]} <= observed_ids:
            raise SourceError("entrant or passenger absent from original participant inventory")
        if event.get("actor_id") != attempt["subject_id"]:
            raise SourceError("original subject identity differs from actor capture")
        if not isinstance(observations.get("rgb_sensors"), list) or not observations["rgb_sensors"]:
            raise SourceError("original RGB sensor inventory missing")
    return {"format": "c135087-native-converter-source-audit-v1", "case_id": attempt["case_id"],
            "frames": 900, "source_sha256": sources,
            "graph_count": len(graphs), "graph_sha256": {str(path.relative_to(root)): digest
                                                     for path, digest in graphs.items()},
            "scope": "Original packet integrity only; physical pixels and legal judgments unreviewed"}
