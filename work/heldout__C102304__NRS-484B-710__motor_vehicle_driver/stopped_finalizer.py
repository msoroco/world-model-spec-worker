"""Saved-only centre-distance output for stopped fire-apparatus branches."""
from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
from pathlib import Path


def _base():
    path = Path(__file__).with_name("fire_finalizer.py")
    spec = importlib.util.spec_from_file_location("fire_finalizer_for_stopped", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def measure_fire_branch(root, config, context):
    """Named selected-measurement method for the pinned contract."""
    return _base().measure_fire_branch(root, config, context)


def analyze(attempt):
    root = Path(attempt)
    config = json.loads((root / "config.json").read_text())
    if config.get("fire_branch") not in ("stopped_drive_to", "stopped_park"):
        raise ValueError("Stopped finalizer requires a stopped-apparatus branch")
    # Base analysis verifies original frame/source joins and independently
    # measures the branch. Its gap channel is a derived diagnostic only here.
    report = _base().analyze(root)
    observed = report["measurements"]["fire_boundary_observation"]["value"]
    channel = root / "fire_centre_distance_ft.jsonl"
    channel.write_text("".join(json.dumps({"time_s": row["time_s"],
                                           "value": row["centre_distance_ft"],
                                           "frame": row["frame"]}) + "\n"
                               for row in observed["observations"]))
    return report


def build_result(attempt, report):
    root = Path(attempt)
    result = _base().build_result(root, report)
    observed = report["measurements"]["fire_boundary_observation"]["value"]
    if observed["boundary_measurement"] != "centre_distance_ft":
        raise ValueError("Stopped target check must use measured centre distance")
    channel = root / "fire_centre_distance_ft.jsonl"
    if not channel.is_file():
        raise ValueError("Missing derived original-frame centre-distance stream")
    result["recording_evidence"] = [{"name": "fire_centre_distance_ft",
                                     "unit": "ft", "reference": channel.name,
                                     "sha256": sha256(channel.read_bytes()).hexdigest()}]
    values = [row["centre_distance_ft"] for row in observed["observations"]]
    result["realized_observables"] = {"fire_centre_distance_ft": {
        "unit": "ft", "method": "original-frame world center distance from retained Native footprints",
        "time_window": "all original frames", "statistic": "min",
        "reference": channel.name, "value": min(values),
        "sample_window_s": [observed["observations"][0]["time_s"],
                            observed["observations"][-1]["time_s"]]}}
    return result


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = analyze(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError("Retain previous stopped analysis report; choose fresh output")
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")
    from worker_exchange.native_output import write_result
    write_result(args.attempt, build_result(args.attempt, report))


if __name__ == "__main__":
    main()
