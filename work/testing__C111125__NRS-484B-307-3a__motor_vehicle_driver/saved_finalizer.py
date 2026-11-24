"""Saved-only dual-green observation report; physical and legal review stay open."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from dual_green import require
from saved_attempt import measure_delivery, measure_saved


PREFIX = "testing__C111125__NRS-484B-307-3a__motor_vehicle_driver__"
SUFFIXES = {"dual_clear", "dual_vehicle_present", "dual_pedestrian_present",
            "dual_pedestrian_late"}


def finalize(site_path, source_root, attempt_dir, case_id, output_path, diagnostic=False):
    """Retain an independently measured source receipt; never infer permission."""
    require(case_id.startswith(PREFIX) and case_id[len(PREFIX):] in SUFFIXES,
            "wrong exact dual-green finalizer case")
    site_path = Path(site_path)
    attempt_dir = Path(attempt_dir)
    output_path = Path(output_path)
    require(output_path.resolve() != (attempt_dir / "native-attempt.json").resolve(),
            "finalizer cannot overwrite original attempt")
    raw_site = site_path.read_bytes()
    site = json.loads(raw_site)
    measured = (measure_saved if diagnostic else measure_delivery)(
        site, source_root, attempt_dir, case_id)
    receipt = json.loads((attempt_dir / "native-attempt.json").read_text(encoding="utf-8"))
    report = {"format": "dual-green-saved-observation", "case_id": case_id,
              "diagnostic_only": bool(diagnostic),
              "site_sha256": hashlib.sha256(raw_site).hexdigest(),
              "attempt_sha256": hashlib.sha256((attempt_dir / "native-attempt.json").read_bytes()).hexdigest(),
              "event_sha256": receipt["event_source"]["sha256"],
              "frame_count": measured["frame_count"],
              "exhibition_frame": measured["exhibition"]["frame"],
              "case_observation": measured["case_observation"],
              "camera_audit": measured.get("camera_audit"),
              "permission_verdict": None, "right_of_way_verdict": None,
              "physical_acceptance_claimed": False}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    require(not output_path.exists(), "finalizer output already exists")
    output_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--site", required=True)
    parser.add_argument("--source-root", required=True)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--case", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    report = finalize(args.site, args.source_root, args.attempt, args.case,
                      args.output, diagnostic=args.diagnostic)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
