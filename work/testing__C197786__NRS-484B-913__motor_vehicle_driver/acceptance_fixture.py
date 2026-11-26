"""Exercise the independent delivery audit on explicitly synthetic saved attempts."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

from delivery_audit import verify_native_frames, verify_original_context, verify_sources
from fire_hose_delivery import body_over_hose_frames, inspect_saved_hose


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--attempt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-passage", choices=("cross", "avoid"), required=True)
    parser.add_argument("--negative-missing-video", action="store_true")
    args = parser.parse_args()
    root = args.attempt.resolve()
    packet = json.loads((root / "saved-packet.json").read_text())
    if packet["case_id"] != args.case:
        raise ValueError("exact saved case differs")
    seal = json.loads((root / "seal.json").read_text())
    if seal.get("diagnostic_fixture") is not True:
        raise ValueError("CPU acceptance proof requires explicit synthetic provenance")
    verify_sources(packet, root)
    verify_native_frames(packet, root)
    verify_original_context(packet, root)
    inspected = inspect_saved_hose(packet, args.case)
    hits = body_over_hose_frames(packet, args.case)
    if bool(hits) != (args.expected_passage == "cross"):
        raise ValueError("saved body passage differs from selected case")
    video = root / ("missing-original.mkv" if args.negative_missing_video else "raw.mkv")
    if not video.is_file():
        raise ValueError("original video source missing")
    runtime = Path(__file__).resolve().parents[2] / "runtime" / "scenario_pipeline"
    sys.path.insert(0, str(runtime))
    from worker_exchange.media import audit

    pixels = {"decoded": 0, "nonblack": False}

    def actual_pixels(frame):
        sample = frame.pixels[::max(3, len(frame.pixels) // 1024)]
        if len(frame.pixels) != frame.width * frame.height * 3:
            raise ValueError("decoded RGB source pixel buffer incomplete")
        pixels["decoded"] += 1
        if any(value for value in sample):
            pixels["nonblack"] = True

    result = audit(video, 900, checkers={"actual_pixels": (hashlib.sha256(Path(__file__).read_bytes()).hexdigest(), actual_pixels)},
                   receipt=args.output.with_suffix(".decode.json"))
    if pixels["decoded"] != 900:
        raise ValueError("original video pixel frames incomplete")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"format": "synthetic-delivery-audit-fixture", "case_id": args.case,
                                      "diagnostic_fixture": True, "native_source_joined": True,
                                      "all_participants": True, "time_join": True,
                                      "body_contact_frames": hits, "observed": inspected,
                                      "source_decode": result, "synthetic_nonblack_pixels": pixels["nonblack"],
                                      "physical_acceptance": None,
                                      "legal_verdict": None}, indent=2) + "\n")
    print(args.case, "synthetic source and full decode checks passed")


if __name__ == "__main__":
    main()
