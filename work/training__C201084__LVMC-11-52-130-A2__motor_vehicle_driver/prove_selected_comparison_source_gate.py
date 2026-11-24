"""Recompute three selected CPU comparisons and bind their retained sources.

The output is a diagnostic preparation receipt. Canonical comparison acceptance
must still fail closed until original Native and source reviews are supplied.
"""

import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path

from audit_lead_position import audit as audit_lead_position
from audit_final_reference_contrast import audit as audit_reference_contrast
from audit_final_traffic_pair import audit as audit_traffic_pair
from audit_selected_source_packet_integrity import verify as verify_packets


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ASSIGNMENT = HERE.name
SOURCE_NAMES = ("acquisition-provenance.json", "native-actors.jsonl",
                "native-survey-readback.json", "video_frames.jsonl")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def source_gate(group, override=None):
    case_id = ASSIGNMENT + "__" + group
    index = read(HERE / "selected-source-review-index.json")
    row = next(item for item in index["selected_cases"] if item["case_id"] == case_id)
    event = read(HERE / f"selected-{group}-source-event.json")
    context = read(HERE / f"selected-{group}-context-pending.json")
    posting = read(HERE / f"selected-{group}-posting-pending.json")
    require(row["event_sha256"] == sha(HERE / f"selected-{group}-source-event.json"), "selected event packet changed")
    require(row["context_sha256"] == sha(HERE / f"selected-{group}-context-pending.json"), "selected context packet changed")
    require(row["posting_sha256"] == sha(HERE / f"selected-{group}-posting-pending.json"), "selected posting packet changed")
    require(context["event_evidence_sha256"] == row["event_sha256"] and
            posting["event_evidence_sha256"] == row["event_sha256"], "selected source review join changed")
    attempt = REPO / ".runtime-work" / f"c201084-final-{group}-primary-compatibility"
    saved = REPO / ".runtime-work" / f"c201084-final-{group}-primary-saved/v0001/processing.json"
    receipt = read(saved)
    selection = read(attempt / "candidate-selection.json")
    require(receipt["passed"] and receipt["recorded_only"] and receipt["originals_preserved"] and
            not receipt["physical_acceptance_claimed"] and not receipt["legal_acceptance_claimed"],
            "selected saved lifecycle differs")
    require(selection["case_id"] == case_id and selection["candidate_id"] == "primary" and
            selection["manifest_sha256"] == index["manifest_sha256"], "selected candidate differs")
    for name in SOURCE_NAMES:
        actual = override if name == "native-actors.jsonl" and override is not None else attempt / name
        expected = event["source_sha256"][name]
        require(sha(actual) == expected, f"selected retained source changed: {group}/{name}")
        require(receipt["original_source_hashes"][name] == expected,
                f"selected saved source changed: {group}/{name}")
    require(event["source_kind"] == "synthetic_native_sample" and
            not event["property_status_verified"] and
            not event["driver_attendance_verified"] and
            not event["original_posting_or_designation_verified"],
            "selected source review claims original legal context")
    return {"case_id": case_id, "selection_sha256": sha(attempt / "candidate-selection.json"),
            "saved_processing_sha256": sha(saved), "source_event_sha256": row["event_sha256"],
            "native_actors_sha256": event["source_sha256"]["native-actors.jsonl"]}


def main():
    index = read(HERE / "selected-source-review-index.json")
    packets = {}
    for row in index["selected_cases"]:
        group = row["case_id"].removeprefix(ASSIGNMENT + "__")
        packets[group] = tuple(read(HERE / f"selected-{group}-{suffix}.json")
                               for suffix in ("source-event", "context-pending", "posting-pending"))
    verify_packets(index, packets)
    rows = {group: source_gate(group) for group in packets}
    main_comparison = audit_reference_contrast()
    lead_position = audit_lead_position(
        REPO / ".runtime-work/c201084-final-conflict-primary-compatibility",
        REPO / ".runtime-work/c201084-final-clear-primary-compatibility")
    lead_presence = audit_traffic_pair()
    audits = (main_comparison, lead_position, lead_presence)
    require(all(item["passed"] and item["diagnostic_only"] for item in audits),
            "selected comparison diagnostic failed")
    require(main_comparison["comparison"]["comparison_id"] == ASSIGNMENT + "__comparison_main" and
            lead_position["comparison_id"] == ASSIGNMENT + "__comparison_lead_position" and
            lead_presence["near_lead_brake_request_frames"] == 1 and
            lead_presence["absent_lead_brake_request_frames"] == 0,
            "selected comparison source outcomes differ")
    comparison_ids = [ASSIGNMENT + suffix for suffix in
                      ("__comparison_main", "__comparison_lead_position", "__comparison_lead_presence")]
    source = REPO / ".runtime-work/c201084-final-reference-primary-compatibility/native-actors.jsonl"
    scratch = REPO / ".runtime-work"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="c201084-source-negative-", dir=scratch) as temporary:
        altered = Path(temporary) / "native-actors.jsonl"
        shutil.copyfile(source, altered)
        with altered.open("ab") as stream:
            stream.write(b"\n")
        try:
            source_gate("reference", override=altered)
        except ValueError as error:
            require("selected retained source changed" in str(error), "wrong changed-source rejection")
            negative = str(error)
        else:
            raise AssertionError("changed Native source was accepted")
    require(not index["original_native_observed"] and not index["original_context_review_bound"]
            and not index["original_posting_review_bound"], "canonical original-source gate wrongly open")
    print(json.dumps({"format": "c201084-selected-comparison-source-gate-v1",
                      "passed": True, "diagnostic_only": True,
                      "canonical_comparison_accepted": False,
                      "manifest_sha256": sha(HERE / "execution-manifest.json"),
                      "source_index_sha256": sha(HERE / "selected-source-review-index.json"),
                      "selected_source_cases": rows,
                      "comparison_ids": comparison_ids,
                      "changed_source_rejection": negative,
                      "original_native_observed": False,
                      "physical_or_legal_completion_claimed": False}, indent=2))


if __name__ == "__main__":
    main()
