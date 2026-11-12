"""Build source-shaped, synthetic full-window release diagnostics.

The output exercises original-frame joins and the measured release comparison.
It is a CPU fixture, never a CARLA capture or physical observation.
"""

import argparse
from hashlib import sha256
import json
from pathlib import Path

from qualitative_release_audit import audit

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
DELAYS = (0, 80, 160)
FRAME_COUNT = 320
FIRST_FRAME = 38033


def _lines(rows):
    return "".join(json.dumps(row, separators=(",", ":"), allow_nan=False) + "\n" for row in rows)


def build(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    source = json.loads((HERE / "diagnostic-yield-sweep-0000.json").read_text())["files"]
    short = [json.loads(line) for line in source["intersection_participants.jsonl"].splitlines()]
    if len(short) != 9:
        raise ValueError("Expected nine original seed body samples")
    roots = []
    for rank, delay in enumerate(DELAYS):
        root = output / f"yield_release_delay-{rank:04d}"
        root.mkdir(exist_ok=True)
        config = {
            "selected_case_id": ASSIGNMENT + f"__yield_release_delay-{rank:04d}",
            "release_delay_frames": delay,
            "frames": FRAME_COUNT,
            "diagnostic_kind": "synthetic_cpu_original_source_shape",
        }
        (root / "config.json").write_text(json.dumps(config, indent=2) + "\n")
        (root / "intersection_topology.json").write_text(source["intersection_topology.json"])
        participants, frames, trace = [], [], []
        for index in range(FRAME_COUNT):
            frame = FIRST_FRAME + index
            time_s = (index + 1) / 20
            subject_index = min(8, max(0, index - delay))
            row = dict(short[min(index, 8)])
            row.update(frame=frame, time_s=time_s,
                       subject_corners=short[subject_index]["subject_corners"])
            participants.append(row)
            frames.append({"video_frame": index, "carla_frame": frame,
                           "native_frame": frame, "time_s": time_s})
            trace.append({"frame": frame, "time_s": time_s})
        for name, rows in (("intersection_participants.jsonl", participants),
                           ("video_frames.jsonl", frames), ("trace.jsonl", trace)):
            (root / name).write_text(_lines(rows))
        roots.append(root)
    result = audit(roots)
    result["sources"] = [
        {"case_id": json.loads((root / "config.json").read_text())["selected_case_id"],
         "path": str(root),
         "files": {name: sha256((root / name).read_bytes()).hexdigest()
                   for name in ("intersection_topology.json", "intersection_participants.jsonl",
                                "video_frames.jsonl", "trace.jsonl")}}
        for root in roots
    ]
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--receipt", required=True)
    args = parser.parse_args()
    result = build(args.output)
    Path(args.receipt).write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"points": result["points"], "physical_realization_claimed": False}))


if __name__ == "__main__":
    main()
