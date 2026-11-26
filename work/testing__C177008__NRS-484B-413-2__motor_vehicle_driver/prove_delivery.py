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
from test_native_capture import Session
from test_signal_construction import site
from native_capture import capture
from saved_export import export
from delivery_audit import audit


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    tag = args.case.rsplit("__", 1)[-1]
    plan = json.loads((ROOT / "case-plan.json").read_text())
    selected = next(item for item in plan["cases"] if item["case_id"] == args.case)
    district = ("residential" if tag.startswith("residence_") else
                "other" if tag.startswith("other_area_") else "business")
    reviewed_site = site(district)
    scratch = REPO / ".runtime-work" / "c177008-owner-nov26/output"
    with tempfile.TemporaryDirectory(prefix="delivery-test-", dir=scratch) as temporary:
        root = Path(temporary)
        site_raw = (json.dumps(reviewed_site, sort_keys=True) + "\n").encode()
        (root / "original-site.json").write_bytes(site_raw)
        site_sha = hashlib.sha256(site_raw).hexdigest()
        manifest = json.loads((ROOT / "execution-manifest.json").read_text())
        entry = next(item for item in manifest["cases"] if item["case_id"] == args.case)
        construction = json.loads((ROOT / entry["construction"]).read_text())
        config = json.loads(next(item["content"] for item in construction["files"]
                                 if item["path"] == "config.json"))
        (root / "config.json").write_text(json.dumps(config) + "\n")
        source = capture(Session(), reviewed_site, site_sha, selected, root, frames=3)
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
