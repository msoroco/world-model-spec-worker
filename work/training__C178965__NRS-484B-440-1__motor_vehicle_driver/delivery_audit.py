"""Independent source-bound roadside delivery audit with synthetic CPU mode."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE / "native/tests"))
from test_saved import fixture
from finalize_saved import summarize

VIEWS = ("overview", "approach", "reference_corner", "driver_reference")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def inspect(case, attempt, *, diagnostic):
    measurements = summarize(attempt, case, diagnostic=diagnostic)
    stopped = measurements["stopped"]
    if len(stopped) < 10:
        raise ValueError("Stopped episode too short for independent review")
    if any(row["opposite_unobstructed_width_m"] < 0 for row in stopped):
        raise ValueError("Invalid original opposite-width measurement")
    if not all("clear_200ft_forward_proxy" in row and "clear_200ft_backward_proxy" in row
               for row in stopped):
        raise ValueError("Both 200-foot directions are required")
    result = {"format": "c178965-independent-delivery-diagnostic-v1", "case_id": case,
              "source_hashes": measurements["source_sha256"],
              "joined_frames": measurements["frame_count"],
              "stopped_frames": len(stopped),
              "forward_clear_proxy_frames": sum(row["clear_200ft_forward_proxy"] for row in stopped),
              "backward_clear_proxy_frames": sum(row["clear_200ft_backward_proxy"] for row in stopped),
              "parking_brake_observed_frames": sum(row["parking_brake_observed"] for row in stopped),
              "legal_verdict": None, "physical_acceptance_claimed": False,
              "diagnostic_fixture": diagnostic}
    if not diagnostic:
        videos = {}
        for view in VIEWS:
            path = Path(attempt) / (view + ".mkv")
            if not path.is_file():
                raise ValueError("Missing original video: " + view)
            decoded = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0",
                "-count_frames", "-show_entries", "stream=nb_read_frames", "-of", "default=nw=1:nk=1",
                str(path)], capture_output=True, text=True, check=True)
            if decoded.stdout.strip() != "600":
                raise ValueError("Original video frame count differs: " + view)
            videos[view] = sha(path)
        result["video_sha256"] = videos
        result["physical_acceptance_claimed"] = False
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt")
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    if args.case not in {HERE.name + "__probe_0" + str(i) for i in (1, 2, 3)}:
        raise ValueError("Another case selected")
    if args.diagnostic:
        temp_root = Path(os.environ.get("TMPDIR", "/")).resolve()
        if not temp_root.is_relative_to(REPO / ".runtime-work"):
            raise ValueError("Set TMPDIR under .runtime-work")
        with tempfile.TemporaryDirectory(dir=temp_root, prefix="c178965-audit-") as temporary:
            attempt = Path(temporary)
            fixture(attempt, int(args.case[-1]))
            print(json.dumps(inspect(args.case, attempt, diagnostic=True), sort_keys=True))
    else:
        if not args.attempt:
            raise ValueError("Original Native source required for delivery acceptance")
        print(json.dumps(inspect(args.case, Path(args.attempt), diagnostic=False), sort_keys=True))


if __name__ == "__main__":
    main()
