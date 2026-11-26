"""Read one immutable saved-source packet and measure without relabeling it."""

import argparse
import hashlib
import json
from pathlib import Path

from measure_statutory import SOURCE_NAMES, measure


def inside(root, relative):
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError("Saved source path must be relative")
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Saved source file missing or outside attempt: " + relative)
    return path


def inspect(attempt, expected_case):
    root = Path(attempt).resolve()
    context_path = inside(root, "stop_yield_context.json")
    trace_path = inside(root, "stop_yield_motion.jsonl")
    context = json.loads(context_path.read_text())
    source_paths = context.get("source_files")
    if not isinstance(source_paths, dict) or set(source_paths) != set(SOURCE_NAMES):
        raise ValueError("Seven exact source files required")
    for name in SOURCE_NAMES:
        source = inside(root, source_paths[name])
        actual = hashlib.sha256(source.read_bytes()).hexdigest()
        if actual != context.get(name + "_sha256"):
            raise ValueError("Saved source SHA-256 differs: " + name)
    rows = [json.loads(line) for line in trace_path.read_text().splitlines() if line.strip()]
    result = measure(context, rows, expected_case)
    result["packet_sources"] = {
        "context_sha256": hashlib.sha256(context_path.read_bytes()).hexdigest(),
        "motion_sha256": hashlib.sha256(trace_path.read_bytes()).hexdigest(),
        "source_files": {name: context[name + "_sha256"] for name in SOURCE_NAMES},
    }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    output = Path(args.output)
    if output.exists():
        raise ValueError("Retain previous saved measurement output")
    result = inspect(args.attempt, args.case)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"case_id": result["case_id"], "source_kind": result["source_kind"],
                      "sample_count": result["sample_count"], "legal_verdict": None}))
