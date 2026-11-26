"""Build law-specific synthetic projection packets for CPU compatibility only.

The shipped graph fixture exercises the Native/Core plumbing. Its speed content
is not a measurement of this law. Projection observations are independently
generated here for each exact case and never represented as original evidence.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from projection_construction import CASES
from projection_measurement import ASSIGNMENT
from projection_sources import CAMERAS

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def outline(y, actor):
    return {"category": actor, "source_actor_id": "synthetic-" + actor,
            "outline_vertices_m": [[100.0, y - 1], [102.0, y - 1],
                                   [102.0, y], [100.0, y]]}


def build():
    base = json.loads((REPO / "runtime/fixtures/example.json").read_text(encoding="utf-8"))
    frames = [json.loads(line) for line in base["files"]["video_frames.jsonl"].splitlines()]
    for case in CASES:
        fixture = {"files": dict(base["files"]), "graphs": base["graphs"],
                   "videos": base["videos"]}
        fixture["files"]["diagnostic-source-note.json"] = json.dumps({
            "source_kind": "synthetic_diagnostic_fixture", "accepted_original_source": False,
            "case_id": case.case_id, "source": "CPU-only projection geometry and generic Core fixture"}) + "\n"
        parts = [outline(case.projection_m if case.controlling_part == "vehicle" else 4.2,
                         "vehicle")]
        if case.controlling_part in ("load", "trailer"):
            parts.append(outline(case.projection_m, case.controlling_part))
        history = []
        cameras = []
        for index, frame in enumerate(frames):
            identity = frame["carla_frame"]
            history.append({"assignment_id": ASSIGNMENT, "case_id": case.case_id,
                "frame": identity, "time_s": frame["time_s"],
                "original_trace_id": "synthetic-c150088-" + case.suffix,
                "curb_segment_start_m": [80.0, 0.0],
                "curb_segment_end_m": [130.0, 0.0],
                "street_side_reference_m": [80.0, 8.0],
                "physical_parts": parts})
            cameras.append({"frame_index": index, "native_frame": identity,
                            "time_s": frame["time_s"],
                            "camera_frames": {name: identity for name in CAMERAS}})
        fixture["files"]["original-projection-history.jsonl"] = "".join(
            json.dumps(row, sort_keys=True) + "\n" for row in history)
        fixture["files"]["camera-frame-map.jsonl"] = "".join(
            json.dumps(row, sort_keys=True) + "\n" for row in cameras)
        folder = ROOT / "diagnostics" / case.suffix
        folder.mkdir(parents=True, exist_ok=True)
        spec = folder / "diagnostic.json"
        spec.write_text(json.dumps(fixture, separators=(",", ":")) + "\n", encoding="utf-8")
        source = str(spec.relative_to(REPO))
        digest = hashlib.sha256(spec.read_bytes()).hexdigest()
        recipe = {"format": "worker-fixture-recipe",
                  "sources": [{"path": "diagnostic-input.json", "source": source, "sha256": digest}],
                  "generator": {"source": source, "sha256": digest}}
        (folder / "fixture-recipe.json").write_text(json.dumps(recipe, indent=2) + "\n", encoding="utf-8")
        print(case.case_id, spec.stat().st_size)


if __name__ == "__main__":
    build()
