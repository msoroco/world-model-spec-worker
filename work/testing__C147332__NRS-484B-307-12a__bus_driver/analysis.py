"""Read saved original channels and measure C147332 green-arrow coverage."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from green_lane_measurement import measure
from source_review import validate as validate_site


CHANNELS = ("bus-body-history.jsonl", "lane-signal-history.jsonl", "camera-frame-map.jsonl")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def recorded_sha(acquisition, name):
    value = acquisition.get(name)
    return value.get("sha256") if isinstance(value, dict) else value


def source_rows(attempt, acquisition, name):
    path = attempt / name
    if not path.is_file() or recorded_sha(acquisition, name) != sha(path):
        raise ValueError("original channel missing or changed: " + name)
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if len(rows) < 2:
        raise ValueError("original channel needs at least two frames: " + name)
    verified = []
    for row in rows:
        rel = row.get("source_path")
        if not isinstance(rel, str) or not rel or Path(rel).is_absolute() or ".." in Path(rel).parts:
            raise ValueError("original channel row source path missing: " + name)
        source = attempt / rel
        digest = recorded_sha(acquisition, rel)
        if (not source.is_file() or sha(source) != digest or
                (row.get("source_sha256") is not None and row["source_sha256"] != digest)):
            raise ValueError("original channel row source missing or changed: " + name)
        verified.append(row)
    return verified


def verified_join(attempt):
    attempt = Path(attempt)
    acquisition = json.loads((attempt / "acquisition.json").read_text())
    packet = attempt / "reviewed-context.json"
    site = validate_site(packet, source_root=attempt)
    if recorded_sha(acquisition, packet.name) != sha(packet):
        raise ValueError("site review packet is not bound to original acquisition")
    streams = [source_rows(attempt, acquisition, name) for name in CHANNELS]
    if len({len(rows) for rows in streams}) != 1:
        raise ValueError("original channels have different frame counts")
    joined = []
    for body, signal, camera in zip(*streams):
        if (signal.get("official_device_source_sha256") != site["official_device_source_sha256"] or
                signal.get("highway_id") != site["highway_id"]):
            raise ValueError("signal observation differs from reviewed site")
        observed_green = {lane.get("lane_id") for lane in signal.get("lanes", [])
                          if lane.get("symbol") == "down_green_arrow"}
        if observed_green != set(site["governed_lane_ids"]):
            raise ValueError("observed green lanes differ from reviewed device")
        joined.append({"frame": body.get("frame"),
                       "elapsed_seconds": body.get("elapsed_seconds"),
                       "body": body, "lane_signals": signal, "camera_frame": camera})
    return joined, site


def build_report(attempt):
    attempt = Path(attempt)
    joined, site = verified_join(attempt)
    observed = measure(joined)
    return {"format": "worker-analysis-report", "analysis_complete": True,
            "site_review": site,
            "measurements": {"green_arrow_bus_lane": observed},
            "source_hashes": {name: sha(attempt / name) for name in CHANNELS},
            "legal_verdict_claimed": False, "physical_acceptance_claimed": False,
            "limitations": ["Original camera frame mapping does not itself prove pixel visibility.",
                            "Official-device and highway legal sufficiency require independent review."]}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    report = build_report(args.attempt)
    output = Path(args.output)
    if output.exists():
        raise ValueError("retain prior report; choose a fresh output")
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + "\n")


if __name__ == "__main__":
    main()
