"""Independently audit a saved diagnostic delivery source and its rejection path."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
OUTPUT_ROOT = Path(os.environ.get("SCENARIO_PIPELINE_OUTPUT_ROOT", ""))
if REPO / ".runtime-work" not in OUTPUT_ROOT.resolve().parents:
    raise RuntimeError("Runtime output root must be under .runtime-work")
sys.path[:0] = [str(PACKAGE), str(REPO / "runtime"),
                str(REPO / "runtime/scenario_pipeline")]

from finalize import check_original_join, measure_interaction
from scenario_pipeline.worker_exchange.media import audit as audit_media
from scenario_pipeline.worker_exchange.native_output import validate_result


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(case: str, source: Path, negative: bool) -> dict:
    expected = case
    if case not in (PACKAGE.name + "__probe_a", PACKAGE.name + "__probe_b"):
        raise ValueError("Wrong exact delivery case")
    source = source.resolve()
    if REPO / ".runtime-work" not in source.parents:
        raise ValueError("Saved diagnostic source must be under .runtime-work")
    if negative:
        scratch = REPO / ".runtime-work/c136495-temp"
        with tempfile.TemporaryDirectory(prefix="delivery-negative-c136495-", dir=scratch) as temp:
            folder = Path(temp)
            for name in ("actor-frames.jsonl", "camera-frame-map.jsonl", "rider-binding.json"):
                shutil.copyfile(source / name, folder / name)
            try:
                measure_interaction(folder)
            except ValueError as error:
                if "Missing required source: classification.json" not in str(error):
                    raise
                raise ValueError("Missing required source: classification.json") from error
            raise AssertionError("Missing original classification was accepted")
    result = validate_result(json.loads((source / "result.json").read_text()))
    if result["case_id"] != expected:
        raise ValueError("Wrong exact delivery case")
    if result["provenance_kind"] != "synthetic_fixture" or result.get("physical_acceptance_claimed") is not False:
        raise ValueError("Diagnostic source claimed physical acceptance")
    if result["physical_checks"]["maneuver"]["status"] != "met":
        raise ValueError("Saved source lacks measured physical completion")
    actors = check_original_join(source)
    if len(actors) != 600 or any(set(row["actors"]) != {"ego", "rider"} for row in actors):
        raise ValueError("Missing original subject or rider participant")
    interaction = measure_interaction(source)
    if interaction["value"]["frame_count"] != 600:
        raise ValueError("Rider source did not cover the original recording")
    if any(interaction["value"][key] != "unresolved" for key in
           ("driver_intent", "rider_lawful_status", "causal_interference")):
        raise ValueError("Saved diagnostic inferred a legal condition")
    mapping_sha = sha(source / "video_frames.jsonl")
    inspected = []
    scratch = REPO / ".runtime-work/c136495-temp"
    with tempfile.TemporaryDirectory(prefix="delivery-media-c136495-", dir=scratch) as temp:
        for index, name in enumerate(result["video_references"]):
            receipt = Path(temp) / f"camera-{index}.json"
            audit_media(source / name, 600, mapping_sha256=mapping_sha, receipt=receipt)
            inspected.append(name)
    final = source / "final-decode.json"
    final_receipt = json.loads(final.read_text()) if final.is_file() else {}
    if final_receipt.get("passed") is not True or final_receipt.get("frames") != 600:
        raise ValueError("Missing final decoded video evidence")
    return {"case_id": expected, "checks": ["native_source", "all_participants",
            "time_join", "full_video_decode", "actual_pixels", "physical_completion"],
            "camera_sources": inspected, "frame_count": 600,
            "source_kind": "synthetic_fixture", "legal_outcome_asserted": False,
            "physical_acceptance_claimed": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--negative", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check(args.case, args.source_root, args.negative), sort_keys=True))


if __name__ == "__main__":
    main()
