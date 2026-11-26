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
from precedence_response_audit import audit_response_pair


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
KINDS = ("precedence", "advance", "other_later", "opposite_straight",
         "opposite_intends_left", "opposite_makes_left", "wide_same_crossing")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2) + "\n")


def write_rows(path, rows):
    Path(path).write_text("".join(json.dumps(row) + "\n" for row in rows))


def reseal(attempt):
    """Keep explicit synthetic perturbations bound to their diagnostic seal."""
    acquisition = json.loads((attempt / "acquisition.json").read_text())
    seal = json.loads((attempt / "capture-seal.json").read_text())
    for name in ORIGINALS:
        digest = sha(attempt / name)
        acquisition[name]["sha256"] = digest
        seal["sources"][name] = digest
    write(attempt / "acquisition.json", acquisition)
    write(attempt / "capture-seal.json", seal)
    exit_receipt = json.loads((attempt / "native-exit.json").read_text())
    exit_receipt["capture_seal_sha256"] = sha(attempt / "capture-seal.json")
    write(attempt / "native-exit.json", exit_receipt)


def prepare_synthetic_response_pair(output):
    """Exercise realized-response audit using labeled synthetic source changes."""
    for kind, request in (("precedence", "brake"), ("advance", "proceed")):
        attempt = output / kind
        controls = [json.loads(line) for line in
                    (attempt / "controller-history.jsonl").read_text().splitlines()]
        for row in controls:
            row["ego_next_tick_request"] = {"request": request if row["frame"] >= 2 else "brake"}
            row["synthetic_response_probe"] = True
        write_rows(attempt / "controller-history.jsonl", controls)
        reseal(attempt)
    try:
        audit_response_pair(output / "precedence", output / "advance", diagnostic=True)
    except ValueError as error:
        if "controller-only response difference lacks realized ego progress" not in str(error):
            raise
    else:
        raise AssertionError("request-only exact pair passed realized-response audit")
    attempt = output / "advance"
    body_path = attempt / "ego-body-history.jsonl"
    bodies = [json.loads(line) for line in body_path.read_text().splitlines()]
    if len(bodies) < 5:
        raise ValueError("synthetic response fixture needs five original-shaped frames")
    for vertex in bodies[3]["body_vertices_xy_m"]:
        vertex[0] += .5
    write_rows(body_path, bodies)
    trace_path = attempt / "trace.jsonl"
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
    if trace[3]["frame"] != bodies[3]["frame"]:
        raise ValueError("synthetic response trace/body frame differs")
    trace[3]["position"]["x"] += .5
    if "position_m" in trace[3]:
        trace[3]["position_m"][0] += .5
    write_rows(trace_path, trace)
    reseal(attempt)


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
    parser.add_argument("--selected", action="store_true",
                        help="retain source-gated selected proof separately from diagnostic proof")
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
    prepare_synthetic_response_pair(output)
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
    response = audit_response_pair(output / "precedence", output / "advance",
                                   diagnostic=True)
    if (response["realized_progress_difference_m"] < .25 or
            response["legal_verdict_claimed"] or not response["diagnostic_fixture"]):
        raise AssertionError("synthetic realized response audit missed its evidence")
    comparisons.append({"comparison_id": "crossing_precedence",
                        "case_ids": [ROOT.name + "__precedence",
                                     ROOT.name + "__advance"],
                        "synthetic_response_probe": True,
                        "request_only_negative_rejected": True,
                        "realized_progress_difference_m": response["realized_progress_difference_m"],
                        "physical_acceptance_claimed": False,
                        "independent_audit_passed": True})
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
    proof_name = "delivery-selected-audit-proof.json" if args.selected else "delivery-diagnostic-audit-proof.json"
    write(ROOT / proof_name, {
        "format": "c125714-delivery-selected-audit" if args.selected else
                  "c125714-delivery-diagnostic-audit", "cases": results,
        "comparisons": comparisons,
        "diagnostic_only": True, "physical_acceptance_claimed": False})


if __name__ == "__main__":
    main()
