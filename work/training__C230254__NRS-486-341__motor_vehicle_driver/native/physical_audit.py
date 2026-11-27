"""Independent original-motion checker for the lane-use capture.

The motion floor is an engineering check that a trial drove through a scene.
It is not a definition of full lane use or deprivation under NRS 486.341.
"""

import argparse
import json
import math
import tempfile
from pathlib import Path

from finalize_lane_use import finalize_bound


def _center(points):
    return (sum(point[0] for point in points) / len(points),
            sum(point[1] for point in points) / len(points))


def assess(attempt, minimum_progress_m=0.25):
    attempt = Path(attempt)
    with tempfile.TemporaryDirectory() as directory:
        receipt = finalize_bound(attempt, Path(directory) / "measured.jsonl")
    rows = [json.loads(line) for line in
            (attempt / "lane-use-source.jsonl").read_text().splitlines() if line.strip()]
    ego = [_center(row["ego_footprint"]) for row in rows]
    protected = [_center(row["motorcycle_footprint"]) for row in rows]
    def progress(positions):
        return sum(math.dist(a, b) for a, b in zip(positions, positions[1:]))
    ego_progress, protected_progress = progress(ego), progress(protected)
    met = (len(rows) >= 2 and ego_progress >= minimum_progress_m
           and protected_progress >= minimum_progress_m)
    return {
        "format": "worker-lane-use-physical-check",
        "status": "met" if met else "not_met",
        "method": "original timestamp joined full-footprint center path",
        "observed": {"frames": len(rows), "subject_path_m": ego_progress,
                     "protected_path_m": protected_progress},
        "minimum_progress_m": minimum_progress_m,
        "engineering_tolerance_not_legal": True,
        "sources": receipt["sources"],
        "physical_motion_observed": met,
        "actual_camera_visibility_unverified": True,
        "legal_verdict_claimed": False,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True)
    args = parser.parse_args()
    print(json.dumps(assess(args.attempt), sort_keys=True))
