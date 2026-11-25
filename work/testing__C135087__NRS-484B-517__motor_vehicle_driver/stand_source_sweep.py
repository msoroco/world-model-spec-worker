"""Extract source-bound stand sweep observations from one original attempt.

The two expected SHA-256 values come from a separately reviewed site and
vehicle packet. The result supplies measurements for later legal review; it
never supplies a sign, expedience, temporary-stop or interference verdict.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from stand import SourceError, audit_saved_attempt
from stand_converter_source import audit as audit_converter
from stand_delivery import audit as audit_delivery


def _sha(path):
    if path.is_symlink() or not path.is_file():
        raise SourceError("reviewed original source missing: " + path.name)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract(root, site_sha256, vehicle_sha256):
    root = Path(root).resolve()
    if any(not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value)
           for value in (site_sha256, vehicle_sha256)):
        raise SourceError("reviewed original source hashes required")
    provenance = json.loads((root / "acquisition-provenance.json").read_text())
    if provenance.get("provenance_kind") != "native" or provenance.get("diagnostic_fixture") is not False:
        raise SourceError("source-backed sweep requires an original Native acquisition")
    for name, expected in (("site-original.json", site_sha256),
                           ("vehicle-original.json", vehicle_sha256)):
        if _sha(root / name) != expected:
            raise SourceError("reviewed source hash differs: " + name)
    attempt = json.loads((root / "attempt-source.json").read_text())
    inventory = audit_saved_attempt(attempt, root)
    converter = audit_converter(root, attempt)
    delivery = audit_delivery(root)
    if (inventory["case_id"] != converter["case_id"] or
            inventory["case_id"] != delivery["case_id"]):
        raise SourceError("original audit case identities differ")
    return {"format": "c135087-source-bound-sweep-observations-v1",
            "case_id": inventory["case_id"],
            "reviewed_site_sha256": site_sha256,
            "reviewed_vehicle_sha256": vehicle_sha256,
            "attempt_source_sha256": _sha(root / "attempt-source.json"),
            "converter_audit_sha256": _sha(root / "converter-source-audit.json"),
            "measurements": inventory["measurement"],
            "decoded_camera_frames": delivery["decoded_camera_frames"],
            "original_graph_count": converter["graph_count"],
            "judgments": {phrase: None for phrase in
                          ("official_designation_and_sign_adequacy", "temporary_stop",
                           "expeditious_passenger_loading", "noninterference")},
            "legal_verdict_claimed": False,
            "physical_completion_claimed": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True)
    parser.add_argument("--reviewed-site-sha256", required=True)
    parser.add_argument("--reviewed-vehicle-sha256", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = extract(args.attempt, args.reviewed_site_sha256,
                     args.reviewed_vehicle_sha256)
    with Path(args.output).open("x", encoding="utf-8") as stream:
        json.dump(result, stream, sort_keys=True, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
