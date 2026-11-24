"""Author one marked, source-shaped CPU fixture for unmarked-pass analysis.

All actor positions and video colors are diagnostic data. The fixture cannot
serve as an original capture or establish visibility or legal status.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace

from crosswalk_measurements import ASSIGNMENT_ID
from native_crosswalk_capture import CAMERAS, FRAME_COUNT, NativeCrosswalkRecorder

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
CASE = ASSIGNMENT_ID + "__unmarked_pass"
ACTORS = {"ego": "diagnostic-ego", "lead": "diagnostic-lead", "pedestrian": "diagnostic-walker"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _vertices(x: float) -> list[list[float]]:
    return [[x + dx, y, z] for dx in (-1.0, 1.0)
            for y in (-0.5, 0.5) for z in (0.0, 1.0)]


def build() -> dict:
    scratch = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    if not scratch.is_relative_to(REPO / ".runtime-work"):
        raise ValueError("fixture scratch must be under .runtime-work")
    scratch.mkdir(parents=True, exist_ok=True)
    output = HERE / "diagnostic_sources" / "unmarked_pass"
    output.mkdir(parents=True, exist_ok=True)
    context = {
        "case_id": CASE, "map_sha256": "0" * 64,
        "layout": "intersection", "junction_kind": "road_intersection",
        "crosswalk": {"kind": "unmarked", "polygon": [[6.0, -2.0], [8.0, -2.0],
                                                        [8.0, 2.0], [6.0, 2.0]],
                      "opposite_sidewalk_lateral_lines": "diagnostic/sidewalk",
                      "curb_or_traveled_edge_sources": "diagnostic/curb"},
        "stopped_vehicle_purpose": {"claim": "permit_pedestrian",
                                    "source_ref": "diagnostic/independent-purpose"},
        "ego_vehicle_identity": ACTORS["ego"],
        "lead_vehicle_identity": ACTORS["lead"],
        "pedestrian_identity": ACTORS["pedestrian"],
        "road_axis": {"origin": [0.0, 0.0], "forward": [1.0, 0.0]},
        "source_scope": "diagnostic_software_fixture",
    }
    recorder = NativeCrosswalkRecorder(case_id=CASE, context=context, actor_ids=ACTORS)
    for index in range(FRAME_COUNT):
        frame = 40 + index
        x = index / 10.0
        actors = {
            "ego": {"actor_id": ACTORS["ego"], "center": [x, 0.0],
                    "vertices": _vertices(x), "speed_mps": 3.0,
                    "source_ref": f"diagnostic/ego/frame/{frame}"},
            "lead": {"actor_id": ACTORS["lead"], "center": [5.0, 0.0],
                     "vertices": _vertices(5.0), "speed_mps": 0.0,
                     "source_ref": f"diagnostic/lead/frame/{frame}"},
            "pedestrian": {"actor_id": ACTORS["pedestrian"], "center": [7.0, 0.0],
                           "source_ref": f"diagnostic/walker/frame/{frame}"},
        }
        recorder.append(world_frame=frame, actors=actors,
                        camera_frames={name: SimpleNamespace(frame=frame) for name in CAMERAS})
    with tempfile.TemporaryDirectory(dir=scratch, prefix="crosswalk-source-") as temporary:
        staged = Path(temporary)
        recorder.write(staged)
        receipt_path = staged / "receipt.json"
        receipt = json.loads(receipt_path.read_text())
        receipt["diagnostic_fixture"] = True
        receipt["source_scope"] = "diagnostic_software_fixture"
        receipt_path.write_text(json.dumps(receipt, sort_keys=True) + "\n")
        for name in ("context.json", "trace.jsonl", "frame-map.jsonl", "receipt.json"):
            (staged / name).replace(output / name)
    (output / "video_frames.jsonl").write_bytes((output / "frame-map.jsonl").read_bytes())
    spec = {
        "files": {}, "graphs": [],
        "videos": [{"path": name + ".mkv", "frames": 900,
                    "width": 1920 if name == "overview" else 1280,
                    "height": 1080 if name == "overview" else 720,
                    "fps": 20, "color": "black"} for name in CAMERAS],
    }
    spec_path = HERE / "diagnostic-unmarked_pass.json"
    spec_path.write_text(json.dumps(spec, indent=2) + "\n")
    sources = []
    for name in ("context.json", "trace.jsonl", "frame-map.jsonl", "receipt.json", "video_frames.jsonl"):
        path = output / name
        sources.append({"path": name, "source": str(path.relative_to(REPO)),
                        "sha256": _sha(path)})
    recipe = {"format": "worker-fixture-recipe", "sources": sources,
              "generator": {"source": str(spec_path.relative_to(REPO)),
                            "sha256": _sha(spec_path)}}
    recipe_path = HERE / "fixture-recipe-unmarked_pass.json"
    recipe_path.write_text(json.dumps(recipe, indent=2) + "\n")
    return {"case_id": CASE, "recipe": recipe_path.name,
            "recipe_sha256": _sha(recipe_path),
            "sources": {item["path"]: item["sha256"] for item in sources},
            "source_scope": "diagnostic_software_fixture"}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
