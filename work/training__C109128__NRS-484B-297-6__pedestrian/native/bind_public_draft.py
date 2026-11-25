"""Bind exact source recipes and measurement contracts for public CPU trials."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent
ROOT = ASSIGNMENT.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    plan = json.loads((ASSIGNMENT / "case-plan.json").read_text())
    draft = json.loads((HERE / "selected-draft-manifest.json").read_text())
    inputs = ["pedestrian-original.jsonl", "video_frames.jsonl",
              "camera-sources.jsonl", "sidewalk_context.json"]
    proposals = []
    manifest_cases = []
    for entry in draft["cases"]:
        case = entry["case_id"]
        condition = case.rsplit("__", 1)[-1]
        source_rows = [(0, "measure_activation"), (1, "measure_subject"),
                       (2, "measure_near_side"), (5, "measure_return")]
        if condition.startswith("direction_"):
            source_rows.append((3, "measure_direction"))
        elif condition.startswith("bike_"):
            source_rows.append((4, "measure_bicycle_lane"))
        else:
            source_rows.append((6, "measure_scope"))
        comparison = next(row for row in plan["comparisons"] if case in row["case_ids"])
        variable = comparison["deliberate_differences"][0]
        config = json.loads(next(file["content"] for file in
            json.loads((HERE / entry["construction"]).read_text())["files"]
            if file["path"] == "config.json"))
        recording = config["recording_description"]
        proposals.append({"case_id": case, "target_law_id": "NRS-484B-297-6",
            "target_type": "planned_delivery_comparison",
            "rationale": "Original blocked-sidewalk lateral bypass comparison; physical and legal review pending",
            "variable_assignments": {variable: {
                "kind": "world_setup", "value": condition}},
            "unresolved_judgment_calls": ["due care", "as far to the side as possible",
                "intervening-area impassability", "as soon as practicable"],
            "recording_description": recording,
            "paired_probe_id": comparison["comparison_id"],
            "deliberate_differences": [variable],
            "probe": condition})
        contract = {"format": "worker-measurement-contract", "case_id": case,
            "requirements": [{"disposition_index": index,
                "requirement": plan["requirement_dispositions"][index]["requirement"],
                "source": plan["requirement_dispositions"][index]["source"],
                "output_key": method, "method": method, "value_type": "object",
                "kind": "measured", "inputs": inputs}
                for index, method in source_rows],
            "negative": {"remove": ["sidewalk_context.json"],
                         "error_contains": "Missing required source: sidewalk_context.json"}}
        contract_path = ASSIGNMENT / f"measurement-contract-{condition}.json"
        contract_path.write_text(json.dumps(contract, indent=2) + "\n")
        row = dict(entry)
        row["kind"] = "delivery"
        row["construction"] = "native/" + entry["construction"]
        for candidate in row["candidates"]:
            candidate["construction"] = "native/" + candidate["construction"]
        row["measurement_contract"] = contract_path.name
        row["measurement_procedure"] = {"entrypoint": "finalize.py",
                                          "output_schema": "worker-analysis-report-v1"}
        row["fixture_recipe"] = "work/" + ASSIGNMENT.name + "/diagnostic-" + condition + "-primary-recipe.json"
        manifest_cases.append(row)
    proposal_dir = ASSIGNMENT / "proposals"
    proposal_dir.mkdir(exist_ok=True)
    (proposal_dir / "cases.json").write_text(json.dumps({
        "cell_id": "C109128", "actor": "pedestrian", "status": "cpu_draft",
        "sweep_specs": [], "sweeps_expanded": True, "cases": proposals},
        indent=2) + "\n")
    manifest = {"format": "worker-execution-manifest",
                "assignment_id": ASSIGNMENT.name,
                "runtime_manifest_sha256": sha(ROOT / "runtime/SOURCE-MANIFEST.json"),
                "status": "draft_public_compatibility_pending",
                "delivery_ready": False, "cases": manifest_cases}
    target = ASSIGNMENT / "public-draft-manifest.json"
    target.write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"cases": len(manifest_cases),
                      "manifest_sha256": sha(target)}))


if __name__ == "__main__":
    build()
