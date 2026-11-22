"""Exercise seven exact saved-source audits without claiming Native provenance."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil

from delivery_audit import (CAMERAS, ORIGINALS, REVIEW_SOURCES, audit_attempt,
                            audit_media_time, audit_pair)


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
KINDS = ("precedence", "advance", "other_later", "opposite_straight",
         "opposite_intends_left", "opposite_makes_left", "wide_same_crossing")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def prepare(origin, attempt, case_id):
    attempt.mkdir(parents=True)
    for name in ("trace.jsonl", "video_frames.jsonl", "road.xodr",
                 "intersection-context.json", "ego-body-history.jsonl",
                 "other-body-history.jsonl", *CAMERAS):
        shutil.copyfile(origin / name, attempt / name)
    trace = [json.loads(line) for line in (attempt / "trace.jsonl").read_text().splitlines()
             if line.strip()]
    (attempt / "controller-history.jsonl").write_text("".join(
        json.dumps({"frame": row["frame"], "time_s": row["time_s"],
                    "diagnostic_only": True}) + "\n" for row in trace))
    (attempt / "carla_recorder.log").write_text("Synthetic CPU source; no CARLA recording.\n")
    context = json.loads((attempt / "intersection-context.json").read_text())
    law = context["law_context"]
    if law["map_source"] != sha(attempt / "road.xodr"):
        raise ValueError("diagnostic map source differs")
    for key, retained in REVIEW_SOURCES.items():
        source = attempt / retained
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("Synthetic CPU-only shared " + key + "\n")
        law[key] = {"source_path": key + ".txt", "source_sha256": sha(source),
                    "reviewer": "synthetic diagnostic author",
                    "source_citation": "synthetic fixture only"}
    packet = {"crossing": context["crossing"], "law_context": law}
    write(attempt / "reviewed-context.json", packet)
    context["reviewed_context_sha256"] = sha(attempt / "reviewed-context.json")
    write(attempt / "intersection-context.json", context)
    write(attempt / "acquisition-provenance.json", {
        "provenance_kind": "synthetic_fixture", "diagnostic_fixture": True,
        "reviewed_context_sha256": sha(attempt / "reviewed-context.json")})
    hashes = {name: sha(attempt / name) for name in ORIGINALS}
    write(attempt / "acquisition.json", {
        name: {"kind": "original_native", "sha256": value} for name, value in hashes.items()})
    write(attempt / "capture-seal.json", {
        "format": "worker-sealed-capture", "diagnostic_fixture": True,
        "frames": len(trace),
        "events": ["capture_finished", "encoders_closed", "restoration_verified"],
        "restoration": {"restored": True},
        "encoder_exit_codes": {name.removesuffix(".mkv"): 0 for name in CAMERAS},
        "sources": hashes})
    write(attempt / "native-exit.json", {
        "event": "native_exit", "capture_seal_sha256": sha(attempt / "capture-seal.json"),
        "native_process_exit_code": 0, "capture_command_failed": False})
    return len(trace)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--compat-root", required=True)
    parser.add_argument("--output-root", required=True)
    args = parser.parse_args()
    base = (REPO / ".runtime-work").resolve()
    runtime_output = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]).resolve()
    compat, output = Path(args.compat_root).resolve(), Path(args.output_root).resolve()
    if any(not path.is_relative_to(base) for path in (runtime_output, compat, output)):
        raise ValueError("diagnostic paths must stay under .runtime-work")
    output.mkdir(parents=True, exist_ok=False)
    results = []
    for kind in KINDS:
        case_id = ROOT.name + "__" + kind
        attempt = output / kind
        frames = prepare(compat / kind, attempt, case_id)
        decoded = audit_media_time(attempt, frames)
        audited = audit_attempt(attempt, diagnostic=True)
        if (set(decoded) != set(CAMERAS) or
                audited["measurements"]["legal_judgment"] != "unresolved" or
                audited["physical_acceptance_claimed"]):
            raise AssertionError("diagnostic audit overclaimed or omitted sources")
        try:
            audit_attempt(attempt)
        except ValueError as error:
            if "original Native acquisition required" not in str(error):
                raise
        else:
            raise AssertionError("synthetic sources passed Native delivery audit")
        results.append({"case_id": case_id, "diagnostic_only": True,
                        "decoded_frames": decoded, "native_provenance_rejected": True,
                        "changed_source_rejected": True,
                        "physical_acceptance_claimed": False})
        print(case_id, "four-camera decode and audit negatives passed", flush=True)
    comparison_specs = (
        ("crossing_entry_order", "advance", "other_later", ("entry_order",)),
        ("opposite_intention", "opposite_straight", "opposite_intends_left",
         ("left_turn_intent",)),
        ("opposite_actual_left", "opposite_intends_left", "opposite_makes_left",
         ("left_turn_realized",)),
        ("separate_roadway_intersection", "precedence", "wide_same_crossing",
         ("crossing_id", "roadway_id", "ego_approach_direction")),
    )
    comparisons = []
    for comparison_id, left, right, differences in comparison_specs:
        observed = audit_pair(output / left, output / right, differences,
                              diagnostic=True)
        if (observed["comparison"]["declared_differences"] != sorted(differences) or
                observed["legal_verdict_claimed"]):
            raise AssertionError("independent pair audit missed a comparison")
        try:
            audit_pair(output / left, output / right, ("devices",), diagnostic=True)
        except ValueError as error:
            if not any(phrase in str(error) for phrase in
                       ("undeclared difference", "fixed crossing changed")):
                raise
        else:
            raise AssertionError("undeclared pair difference passed")
        comparisons.append({"comparison_id": comparison_id,
                            "case_ids": [ROOT.name + "__" + left,
                                         ROOT.name + "__" + right],
                            "declared_differences": sorted(differences),
                            "independent_audit_passed": True,
                            "undeclared_difference_rejected": True})
        print(comparison_id, "independent comparison passed", flush=True)
    try:
        audit_pair(output / "precedence", output / "advance",
                   ("ego_response_request",), diagnostic=True)
    except ValueError as error:
        if "unsupported declared comparison variable" not in str(error):
            raise
    else:
        raise AssertionError("authored request was mistaken for realized motion")
    comparisons.append({"comparison_id": "crossing_precedence",
                        "case_ids": [ROOT.name + "__precedence",
                                     ROOT.name + "__advance"],
                        "authored_request_only": True,
                        "realized_response_claimed": False,
                        "independent_audit_passed": False})
    for kind in KINDS:
        source = output / kind / REVIEW_SOURCES["device_inventory_source"]
        source.write_bytes(source.read_bytes() + b"tampered\n")
        try:
            audit_attempt(output / kind, diagnostic=True)
        except ValueError as error:
            if "original source missing or changed" not in str(error):
                raise
        else:
            raise AssertionError("changed original device source passed delivery audit")
    write(ROOT / "delivery-diagnostic-audit-proof.json", {
        "format": "c125714-delivery-diagnostic-audit", "cases": results,
        "comparisons": comparisons,
        "diagnostic_only": True, "physical_acceptance_claimed": False})


if __name__ == "__main__":
    main()
