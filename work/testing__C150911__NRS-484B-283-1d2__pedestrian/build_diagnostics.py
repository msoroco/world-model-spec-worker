"""Build source-specific nine-frame textual software fixtures, never physical evidence."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
EXAMPLE = ROOT / "runtime/fixtures/example.json"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def site() -> dict:
    value = {"cell_id": "C150911", "actor": "pedestrian",
        "layout": "one_way_road", "highway_public_vehicular_access": True,
        "signal_facing_pedestrian": True, "signal_facing_direction": "both",
        "highway_polygon_xy": [[-1, -1], [1, -1], [1, 1], [-1, 1]],
        "crossing_routes": {
            "forward": {"source_sha256": sha(b"synthetic-forward"),
                "waypoints_xy": [[-2, 0], [0, 0], [2, 0]]},
            "reverse": {"source_sha256": sha(b"synthetic-reverse"),
                "waypoints_xy": [[2, 0], [0, 0], [-2, 0]]}}}
    for name in ("opendrive", "highway", "crossing", "sidewalk", "signal",
                 "signal_facing", "one_way_direction", "exception_context"):
        value[name + "_source_sha256"] = sha(("synthetic-" + name).encode())
    return value


def build() -> None:
    plan = json.loads((HERE / "case-plan.json").read_text())
    example = json.loads(EXAMPLE.read_text())
    for case in plan["cases"]:
        cid = case["case_id"]
        folder = HERE / "cases" / cid.split("__")[-1]
        diagnostic = json.loads(json.dumps(example))
        files = diagnostic["files"]
        capture = json.loads(files["capture/manifest.json"])
        capture["case_id"] = cid
        files["capture/manifest.json"] = json.dumps(capture, sort_keys=True) + "\n"
        mapping = [json.loads(line) for line in files["video_frames.jsonl"].splitlines()]
        trace = [json.loads(line) for line in files["trace.jsonl"].splitlines()]
        complete = {"before_zero": 5, "at_zero": 6,
            "after_zero": 7}[case["completion"]]
        source_site = site()
        route = source_site["crossing_routes"][case["direction"]]["waypoints_xy"]
        frames = []
        for index, row in enumerate(mapping):
            value = 2 if index < 4 else 1 if index < 6 else 0
            position = route[0] if index < 2 else route[1] if index < complete else route[-1]
            frames.append({"original_frame": row["carla_frame"],
                "time_s": row["time_s"], "signal_form": case["signal_form"],
                "signal_facing_direction": case["direction"],
                "illuminated": True, "flashing": index <= 6,
                "countdown_present": True, "countdown_value": value,
                "pedestrian_xy": position,
                "position_m": trace[index]["position_m"],
                "pedestrian_id": "synthetic-pedestrian",
                "in_highway": 2 <= index < complete,
                "crossing_complete": index >= complete,
                "site_source_sha256": source_site["signal_source_sha256"],
                "source_sha256": sha(b"synthetic-observation"),
                "signal_readback_sha256": sha(b"synthetic-signal-readback"),
                "pedestrian_pose_sha256": sha(b"synthetic-pedestrian-pose"),
                "exception_context": {"NRS 484B.287": "synthetic_unknown",
                    "NRS 484B.290": "synthetic_unknown",
                    "NRS 484B.350": "synthetic_unknown"}})
        packet = {"assignment_id": HERE.name, "case_id": cid,
            "original_trace_id": "synthetic-diagnostic-trace",
            "pedestrian_actor_id": "synthetic-pedestrian",
            "crossing_id": "synthetic-highway-crossing",
            "signal_actor_id": "synthetic-official-facing-signal",
            "site": source_site, "diagnostic_fixture": True,
            "frames": frames}
        source_text = json.dumps(packet, sort_keys=True) + "\n"
        files["original-countdown-observations.json"] = source_text
        files["original-countdown-receipt.json"] = json.dumps({
            "case_id": cid, "fps": 20, "frame_count": len(frames),
            "diagnostic_fixture": True,
            "source_sha256": sha(source_text.encode())}, sort_keys=True) + "\n"
        files["fixture-provenance.json"] = json.dumps({"case_id": cid,
            "scope": "Synthetic nine-frame countdown crossing software diagnostic only; no original signal, pedestrian or legal evidence"},
            sort_keys=True) + "\n"
        path = folder / "diagnostic.json"
        path.write_text(json.dumps(diagnostic, separators=(",", ":")) + "\n")
        relative = str(path.relative_to(ROOT))
        write(folder / "fixture-recipe.json", {"format": "worker-fixture-recipe",
            "sources": [{"path": "diagnostic-input.json", "source": relative,
                "sha256": sha(path.read_bytes())}],
            "generator": {"source": relative, "sha256": sha(path.read_bytes())}})
        write(folder / "measurement-contract.json", {
            "format": "worker-measurement-contract", "case_id": cid,
            "requirements": [{"disposition_index": i,
                "requirement": disposition["requirement"],
                "source": disposition["source"],
                "output_key": key, "method": "measure_" + key,
                "value_type": "object", "kind": "measured",
                "inputs": ["original-countdown-observations.json",
                    "original-countdown-receipt.json"]}
                for i, (disposition, key) in enumerate(zip(
                    plan["requirement_dispositions"],
                    ("flashing_countdown", "crossing_completion", "zero_boundary",
                     "crossing_context")))],
            "negative": {"remove": ["original-countdown-observations.json"],
                "error_contains": "Missing required source: original-countdown-observations.json"}})
        print(cid.split("__")[-1], "synthetic diagnostic", flush=True)


if __name__ == "__main__":
    build()
