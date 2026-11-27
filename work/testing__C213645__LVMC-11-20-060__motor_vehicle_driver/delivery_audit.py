"""Independent source and media audit for a saved driveway attempt.

This is a CPU software check. Local acceptance must also decode promoted media,
review pixels and physical completion; no fixture can satisfy those checks.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path

from driveway_measurement import load_sources, measure
from native_acquisition import VIEWS


def audit(root, case, *, diagnostic=False):
    root = Path(root)
    inventory, source = load_sources(root, diagnostic=diagnostic)
    measured = measure(root, case, diagnostic=diagnostic)
    frames = source["frame_map"]["frames"]
    media = inventory.get("media", {})
    if set(media) != set(VIEWS):
        raise ValueError("four original camera sources missing")
    for name in VIEWS:
        entry = media[name]
        path = root / entry.get("path", "")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != entry.get("sha256"):
            raise ValueError("original camera source absent or changed: " + name)
        with zipfile.ZipFile(path) as archive:
            names = archive.namelist()
            expected = [f"{i:04d}-{row['frame']}.png" for i, row in enumerate(frames)]
            if names != expected:
                raise ValueError("original camera frame map differs: " + name)
            for filename in names:
                if not archive.read(filename).startswith(b"\x89PNG\r\n\x1a\n"):
                    raise ValueError("original camera pixel frame malformed: " + name)
    if inventory.get("physical_acceptance_claimed") is not False:
        raise ValueError("software attempt improperly claims physical acceptance")
    return {"format": "worker-driveway-delivery-audit",
            "case_id": case["case_id"], "source_kind": inventory["source_kind"],
            "frame_count": len(frames), "source_sha256": measured["source_sha256"],
            "media_sha256": {name: media[name]["sha256"] for name in VIEWS},
            "software_checks_passed": True,
            "physical_completion_verified": False,
            "actual_pixels_reviewed": False,
            "legal_verdict_claimed": False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--attempt", required=True, type=Path)
    parser.add_argument("--case", required=True)
    parser.add_argument("--diagnostic", action="store_true")
    args = parser.parse_args()
    plan = json.loads((Path(__file__).resolve().parent / "case-plan.json").read_text())
    cases = [c for c in plan["cases"] if c["case_id"] == args.case]
    if len(cases) != 1:
        raise ValueError("exact case not found")
    print(json.dumps(audit(args.attempt, cases[0], diagnostic=args.diagnostic), sort_keys=True))


if __name__ == "__main__":
    main()
