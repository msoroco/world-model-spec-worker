"""Build a handoff proposal for the exact nighttime truck selected cases."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OWN = ROOT.name
OTHER = "testing__C393410__LVMC-11-48-060__motor_vehicle_driver"


def main():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    source = json.loads((REPO / "work" / OTHER / "gpu-queue-proposal.json").read_text())
    template = source["cases"][0]
    old_case = template["case_id"]
    rows = []
    for index, case in enumerate(plan["cases"], 1):
        cid = case["case_id"]
        row = json.loads(json.dumps(template).replace(old_case, cid).replace(OTHER, OWN)
                         .replace("c393410-local", "c393410-050-local"))
        row["order"] = index
        rows.append(row)
    compare_template = source["comparison_audit_commands"][0]
    old_comparison = compare_template["comparison_id"]
    comparison_rows = []
    for item in plan["comparisons"]:
        row = json.loads(json.dumps(compare_template).replace(OTHER, OWN)
                         .replace(old_comparison, item["comparison_id"])
                         .replace("c393410-local", "c393410-050-local"))
        row["comparison_id"] = item["comparison_id"]
        row["case_ids"] = item["case_ids"]
        comparison_rows.append(row)
    proposal = {"format": source["format"], "assignment_id": OWN, "cases": rows,
        "comparison_audit_commands": comparison_rows,
        "source_prerequisites": [
            "Independent original municipal residence district frontage and business exclusion review",
            "Original authoritative truck-route designation and reviewed C393410 road network",
            "Vehicle-specific actual unladen weight and identity original records",
            "Timezone-qualified original local civil clock with UTC source and uncertainty",
            "DPW written application, issued written permit and all vehicle/route/time conditions, or reviewed negative administrative search",
            "Original Native 900-frame motion and four complete camera streams; independent pixel review and physical/legal judgment"]}
    (ROOT / "gpu-queue-proposal.json").write_text(json.dumps(proposal, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
