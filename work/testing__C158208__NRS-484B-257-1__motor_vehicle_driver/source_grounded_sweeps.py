"""Validate physical sweep proposals against reviewed original source bytes.

The author of an original site supplies feasible engineering ranges. This
checker binds each range to a reviewed survey and never supplies a legal
threshold or fabricates a numerical range from an absent site.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from build_semantic_proposals import JUDGMENTS, LAW
from native_attempt import verify_review_sources
from source_tick_capture import verify_seal
from statutory_branch_measurement import measure_branch


def _finite_number(value, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value):
        raise ValueError(name + " must be a finite number")
    return float(value)


def verify(site_path: Path, sweep_path: Path) -> dict:
    site_path, sweep_path = Path(site_path), Path(sweep_path)
    site = json.loads(site_path.read_text())
    if (site.get("cell_id") != "C158208" or site.get("review_status") != "reviewed" or
            site.get("diagnostic_fixture") is True):
        raise ValueError("original reviewed C158208 site required for physical sweeps")
    source_hashes = verify_review_sources(site, site_path, diagnostic_fixture=False)
    proposal = json.loads(sweep_path.read_text())
    if (proposal.get("site_sha256") != hashlib.sha256(site_path.read_bytes()).hexdigest() or
            proposal.get("law_id") != LAW or proposal.get("legal_cutoff") is not None):
        raise ValueError("source-bound sweep identity or legal cutoff differs")
    specs = proposal.get("sweep_specs")
    phrases = [phrase for phrase, _, _ in JUDGMENTS]
    if not isinstance(specs, list) or len(specs) != len(phrases):
        raise ValueError("one source-grounded sweep per statutory judgment required")
    found = set()
    for spec in specs:
        ref = spec.get("judgment_refs")
        if not isinstance(ref, list) or len(ref) != 1:
            raise ValueError("one exact judgment reference per sweep required")
        phrase = ref[0].get("phrase")
        if phrase not in phrases or phrase in found or ref[0].get("note") != JUDGMENTS[phrases.index(phrase)][1]:
            raise ValueError("duplicate or altered statutory judgment reference")
        found.add(phrase)
        if (spec.get("status") != "complete" or spec.get("target_law_id") != LAW or
                spec.get("mode") != "one_dimensional" or
                not isinstance(spec.get("axes"), list) or len(spec["axes"]) != 1):
            raise ValueError("one complete physical axis required per judgment")
        axis = spec["axes"][0]
        minimum = _finite_number(axis.get("min"), "sweep minimum")
        maximum = _finite_number(axis.get("max"), "sweep maximum")
        spacing = _finite_number(axis.get("spacing"), "sweep spacing")
        if minimum >= maximum or spacing <= 0 or spacing > maximum - minimum:
            raise ValueError("sweep range and spacing must be feasible")
        for key in ("variable", "observable", "unit", "range_rationale", "spacing_rationale"):
            if not isinstance(axis.get(key), str) or not axis[key].strip():
                raise ValueError("sweep axis lacks " + key)
        measurement = axis.get("measurement")
        if not isinstance(measurement, dict) or any(not measurement.get(k)
                for k in ("method", "time_window", "statistic")):
            raise ValueError("source-grounded sweep measurement required")
        evidence = axis.get("feasibility_evidence")
        if not isinstance(evidence, dict):
            raise ValueError("source-grounded feasibility evidence required")
        survey = evidence.get("survey")
        if survey not in source_hashes or evidence.get("sha256") != source_hashes[survey]:
            raise ValueError("sweep feasibility differs from original survey source")
        if not isinstance(evidence.get("observation"), str) or not evidence["observation"].strip():
            raise ValueError("survey observation explaining sweep bounds required")
        if not isinstance(spec.get("recording_description"), dict) or not isinstance(spec.get("variable_assignments"), dict):
            raise ValueError("complete sweep recording and variable assignments required")
        for mark in spec.get("landmarks", []):
            if (mark.get("purpose") != "coverage_landmark" or
                    mark.get("source") not in source_hashes or
                    mark.get("source_sha256") != source_hashes[mark["source"]]):
                raise ValueError("coverage landmark lacks original survey binding")
            _finite_number(mark.get("value"), "coverage landmark")
    return {"format": "c158208-source-grounded-sweep-verification-v1",
            "site_sha256": proposal["site_sha256"],
            "sweep_sha256": hashlib.sha256(sweep_path.read_bytes()).hexdigest(),
            "judgment_phrases": phrases, "source_hashes": source_hashes,
            "legal_status": "unresolved"}


def measure_realization(attempt: Path, site_path: Path, sweep_path: Path,
                        case_id: str, *, diagnostic_fixture: bool = False) -> dict:
    """Measure a selected physical axis from sealed ticks, without legal labels."""
    verified = verify(site_path, sweep_path)
    attempt = Path(attempt)
    packet = verify_seal(attempt)
    if not diagnostic_fixture and len(packet["samples"]) != 900:
        raise ValueError("original sweep realization requires 900 sealed Native ticks")
    identity = json.loads((attempt / "capture-identity.json").read_text())
    if (identity.get("case_id") != case_id or
            identity.get("site_packet_sha256") != verified["site_sha256"] or
            identity.get("provenance_kind") !=
            ("synthetic_fixture" if diagnostic_fixture else "original_capture")):
        raise ValueError("sweep realization capture identity or site differs")
    site = json.loads(Path(site_path).read_text())
    measured = measure_branch(packet, site, case_id)
    samples = measured["observed_history"]
    available = {
        "minimum_approach_speed_mps": measured["minimum_approach_speed_mps"],
        "stopping_reference_station_m": measured["reference_station_m"],
        "through_center_station_at_ego_entry_m": next(
            item["through_center_station_m"] for item in samples
            if item["frame"] == measured["ego_entry_frame"]),
        "through_center_station_at_reference_m": next(
            item["through_center_station_m"] for item in samples
            if item["frame"] == measured["reference_crossing_frame"]),
    }
    realized = []
    for spec in json.loads(Path(sweep_path).read_text())["sweep_specs"]:
        axis = spec["axes"][0]
        observable = axis["observable"]
        if observable not in available:
            raise ValueError("unsupported sealed-tick sweep observable: " + observable)
        value = available[observable]
        realized.append({"sweep_id": spec["sweep_id"], "observable": observable,
                         "unit": axis["unit"], "value": value,
                         "inside_planned_engineering_range": axis["min"] <= value <= axis["max"],
                         "legal_status": "unresolved"})
    return {"format": "c158208-source-grounded-sweep-realization-v1",
            "case_id": case_id, "diagnostic_fixture": diagnostic_fixture,
            "site_sha256": verified["site_sha256"],
            "sweep_sha256": verified["sweep_sha256"],
            "original_tick_count": len(packet["samples"]),
            "realized_axes": realized, "legal_status": "unresolved"}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--site", type=Path, required=True)
    parser.add_argument("--sweeps", type=Path, required=True)
    parser.add_argument("--attempt", type=Path)
    parser.add_argument("--case")
    parser.add_argument("--diagnostic-fixture", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError("sweep receipt already exists")
    if bool(args.attempt) != bool(args.case):
        raise ValueError("attempt and exact case must be supplied together")
    receipt = (measure_realization(args.attempt, args.site, args.sweeps, args.case,
                                   diagnostic_fixture=args.diagnostic_fixture)
               if args.attempt else verify(args.site, args.sweeps))
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n")
    print(receipt["format"])
