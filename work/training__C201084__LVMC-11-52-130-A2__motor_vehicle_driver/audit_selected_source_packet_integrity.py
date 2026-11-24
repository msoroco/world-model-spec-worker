"""Independently check selected diagnostic source packets against the final plan."""

import copy
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
ASSIGNMENT = ROOT.name


def read(name):
    return json.loads((ROOT / name).read_text())


def digest(name):
    return hashlib.sha256((ROOT / name).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify(index, packets):
    manifest = read("execution-manifest.json")
    plan = read("case-plan.json")
    require(index["manifest_sha256"] == digest("execution-manifest.json"), "selected manifest hash mismatch")
    require(index["diagnostic_only"] and not index["original_native_observed"], "diagnostic provenance changed")
    require(not index["original_context_review_bound"] and not index["original_posting_review_bound"], "unsupported context/posting claim")
    planned = {case["case_id"] for case in plan["cases"]}
    manifested = {case["case_id"] for case in manifest["cases"]}
    selected = {row["case_id"] for row in index["selected_cases"]}
    require(len(selected) == 8 and selected == planned == manifested, "selected case set mismatch")
    overlaps = {}
    for row in index["selected_cases"]:
        case_id = row["case_id"]
        group = case_id.removeprefix(ASSIGNMENT + "__")
        require(group in packets, "missing selected source packet")
        event, context, posting = packets[group]
        for kind, packet in (("event", event), ("context", context), ("posting", posting)):
            name = f"selected-{group}-{'source-event' if kind == 'event' else kind + '-pending'}.json"
            require(row[f"{kind}_sha256"] == digest(name), f"{kind} file hash mismatch")
            require(packet["case"] == group, f"{kind} case mismatch")
            require(not packet["physical_or_legal_completion_claimed"], f"{kind} claims physical/legal completion")
        require(event["source_kind"] == "synthetic_native_sample" and event["diagnostic_fixture"], "event source is not diagnostic")
        require(event["frames"] == 600 and event["capture_hz"] == 20, "event frame contract mismatch")
        require(not event["driver_attendance_verified"] and not event["property_status_verified"], "unsupported attendance/property claim")
        require(not event["original_posting_or_designation_verified"] and not event["statutory_necessity_verified"], "unsupported posting/necessity claim")
        require(context["event_evidence_sha256"] == row["event_sha256"], "context event join mismatch")
        require(posting["event_evidence_sha256"] == row["event_sha256"], "posting event join mismatch")
        require(context["camera_source_sha256"] == posting["camera_source_sha256"], "context/posting camera join mismatch")
        require(not context["original_context_review_bound"] and not posting["original_posting_review_bound"], "original source falsely bound")
        require(not context["property_legally_verified"] and not posting["legal_applicability_verified"], "unsupported legal conclusion")
        require(len(event["source_sha256"]) == 4 and all(len(value) == 64 for value in event["source_sha256"].values()), "retained source hash list incomplete")
        overlaps[group] = len(event["near_zero_authored_zone_overlap_episodes"])
        require(overlaps[group] == row["near_zero_zone_overlap_episodes"], "zone-overlap index mismatch")
    comparison_pairs = {frozenset(case_id.removeprefix(ASSIGNMENT + "__") for case_id in item["case_ids"]) for item in plan["comparisons"]}
    require(comparison_pairs == {frozenset(("reference", "contrast")), frozenset(("conflict", "clear")), frozenset(("near_lead", "absent_lead"))}, "comparison pair mismatch")
    require(overlaps["reference"] > 0 and overlaps["contrast"] == 0, "main diagnostic occupancy contrast missing")
    return overlaps


def main():
    index = read("selected-source-review-index.json")
    packets = {}
    for row in index["selected_cases"]:
        group = row["case_id"].removeprefix(ASSIGNMENT + "__")
        packets[group] = tuple(read(f"selected-{group}-{suffix}.json") for suffix in ("source-event", "context-pending", "posting-pending"))
    overlaps = verify(index, packets)
    rejected = []
    for label, mutate in (
        ("event_context_join", lambda p: p["reference"][1].__setitem__("event_evidence_sha256", "0" * 64)),
        ("unsupported_original_claim", lambda p: p["reference"][2].__setitem__("original_posting_review_bound", True)),
        ("event_frame_count", lambda p: p["reference"][0].__setitem__("frames", 599)),
    ):
        altered = copy.deepcopy(packets)
        mutate(altered)
        try:
            verify(index, altered)
        except ValueError as error:
            rejected.append({"mutation": label, "error": str(error)})
        else:
            raise AssertionError(f"mutation accepted: {label}")
    print(json.dumps({"format": "c201084-selected-source-packet-integrity-v1", "passed": True,
                      "manifest_sha256": digest("execution-manifest.json"),
                      "source_index_sha256": digest("selected-source-review-index.json"),
                      "case_count": len(overlaps), "comparison_pair_count": 3,
                      "zone_overlap_diagnostic_counts": overlaps,
                      "negative_rejections": rejected, "diagnostic_only": True,
                      "original_native_observed": False, "legal_completion_claimed": False}, indent=2))


if __name__ == "__main__":
    main()
