"""Bind every witnessed branch requirement to the exact planned CPU cases.

This selects construction work, never claims physical capture or accepted reuse.
"""
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main():
    path = HERE / "case-plan.json"
    plan = json.loads(path.read_text())
    cases = {case["case_id"].rsplit("__", 1)[-1]: case for case in plan["cases"]}
    crest = [cases["probe_01"]["case_id"], cases["probe_02"]["case_id"]]
    curve = [cases["probe_03"]["case_id"]]
    for row in plan["requirement_dispositions"]:
        row["case_ids"] = curve if row["branch"] == "curve or grade crest reversal" else crest
        row["status"] = "selected_required"
        row["evidence_or_gap"] = (
            "Exact three-case CPU source and finalizer diagnostics selected; "
            "original CARLA body rays, reviewed pixels, physical reversal and accepted "
            "comparison remain unverified.")
    for case in cases.values():
        case["selection_status"] = "selected_for_cpu_delivery_preparation"
        case["kind"] = "selected_native_request"
        case["construction_status"] = (
            "source-joined selected CPU diagnostics in progress; original physical "
            "visibility and maneuver unverified")
    path.write_text(json.dumps(plan, indent=2, allow_nan=False) + "\n")
    print(json.dumps({"selected_cases": len(cases),
                      "selected_requirements": len(plan["requirement_dispositions"]),
                      "original_physical_proven": False}))


if __name__ == "__main__":
    main()
