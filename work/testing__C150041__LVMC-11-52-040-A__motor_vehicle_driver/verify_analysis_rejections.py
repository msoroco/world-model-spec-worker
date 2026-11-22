"""Check six independently run missing-activity-source analysis failures."""
from __future__ import annotations

import argparse
from pathlib import Path

from parking_pose import REQUESTS


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt-prefix", required=True)
    parser.add_argument("--log-root", required=True)
    args = parser.parse_args()
    root = Path(args.log_root)
    for kind in REQUESTS:
        attempt = Path(args.attempt_prefix + kind)
        log = root / kind / "cpu-analysis-negative.log"
        if (not log.is_file() or "ValueError: activity original source missing" not in log.read_text()
                or (attempt / "result.json").exists() or (attempt / "analysis-report.json").exists()):
            raise ValueError("missing-source analysis did not reject exactly: " + kind)
    print("six exact missing-activity-source analysis invocations rejected; no outputs written")
