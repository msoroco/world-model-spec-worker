"""Replay two exact source-shaped CPU captures through saved-only CLIs.

This is a diagnostic software proof. The fake adapter does not establish a
reviewed alley, original CARLA pixels, interior attention or legal status.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from unittest.mock import patch
import sys
import types

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "tests"))

import native_capture
import saved_delivery
import saved_finalizer
from test_native_capture import Actor, Adapter, SITE, context


def prove(output_root: Path) -> dict:
    root = output_root.resolve()
    if ".runtime-work" not in root.parts or root.exists():
        raise ValueError("choose a fresh output directory under .runtime-work")
    root.mkdir(parents=True)
    carla = types.SimpleNamespace(VehicleControl=lambda **kwargs: kwargs)
    sources = {}
    for case_id in native_capture.CASE_PROFILES:
        attempt = root / case_id.rsplit("__", 1)[1]
        attempt.mkdir()
        with patch.object(native_capture, "sample_from_native", side_effect=context):
            native_capture.capture(Adapter(), Actor(), carla, SITE,
                                   case_id, "diagnostic-person", attempt)
        report = attempt / "saved-measurement.json"
        saved_finalizer.main(["--attempt", str(attempt), "--case", case_id,
                              "--output", str(report), "--allow-diagnostic"])
        result = json.loads(report.read_text())
        if (result["original_frames"] != 900 or result["decoded_original_pngs"] != 3600 or
                result["attention_state"] != "unobserved" or
                result["legal_judgment"] != "unresolved"):
            raise ValueError("exact saved measurement is incomplete")
        sources[case_id] = {"capture_sha256": hashlib.sha256((attempt / "capture.json").read_bytes()).hexdigest(),
                            "measurement_sha256": hashlib.sha256(report.read_bytes()).hexdigest(),
                            "original_pngs_decoded": result["decoded_original_pngs"]}
    steady, variation = (root / "steady_travel", root / "steering_variation")
    pair_path = root / "saved-comparison.json"
    saved_delivery.main(["--steady", str(steady), "--variation", str(variation),
                         "--output", str(pair_path), "--allow-diagnostic"])
    pair = json.loads(pair_path.read_text())
    if pair["legal_judgment"] != "unresolved" or pair["diagnostic_fixture"] is not True:
        raise ValueError("saved comparison promoted a diagnostic judgment")
    source = variation / "operation.jsonl"
    source.rename(variation / "operation.hidden")
    negative = root / "missing-operation.json"
    try:
        saved_finalizer.main(["--attempt", str(variation), "--case",
                              next(case for case in sources if case.endswith("__steering_variation")),
                              "--output", str(negative), "--allow-diagnostic"])
    except ValueError as error:
        if "original source missing or symlinked: operation.jsonl" not in str(error):
            raise
    else:
        raise ValueError("missing original operation source was accepted")
    if negative.exists():
        raise ValueError("negative saved proof wrote a receipt")
    source.parent.joinpath("operation.hidden").rename(source)
    return {"format": "c10301-diagnostic-saved-pair-proof-v1",
            "cases": sources, "comparison_sha256": hashlib.sha256(pair_path.read_bytes()).hexdigest(),
            "negative_missing_operation_rejected": True,
            "diagnostic_fixture": True, "physical_acceptance_claimed": False,
            "legal_verdict_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-root", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(prove(args.output_root), sort_keys=True))


if __name__ == "__main__":
    main()
