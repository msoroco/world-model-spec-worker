"""Source-bound diagnostic comparison for the planned posted-speed cases.

This is a CPU audit of saved source samples. It does not infer public authority,
physical completion, original pixels, or a legal verdict from a fixture.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

MPS_TO_MPH = 2.2369362921
REQUIRED_CONTEXT = (
    "sign_id", "posted_mph", "authority_source", "highway_source",
    "governed_direction", "zone_start_m", "zone_end_m",
)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_json(path, expected_hash):
    require(digest(path) == expected_hash, "source hash mismatch: " + str(path))
    return json.loads(Path(path).read_text())


def audit_case(case, base, min_frames, min_duration_s):
    context_path = base / case["context_path"]
    trace_path = base / case["trace_path"]
    context = load_json(context_path, case["context_sha256"])
    require(all(context.get(k) is not None for k in REQUIRED_CONTEXT), "missing signed-zone context")
    require(context["authority_source"] and context["highway_source"], "missing authority or highway source")
    require(context["posted_mph"] > 0, "invalid posted speed")
    require(context["zone_start_m"] < context["zone_end_m"], "invalid governed interval")
    require(digest(trace_path) == case["trace_sha256"], "trace source hash mismatch")
    samples = [json.loads(line) for line in trace_path.read_text().splitlines() if line]
    require(len(samples) >= min_frames, "insufficient source frames")
    require([row.get("frame") for row in samples] == list(range(len(samples))), "nonconsecutive source frames")
    times = [row["time_s"] for row in samples]
    require(all(math.isfinite(t) for t in times) and all(a < b for a, b in zip(times, times[1:])), "nonmonotonic time")
    require(times[-1] - times[0] >= min_duration_s, "insufficient source duration")
    governed = []
    for row in samples:
        require(all(k in row for k in ("x_m", "speed_mps", "direction")), "missing raw motion source")
        speed = row["speed_mps"]
        require(math.isfinite(speed) and speed >= 0, "invalid measured speed")
        if context["zone_start_m"] <= row["x_m"] <= context["zone_end_m"] and row["direction"] == context["governed_direction"]:
            governed.append(row)
    require(governed, "no governed-zone motion samples")
    speeds = [row["speed_mps"] * MPS_TO_MPH for row in governed]
    return {
        "case_id": case["case_id"],
        "context_sha256": case["context_sha256"],
        "trace_sha256": case["trace_sha256"],
        "source_frames": len(samples),
        "governed_frames": len(governed),
        "posted_mph": context["posted_mph"],
        "min_measured_mph": min(speeds),
        "max_measured_mph": max(speeds),
        "max_delta_mph": max(speeds) - context["posted_mph"],
        "sign_id": context["sign_id"],
        "authority_source": context["authority_source"],
        "highway_source": context["highway_source"],
        "governed_direction": context["governed_direction"],
        "zone_start_m": context["zone_start_m"],
        "zone_end_m": context["zone_end_m"],
    }


def audit(spec_path, min_frames=600, min_duration_s=29.9):
    spec_path = Path(spec_path)
    spec = json.loads(spec_path.read_text())
    require(spec.get("format") == "posted-speed-source-comparison-v1", "wrong comparison format")
    require(len(spec.get("cases", [])) == 3, "expected three comparison cases")
    cases = [audit_case(case, spec_path.parent, min_frames, min_duration_s) for case in spec["cases"]]
    require(len({c["case_id"] for c in cases}) == 3, "duplicate case")
    fixed = ("context_sha256", "posted_mph", "sign_id", "authority_source", "highway_source",
             "governed_direction", "zone_start_m", "zone_end_m")
    for key in fixed:
        require(len({c[key] for c in cases}) == 1, "comparison context changed: " + key)
    require(len({c["trace_sha256"] for c in cases}) == 3, "comparison reuses a trace")
    return {"format": "posted-speed-source-comparison-audit-v1", "passed": True,
            "comparison_id": spec["comparison_id"], "cases": cases,
            "measurement_note": "Measured saved speed only. No fixture-derived legal classification or tolerance."}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("spec")
    parser.add_argument("--min-frames", type=int, default=600)
    parser.add_argument("--min-duration-s", type=float, default=29.9)
    args = parser.parse_args()
    print(json.dumps(audit(args.spec, args.min_frames, args.min_duration_s), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
