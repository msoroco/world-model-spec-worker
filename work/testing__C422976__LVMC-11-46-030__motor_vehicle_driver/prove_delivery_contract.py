"""Exercise the exact-case independent audit protocol on CPU-only packets."""

import argparse
import json
from pathlib import Path
import sys

from school_lane_controls import VARIANTS


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "tests"))
from test_delivery_audit import DeliveryAuditTests
from delivery_audit import ASSIGNMENT


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--mode", choices=("diagnostic-positive", "delivery-negative"),
                        required=True)
    args = parser.parse_args()
    if args.case not in {ASSIGNMENT + "__" + item.suffix for item in VARIANTS}:
        raise ValueError("exact selected case required")
    fixture = DeliveryAuditTests("test_original_source_joins_and_decode_protocol")
    fixture.setUp()
    try:
        receipt = fixture.attempt()
        receipt["case_id"] = args.case
        frame_map = fixture.root / "frame-map.json"
        trace = fixture.root / "trace.json"
        seal_path = fixture.root / "seal.json"
        for path in (frame_map, trace, seal_path):
            packet = json.loads(path.read_text())
            packet["case_id"] = args.case
            path.write_text(json.dumps(packet, sort_keys=True) + "\n")
        from test_delivery_audit import digest
        receipt["frame_map_ref"]["sha256"] = digest(frame_map)
        receipt["trace_ref"]["sha256"] = digest(trace)
        seal = json.loads(seal_path.read_text())
        seal["sources"]["frame-map.json"] = receipt["frame_map_ref"]["sha256"]
        seal["sources"]["trace.json"] = receipt["trace_ref"]["sha256"]
        seal_path.write_text(json.dumps(seal, sort_keys=True) + "\n")
        receipt["capture_seal_ref"]["sha256"] = digest(seal_path)
        if args.mode == "delivery-negative":
            receipt["owner_released"] = False
            fixture.run_audit(receipt)
            raise AssertionError("unreleased attempt was accepted")
        result = fixture.run_audit(receipt)
        if result["frames_checked"] != 900 or len(result["video_sha256"]) != 4:
            raise ValueError("audit omitted the frame or video checks")
        print(json.dumps({"case_id": args.case, "scope": "synthetic audit protocol only",
                          "positive_protocol_passed": True, "original_delivery_claimed": False},
                         sort_keys=True))
    finally:
        fixture.doCleanups()


if __name__ == "__main__":
    main()
