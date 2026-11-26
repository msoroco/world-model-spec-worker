"""Exercise positive and negative source-shaped release comparisons on CPU."""

import json
import shutil
import tempfile
from pathlib import Path

from audit_school_release_comparison import GROUPS, audit


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def prove():
    results = []
    for group, suffixes in GROUPS.items():
        sources = {suffix: REPO / ".runtime-work" /
                   ("c394563-variant-physical-source-" + suffix + "-v2")
                   for suffix in suffixes}
        positive = audit(group, sources)
        output = ROOT / "proofs" / ("release-comparison-" + group + ".json")
        output.write_text(json.dumps(positive, indent=2) + "\n")
        negatives = []
        with tempfile.TemporaryDirectory(dir=REPO / ".runtime-work",
                                         prefix="c394563-release-negative-") as temporary:
            changed = Path(temporary) / "changed"
            shutil.copytree(sources[suffixes[-1]], changed)
            altered = dict(sources)
            altered[suffixes[-1]] = changed

            def reject(name, expected):
                try:
                    audit(group, altered)
                except ValueError as error:
                    if expected not in str(error):
                        raise
                    negatives.append({"name": name, "expected_error": expected})
                else:
                    raise AssertionError("Release comparison negative passed: " + name)

            road = changed / "road.xodr"
            original_road = road.read_text()
            road.write_text(original_road + "\nchanged diagnostic source\n")
            reject("changed_road", "Fixed school warning source differs")
            road.write_text(original_road)

            rows_path = changed / "native-rows.jsonl"
            rows = [json.loads(line) for line in rows_path.read_text().splitlines()]
            rows[250]["release_event"] = "unverified"
            rows_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            reject("changed_release", "Requested release event")
            rows[250]["release_event"] = positive["case_ids"][-1].rsplit("__", 1)[1]
            if suffixes[-1] == "probe_1":
                rows[250]["release_event"] = "signal_removed"
            rows[200]["vehicle_center_x_m"] += 1
            rows_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            reject("changed_fixed_motion", "Fixed release comparison condition differs")
            rows[200]["vehicle_center_x_m"] -= 1
            first_rows = (sources[suffixes[0]] / "native-rows.jsonl").read_text().splitlines()
            rows[250]["warning_xyz_m"] = json.loads(first_rows[250])["warning_xyz_m"]
            rows_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n")
            reject("unchanged_release_actor", "Release actor state does not differ")
            try:
                audit(group, {suffixes[0]: sources[suffixes[0]]})
            except ValueError as error:
                if "cases missing" not in str(error):
                    raise
                negatives.append({"name": "missing_case", "expected_error": "cases missing"})
            else:
                raise AssertionError("Missing release comparison case accepted")
        results.append({"comparison_id": positive["comparison_id"],
                        "case_ids": positive["case_ids"],
                        "positive_receipt": str(output.relative_to(ROOT)),
                        "negative_checks": negatives})
    proof = {"format": "worker-school-release-comparison-cpu-proof-v1",
             "diagnostic_only": True, "physical_or_legal_acceptance_claimed": False,
             "comparisons": results}
    path = ROOT / "proofs/release-comparison-proof.json"
    path.write_text(json.dumps(proof, indent=2) + "\n")
    return proof


if __name__ == "__main__":
    result = prove()
    print(json.dumps({"passed": True, "comparison_count": len(result["comparisons"]),
                      "negative_count": sum(len(item["negative_checks"])
                                            for item in result["comparisons"])}))
