"""Check source-bound accepted-context review and uncovered case decisions."""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
PLAN = HERE / "case-plan.json"
ASSIGNMENT = ROOT / "inputs" / HERE.name / "assignment.json"
CONTEXT = ROOT / "inputs" / HERE.name / "review-context" / "review.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check(plan: dict) -> dict:
    assignment = json.loads(ASSIGNMENT.read_text())
    context = json.loads(CONTEXT.read_text())
    review = plan["evidence_review"]
    expected = {
        row["recording_id"]: row
        for comparison in context["comparisons"]
        for row in comparison["cases"]
    }
    if len(expected) != 4 or len(review["facts"]) != 4:
        raise ValueError("four accepted memberships require an individual review")
    if context["law"]["text"] != assignment["law"]["text"]:
        raise ValueError("review context changed the exact law")
    if {r["recording_id"] for r in review["facts"]} != set(expected):
        raise ValueError("accepted membership left unreviewed or invented")
    for fact in review["facts"]:
        expected_case = expected[fact["recording_id"]]
        if fact["case_id"] != expected_case["case_id"]:
            raise ValueError("review fact bound to another accepted case")
        if fact["receipt_sources"] != expected_case["receipt_sources"]:
            raise ValueError("review changed accepted receipt inventory")
        if fact["qualified_reuse"] or fact["worker_original_media_reviewed"]:
            raise ValueError("context-only review cannot certify original reuse")
        if not fact["demonstrated_fact"] or not fact["limitations"]:
            raise ValueError("accepted fact or limit absent")
        refs = fact["sources"]
        if not refs or any(
            sha(ROOT / ref["path"]) != ref["sha256"] for ref in refs
        ):
            raise ValueError("review fact lacks current source hashes")
    gap_ids = {gap["id"] for gap in review["gaps"]}
    if gap_ids != {"crest_matched_grade_visibility", "curve_matched_geometry_visibility"}:
        raise ValueError("crest and curve gaps must remain distinct")
    for gap in review["gaps"]:
        source = gap["source"]
        if sha(ROOT / source["path"]) != source["sha256"]:
            raise ValueError("gap lacks current review-context source")
        if not gap["requirement"] or not gap["why_existing_insufficient"]:
            raise ValueError("gap is not explained")
    cases = {case["case_id"].rsplit("__", 1)[-1]: case for case in plan["cases"]}
    if set(cases) != {"probe_01", "probe_02", "probe_03"}:
        raise ValueError("draft case inventory changed")
    for suffix, expected_gaps in {
        "probe_01": {"crest_matched_grade_visibility", "curve_matched_geometry_visibility"},
        "probe_02": {"crest_matched_grade_visibility"},
        "probe_03": {"curve_matched_geometry_visibility"},
    }.items():
        if set(cases[suffix]["gap_ids"]) != expected_gaps:
            raise ValueError("case does not address its reviewed evidence gap")
    return {"accepted_memberships_reviewed": 4, "proven_exact_reuses": 0,
            "uncovered_gaps": sorted(gap_ids), "planned_cases": len(cases)}


def prove() -> dict:
    plan = json.loads(PLAN.read_text())
    measured = check(plan)
    rejected = []
    mutations = {
        "missing_membership": lambda d: d["evidence_review"]["facts"].pop(),
        "false_reuse": lambda d: d["evidence_review"]["facts"][0].update(qualified_reuse=True),
        "stale_source_hash": lambda d: d["evidence_review"]["facts"][0]["sources"][0].update(sha256="0" * 64),
        "invented_receipt": lambda d: d["evidence_review"]["facts"][0].update(receipt_sources=[{"path": "unreviewed", "sha256": "0" * 64}]),
        "missing_curve_gap": lambda d: d["evidence_review"]["gaps"].pop(),
        "misbound_curve_case": lambda d: d["cases"][2].update(gap_ids=["crest_matched_grade_visibility"]),
    }
    for name, mutate in mutations.items():
        changed = copy.deepcopy(plan)
        mutate(changed)
        try:
            check(changed)
        except ValueError as error:
            rejected.append({"mutation": name, "error": str(error)})
        else:
            raise AssertionError("accepted altered evidence review: " + name)
    proof = {"format": "c104496-source-context-review-proof-v1",
             "assignment_id": HERE.name, "plan_sha256": sha(PLAN),
             "assignment_sha256": sha(ASSIGNMENT), "context_sha256": sha(CONTEXT),
             "measured": measured, "negative_rejections": rejected,
             "passed": len(rejected) == len(mutations),
             "physical_originals_reviewed": False}
    (HERE / "evidence-review-proof.json").write_text(
        json.dumps(proof, indent=2, sort_keys=True) + "\n")
    return proof


if __name__ == "__main__":
    print(json.dumps(prove(), sort_keys=True))
