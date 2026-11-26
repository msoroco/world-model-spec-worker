"""Finalize sealed signal-entry motion from saved bytes without Native execution."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from ped_entry import CASES, measure_original
from delivery_audit import ASSIGNMENT, SOURCES, linked, sha


def process(root: Path, site_ref: dict, trace_ref: dict, case_id: str,
            output: Path, diagnostic_fixture: bool = False) -> dict:
    root = Path(root).resolve()
    output = Path(output).resolve()
    if output.exists() or output.is_relative_to(root) or root.is_relative_to(output):
        raise ValueError("fresh derived output outside saved acquisition required")
    case = next((item for item in CASES if case_id == ASSIGNMENT + "__" + item.case_id), None)
    if case is None:
        raise ValueError("exact selected signal-entry case required")
    site_path = linked(root, site_ref)
    trace_path = linked(root, trace_ref)
    site = json.loads(site_path.read_text(encoding="utf-8"))
    trace = json.loads(trace_path.read_text(encoding="utf-8"))
    if (trace.get("case_id") != case_id or
            bool(trace.get("diagnostic_fixture")) != diagnostic_fixture or
            site.get("diagnostic_fixture") is True and not diagnostic_fixture or
            site.get("reviewed_original_site") is not True and not diagnostic_fixture):
        raise ValueError("original versus diagnostic source provenance differs")
    scene = site.get("scenes", {}).get(case.case_id)
    if not isinstance(scene, dict):
        raise ValueError("saved reviewed exact scene missing")
    for name in SOURCES:
        source_ref = site.get("source_refs", {}).get(name)
        linked(root, source_ref)
        if scene.get(name + "_source_sha256") != source_ref["sha256"]:
            raise ValueError("saved scene source binding differs: " + name)
    measured = measure_original(trace.get("frames", []), scene, case)
    if sha(site_path) != site_ref["sha256"] or sha(trace_path) != trace_ref["sha256"]:
        raise ValueError("saved acquisition changed during processing")
    output.mkdir(parents=True)
    measure_path = output / "measurement.json"
    measure_path.write_text(json.dumps(measured, indent=2, sort_keys=True) + "\n",
                            encoding="utf-8")
    receipt = {"format": "c227824-recorded-only-processing-v1", "case_id": case_id,
               "source_kind": "synthetic_software_fixture" if diagnostic_fixture
               else "original_native_attempt", "site_sha256": site_ref["sha256"],
               "trace_sha256": trace_ref["sha256"],
               "measurement_sha256": sha(measure_path), "original_frame_count": 900,
               "analysis_complete": True, "physical_acceptance": False,
               "legal_verdict_claimed": False}
    (output / "processing-receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority-root", type=Path, required=True)
    parser.add_argument("--site-ref", type=Path, required=True)
    parser.add_argument("--trace-ref", type=Path, required=True)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--diagnostic-fixture", action="store_true")
    args = parser.parse_args()
    print(json.dumps(process(args.authority_root,
                             json.loads(args.site_ref.read_text(encoding="utf-8")),
                             json.loads(args.trace_ref.read_text(encoding="utf-8")),
                             args.case_id, args.output, args.diagnostic_fixture),
                     sort_keys=True))


if __name__ == "__main__":
    main()
