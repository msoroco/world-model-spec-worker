"""Create exact synthetic saved-source diagnostics; never physical evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build() -> None:
    plan = json.loads((HERE / "case-plan.json").read_text(encoding="utf-8"))
    example = json.loads((ROOT / "runtime/fixtures/example.json").read_text(encoding="utf-8"))
    for case in plan["cases"]:
        short = case["case_id"].split("__")[-1]
        folder = HERE / "cases" / short
        diagnostic = json.loads(json.dumps(example))
        files = diagnostic["files"]
        capture = json.loads(files["capture/manifest.json"])
        capture["case_id"] = case["case_id"]
        files["capture/manifest.json"] = json.dumps(capture, sort_keys=True) + "\n"
        mapping = [json.loads(line) for line in files["video_frames.jsonl"].splitlines()]
        east = case["approach_direction"] == "east"
        left = case["pedestrian_highway_side"] == "left"
        y = -4.5 if east == left else 4.5
        rows = []
        for index, mapped in enumerate(mapping):
            px = 20.0 - index if east else -20.0 + index
            vx = -30.0 + index if east else 30.0 - index
            rows.append({"frame": mapped["carla_frame"], "time_s": mapped["time_s"],
                         "pedestrian_xyz_m": [px, y, 0.0], "vehicle_xyz_m": [vx, 0.0, 0.0],
                         "pedestrian_forward_xy": [-1.0, 0.0] if east else [1.0, 0.0],
                         "vehicle_forward_xy": [1.0, 0.0] if east else [-1.0, 0.0],
                         "observation_source": "synthetic_diagnostic"})
        packet = {"assignment_id": HERE.name, "case_id": case["case_id"],
                  "diagnostic_fixture": True, "original_trace_id": "synthetic-diagnostic-trace",
                  "site_source_sha256": sha(b"synthetic-site-packet"),
                  "site": {"reviewed_public_highway": True, "reviewed_sidewalk_absent": True,
                           "reviewed_subsection_6_inapplicable": True,
                           "centerline_xy_m": [[-30.0, 0.0], [30.0, 0.0]],
                           "fixture_only": True}, "frames": rows}
        source = json.dumps(packet, sort_keys=True) + "\n"
        files["original-walking-observations.json"] = source
        files["original-walking-receipt.json"] = json.dumps({"case_id": case["case_id"],
            "fps": 20, "frame_count": len(rows), "diagnostic_fixture": True,
            "source_sha256": sha(source.encode())}, sort_keys=True) + "\n"
        files["fixture-provenance.json"] = json.dumps({"case_id": case["case_id"],
            "scope": "Synthetic 9-frame walking software diagnostic, not original public highway or legal evidence"}, sort_keys=True) + "\n"
        path = folder / "diagnostic.json"
        path.write_text(json.dumps(diagnostic, separators=(",", ":")) + "\n", encoding="utf-8")
        rel = str(path.relative_to(ROOT))
        write(folder / "fixture-recipe.json", {"format": "worker-fixture-recipe",
            "sources": [{"path": "diagnostic-input.json", "source": rel,
                         "sha256": sha(path.read_bytes())}],
            "generator": {"source": rel, "sha256": sha(path.read_bytes())}})


if __name__ == "__main__":
    build()
