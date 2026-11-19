"""Recheck every declared C129731 comparison on current exact CPU attempts."""

import hashlib
import json
import shlex
from pathlib import Path

import comparison_audit as boundary
import crest_branch_comparison as crest
import curve_direction_comparison as curve

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest_path = HERE / "execution-manifest.json"
    manifest = json.loads(manifest_path.read_text())
    declared = {row["comparison_id"]: row for row in
                json.loads((HERE / "case-plan.json").read_text())["comparisons"]}

    def attempt(index):
        command = shlex.split(manifest["cases"][index]["post_capture"]["command"])
        return ROOT / command[command.index("--attempt") + 1]

    reports = {}
    negative_rejections = {}
    for comparison_id, indices in (
        ("curve_visibility_boundary", (0, 1, 2)),
        ("crest_visibility_boundary", (3, 4, 5)),
    ):
        paths = [attempt(index) for index in indices]
        report = boundary.audit_group(comparison_id, paths, diagnostic=True, folder=HERE)
        assert report["software_checks_passed"] and report["passed"] is False
        assert report["case_ids"] == declared[comparison_id]["case_ids"]
        reports[comparison_id] = report
        swapped = [paths[1], paths[0], paths[2]]
        try:
            boundary.audit_group(comparison_id, swapped, diagnostic=True, folder=HERE)
        except ValueError as error:
            negative_rejections[comparison_id] = str(error)
        else:
            raise ValueError("Swapped boundary identities accepted: " + comparison_id)

    canonical = (
        ("at_500ft", (6, 7, 8, 9), crest.audit_canonical_pairs,
         ("canonical-at-approach-b", "canonical-at-near-b", "canonical-at-approach-a", "canonical-at-near-a")),
        ("short_of_500ft", (10, 11, 12, 13), crest.audit_canonical_short_pair,
         ("canonical-short-approach-b", "canonical-short-near-b", "canonical-short-approach-a", "canonical-short-near-a")),
        ("beyond_500ft", (14, 15, 16, 17), crest.audit_canonical_beyond_pairs,
         ("canonical-beyond-approach-b", "canonical-beyond-near-b", "canonical-beyond-approach-a", "canonical-beyond-near-a")),
    )
    for probe, indices, auditor, names in canonical:
        paths = {name: attempt(index) for name, index in zip(names, indices)}
        report = auditor(paths)
        assert report["software_checks_passed"] and report["passed"] is False
        assert len(report["comparisons"]) == 4
        for row in report["comparisons"]:
            matches = [(key, value) for key, value in declared.items()
                       if value["case_ids"] == row["case_ids"]]
            assert len(matches) == 1
            comparison_id, plan = matches[0]
            assert plan["deliberate_differences"] == [row["deliberate_difference"]]
            reports[comparison_id] = {
                "comparison": row,
                "source_sha256": report["source_sha256"],
                "software_checks_passed": True,
                "passed": False,
                "physical_acceptance_claimed": False,
            }
        swapped = dict(paths)
        swapped[names[0]], swapped[names[1]] = swapped[names[1]], swapped[names[0]]
        try:
            auditor(swapped)
        except ValueError as error:
            negative_rejections["crest_" + probe] = str(error)
        else:
            raise ValueError("Swapped crest identities accepted: " + probe)

    for probe, indices in (
        ("short_of_500ft", (18, 19)),
        ("at_500ft", (20, 21)),
        ("beyond_500ft", (22, 23)),
    ):
        paths = {"approach_a": attempt(indices[0]), "approach_b": attempt(indices[1])}
        report = curve.audit(probe, paths)
        comparison_id = report["comparison_id"]
        assert report["software_checks_passed"] and report["passed"] is False
        assert report["case_ids"] == declared[comparison_id]["case_ids"]
        reports[comparison_id] = report
        try:
            curve.audit(probe, {"approach_a": paths["approach_b"],
                                "approach_b": paths["approach_a"]})
        except ValueError as error:
            negative_rejections[comparison_id] = str(error)
        else:
            raise ValueError("Swapped curve identities accepted: " + comparison_id)

    assert set(reports) == set(declared)
    proof = {
        "format": "c129731-current-comparison-cpu-proof",
        "manifest_sha256": sha(manifest_path),
        "comparison_count": len(reports),
        "negative_rejections": negative_rejections,
        "reports": reports,
        "software_checks_passed": True,
        "passed": False,
        "physical_acceptance_claimed": False,
    }
    output = HERE / "current-comparison-proof.json"
    output.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"comparison_count": len(reports),
                      "negative_count": len(negative_rejections),
                      "manifest_sha256": proof["manifest_sha256"],
                      "physical_acceptance_claimed": False}, sort_keys=True))


if __name__ == "__main__":
    main()
