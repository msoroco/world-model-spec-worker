"""Select the six uncovered railroad, one-way and traversal delivery cases.

Preserve the two intersection 100-foot drafts until accepted-original source
equivalence is established. This builder never asserts physical acceptance.
"""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCES = (
    ("draft-statutory-execution-manifest.json", ("rail_reference", "rail_contrast",
                                                   "oneway_absent", "oneway_present")),
    ("draft-traversal-execution-manifest.json", ("traversal_reference",
                                                   "traversal_contrast")),
)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n")


def main():
    frozen = ROOT / "inputs" / HERE.name / "assignment.json"
    assignment = json.loads(frozen.read_text())
    law = assignment["law_record"]["text"]
    assert all(term in law for term in ("railroad grade crossing", "intersection",
                                        "one-way highway"))
    accepted = assignment["local_snapshot"]["memberships"]["full-train"]
    assert len(accepted) == 3 and all("100-" in row["case_id"] for row in accepted)
    assert not any(any(term in row["case_id"].lower()
                       for term in ("rail", "oneway", "traversal")) for row in accepted)
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    gaps = {row["id"] for row in plan["evidence_review"]["gaps"]}
    assert {"accepted_100ft_equivalence", "railroad_and_traversal",
            "oneway_exception"} <= gaps
    selected_suffixes = {suffix for _, suffixes in SOURCES for suffix in suffixes}
    assert len(selected_suffixes) == 6
    for case in plan["cases"]:
        suffix = case["case_id"].rsplit("__", 1)[-1]
        if suffix in selected_suffixes:
            case["case_description"] = case["case_description"].replace(
                "Unselected ", "Selected CPU preparation for ", 1)
            case["planning_status"] = "selected_preparation_incomplete"
        else:
            assert suffix in ("reference", "contrast")
    write(plan_path, plan)
    entries = []
    source_hashes = {}
    runtime_sha = None
    for filename, suffixes in SOURCES:
        path = HERE / filename
        draft = json.loads(path.read_text())
        source_hashes[filename] = sha(path)
        runtime_sha = runtime_sha or draft["runtime_manifest_sha256"]
        assert draft["runtime_manifest_sha256"] == runtime_sha
        for suffix in suffixes:
            case_id = HERE.name + "__" + suffix
            entry = copy.deepcopy(next(row for row in draft["cases"]
                                       if row["case_id"] == case_id))
            assert len(entry["candidates"]) == 3
            for candidate in (entry, *entry["candidates"]):
                assert sha(HERE / candidate["construction"]) == candidate["construction_sha256"]
            entry["kind"] = "delivery"
            entry["preparation_status"] = "selected_current_proofs_pending"
            entries.append(entry)
    output = HERE / "execution-manifest.json"
    manifest = {"format": "worker-execution-manifest",
                "assignment_id": HERE.name,
                "runtime_manifest_sha256": runtime_sha,
                "status": "partial_selected_current_proofs_pending",
                "selection_review": {
                    "law_input_sha256": sha(frozen),
                    "case_plan_sha256": sha(plan_path),
                    "draft_manifest_sha256": source_hashes,
                    "selected_case_ids": [entry["case_id"] for entry in entries],
                    "withheld_intersection_case_ids": [HERE.name + "__reference",
                                                       HERE.name + "__contrast"],
                    "accepted_intersection_recording_ids": [row["recording_id"] for row in accepted],
                    "accepted_100ft_equivalence_receipt": None,
                    "reason": "No accepted source-backed railroad, one-way or moving intersection-traversal coverage is supplied. The accepted 101/100/99-foot intersection originals are preserved pending source-equivalence review.",
                    "physical_or_legal_acceptance_claimed": False},
                "cases": entries}
    write(output, manifest)
    print(json.dumps({"selected_case_count": len(entries),
                      "candidate_count": sum(1 + len(x["candidates"]) for x in entries),
                      "manifest_sha256": sha(output),
                      "case_plan_sha256": sha(plan_path),
                      "canonical_delivery_ready": False}))


if __name__ == "__main__":
    main()
