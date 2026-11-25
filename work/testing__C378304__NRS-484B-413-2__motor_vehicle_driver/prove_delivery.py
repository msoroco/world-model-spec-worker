"""Exercise independent delivery audit on a fake camera acquisition and stale source."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from test_native_capture import Session
from test_native_site import SITE
from native_capture import capture
from saved_export import export
from delivery_audit import audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    tag = args.case.rsplit("__", 1)[-1]
    selected = {"case_id": args.case, "target": {
        "weather_request": "rain" if tag == "rain" else "clear",
        "signal_continuity_request": "interrupt_then_resume" if tag == "interrupted" else "continuous"}}
    scratch = REPO / ".runtime-work" / "c378304"
    with tempfile.TemporaryDirectory(prefix="delivery-test-", dir=scratch) as temporary:
        root = Path(temporary)
        site_raw = (json.dumps(SITE, sort_keys=True) + "\n").encode()
        (root / "original-site.json").write_bytes(site_raw)
        site_sha = hashlib.sha256(site_raw).hexdigest()
        config = json.loads((ROOT / "config.json").read_text())
        config["selected_case_id"] = args.case
        (root / "config.json").write_text(json.dumps(config) + "\n")
        source = capture(Session(), SITE, site_sha, selected, root, frames=3)
        receipt = {"format": "original-turn-signal-acquisition", "case_id": args.case,
                   "physical_acceptance": False, "legal_assessment": "unresolved",
                   "site_sha256": site_sha, "trace_sha256": source["trace_sha256"],
                   "frame_count": 3, "camera_archives": source["camera_archives"]}
        (root / "original-acquisition-receipt.json").write_text(json.dumps(receipt) + "\n")
        (root / "trace.jsonl").write_text("".join(json.dumps({"frame": row["frame"],
            "time_s": row["time_s"]}) + "\n" for row in
            json.loads((root / "original-turn-signal.json").read_text())["samples"]))
        (root / "road.xodr").write_text("diagnostic road\n")
        (root / "carla_recorder.log").write_text("diagnostic recorder\n")
        export(root, args.case, allow_diagnostic=True)
        if args.negative:
            (root / "approach.png.zip").write_bytes((root / "approach.png.zip").read_bytes() + b"changed")
            try:
                audit(root, args.case, diagnostic_test=True)
            except ValueError as error:
                if "camera archive hash differs" not in str(error):
                    raise
                print("camera archive hash differs; rejected stale original pixel source")
                raise SystemExit(2)
            raise AssertionError("stale original pixel source accepted")
        report = audit(root, args.case, diagnostic_test=True)
        if report["frame_count"] != 3 or len(report["video_sources"]) != 4:
            raise AssertionError("four original camera streams not audited")
        print(json.dumps({"case_id": args.case, "frame_count": 3,
                          "full_video_decode": True, "physical_acceptance_claimed": False}))


if __name__ == "__main__":
    main()
