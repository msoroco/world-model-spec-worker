"""Execute pinned per-topic contract validation and saved report source joins."""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/pipeline/scenario_pipeline"))
from worker_exchange.measurement_contract import validate, verify_report


def main():
    plan = json.loads((HERE / "case-plan.json").read_text())
    checked = {}
    for suffix in ("condition_a", "condition_b"):
        case = next(c["case_id"] for c in plan["cases"]
                    if c["case_id"].endswith("__" + suffix))
        contract = json.loads((HERE / "draft-candidates" / suffix / "measurement-contract.json").read_text())
        source = (HERE / "native/finalize.py").read_text()
        rows = validate(contract, plan["requirement_dispositions"], source, case)
        if [row["requirement"] for row in rows] != ["text-0", "text-1", "reviewed-scope-0",
                                                   "reviewed-scope-1", "reviewed-scope-2"]:
            raise ValueError("Statutory source-topic measurements differ")
        proof = json.loads((HERE / ("portable-proof-" + suffix + "-primary.json")).read_text())
        scratch = Path(proof["scratch"]); fixture = Path(proof["fixture"])
        report = json.loads((scratch / "output/analysis-report.json").read_text())
        values = verify_report(contract, report, fixture)
        if values["reverse_motion_frames"]["value"] != 200 or \
           values["crosswalk_witness_relation"]["value"] is not \
           (suffix == "condition_b"):
            raise ValueError("Per-topic source-bound measured result differs")
        checked[suffix] = {"topics": [r["requirement"] for r in rows],
                           "source_hashes_verified": True,
                           "witness_relation": values["crosswalk_witness_relation"]["value"]}
    print(json.dumps({"passed": True, "scope": "pinned per-topic CPU contract verification",
                      "selected": False, "cases": checked}, indent=2))


if __name__ == "__main__": main()
