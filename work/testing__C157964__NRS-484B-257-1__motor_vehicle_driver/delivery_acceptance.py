"""CPU delivery audit for an exact C157964 case and its four camera videos.

Diagnostic mode proves decoder and source checks only. Original mode additionally
requires an independently pinned physical review packet and original custody.
"""

import argparse
import json
import subprocess
from pathlib import Path

from delivery_audit import audit_original
from saved_audit import audit_saved
from yield_view import CASES, require


VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def audit(case, attempt, *, diagnostic=False, review_packet=None,
          expected_site_packet_sha256=None, expected_review_packet_sha256=None):
    require(diagnostic or expected_site_packet_sha256,
            "independent reviewed site hash missing")
    source = audit_saved(attempt, case, allow_diagnostic=diagnostic,
                         expected_site_packet_sha256=expected_site_packet_sha256)
    require(source["frame_count"] == 900 and source["decoded_camera_frames"] == 3600,
            "all participant and camera frame joins missing")
    video_root = Path(attempt).resolve().parent
    decoded = {}
    for view in VIEWS:
        video = video_root / (view + ".mkv")
        require(video.is_file(), "delivery video missing: " + view)
        process = subprocess.run(("ffmpeg", "-nostdin", "-v", "error", "-i",
                                  str(video), "-f", "null", "-"),
                                 capture_output=True, text=True, check=False)
        require(process.returncode == 0 and not process.stderr.strip(),
                "full delivery video decode failed: " + view)
        decoded[view] = "full_decode_passed"
    if not diagnostic:
        require(review_packet and expected_review_packet_sha256,
                "independent original physical review missing")
        physical = audit_original(attempt, review_packet, case,
                                  expected_site_packet_sha256=expected_site_packet_sha256,
                                  expected_review_packet_sha256=expected_review_packet_sha256)
        require(physical["physical_completion"] is True,
                "original physical completion missing")
    return {"case_id": case.case_id, "source_audit": source,
            "decoded_videos": decoded, "diagnostic": diagnostic,
            "original_physical_completion": False if diagnostic else True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("case_id")
    parser.add_argument("attempt", type=Path)
    parser.add_argument("--diagnostic", action="store_true")
    parser.add_argument("--review-packet", type=Path)
    parser.add_argument("--expected-site-packet-sha256")
    parser.add_argument("--expected-review-packet-sha256")
    args = parser.parse_args()
    case = next((item for item in CASES if args.case_id in
                 (item.case_id, "testing__C157964__NRS-484B-257-1__motor_vehicle_driver__" + item.case_id)), None)
    require(case is not None, "unknown exact delivery case")
    print(json.dumps(audit(case, args.attempt, diagnostic=args.diagnostic,
                           review_packet=args.review_packet,
                           expected_site_packet_sha256=args.expected_site_packet_sha256,
                           expected_review_packet_sha256=args.expected_review_packet_sha256),
                     sort_keys=True))


if __name__ == "__main__":
    main()
