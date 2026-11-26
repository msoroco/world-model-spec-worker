"""Bind the 14 exact drafts to saved-only finalization and measurement contracts.

This prepares selected source bundles. It does not issue compatibility receipts or
claim delivery readiness before the full positive/negative pipeline is tested.
"""

import hashlib
import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
NATIVE = ROOT / "native"
SCRATCH = Path(os.environ["SCENARIO_PIPELINE_OUTPUT_ROOT"]) / "selected-contract-staging"
SOURCES = ("pedestrian-caution-trace.jsonl", "pedestrian-source-review.jsonl",
           "context-survey.json")


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def build():
    draft = json.loads((ROOT / "draft-all-branches-manifest.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    files = {name: (NATIVE / name).read_text() for name in
             ("finalize.py", "saved_measure.py", "branch_meter.py")}
    rows = []
    for index, entry in enumerate(draft["cases"]):
        case_id = entry["case_id"]
        suffix = case_id.rsplit("__", 1)[-1]
        source = json.loads((ROOT / entry["construction"]).read_text())
        config = json.loads(next(f["content"] for f in source["files"]
                                 if f["path"] == "config.json"))
        drafted_description = source["recording_description"]
        description = {"channels": drafted_description["channels"],
                       "context_inputs": [],
                       "limitations": drafted_description["limitations"]}
        for channel in description["channels"]:
            channel["unit"] = "structured"
            channel["reference_frame"] = "original Native 20 Hz frame and four-camera join"
            channel["uncertainty"] = "synthetic software fixtures cannot establish physical visibility or perception"
        config["status"] = "selected_cpu_preparation"
        config["recording_description"] = description
        source["recording_description"] = description
        source["status"] = "selected_cpu_preparation"
        source["measurement_plan"] = {"entrypoint": "finalize.py",
            "required_sources": list(SOURCES), "source_review_required": True,
            "driver_observation_not_inferred_from_visibility": True}
        source["static_checks"] = [
            "exact law/cell/actor and 600-frame four-camera capture",
            "independent original-source statutory position and observation review",
            "no legal caution threshold or physical outcome inferred from requested speed"]
        source["termination_rules"] = ["600 original frames",
            "destroy owned actors and restore the original world"]
        source["mechanisms"] = ["surveyed pedestrian and context geometry",
            "post-observation engineering speed request comparison",
            "source-bound measured results retain unknown driver observation"]
        for file in source["files"]:
            if file["path"] == "config.json":
                file["content"] = json.dumps(config, indent=2) + "\n"
        source["files"].extend({"path": name, "content": content}
                               for name, content in files.items())
        target = ROOT / "cases" / suffix
        target.mkdir(parents=True, exist_ok=True)
        for file in source["files"]:
            path = target / file["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(file["content"])
        construction = target / "construction.json"
        dump(SCRATCH / (suffix + "-construction.json"), source)
        os.replace(SCRATCH / (suffix + "-construction.json"), construction)
        applicable = [(position, disposition) for position, disposition in
                      enumerate(plan["requirement_dispositions"])
                      if case_id in disposition.get("case_ids", [])]
        if len(applicable) != 1:
            raise ValueError("Exact case needs one statutory position disposition: " + case_id)
        position, disposition = applicable[0]
        contract = {"format": "worker-measurement-contract", "case_id": case_id,
            "requirements": [{"disposition_index": position,
                "requirement": disposition["requirement"],
                "source": disposition["source"],
                "output_key": "caution_observation",
                "method": "caution_observation", "value_type": "object",
                "kind": "measured", "inputs": list(SOURCES)}],
            "negative": {"remove": ["pedestrian-source-review.jsonl"],
                         "error_contains": "Missing required source: pedestrian-source-review.jsonl"}}
        contract_path = ROOT / ("measurement-" + suffix + ".json")
        dump(SCRATCH / contract_path.name, contract)
        os.replace(SCRATCH / contract_path.name, contract_path)
        rows.append({"case_id": case_id,
                     "construction": str(construction.relative_to(ROOT)),
                     "construction_sha256": digest(construction),
                     "measurement_contract": contract_path.name,
                     "measurement_contract_sha256": digest(contract_path)})
        if index == 0:
            for name in ("runner.py", "config.json", "finalize.py",
                         "saved_measure.py", "branch_meter.py"):
                (ROOT / name).write_text((target / name).read_text())
            root_test = ROOT / "tests" / "test_offline.py"
            root_test.parent.mkdir(parents=True, exist_ok=True)
            root_test.write_text((target / "tests" / "test_offline.py").read_text())
            dump(SCRATCH / "root-construction.json", source)
            os.replace(SCRATCH / "root-construction.json", ROOT / "construction.json")
    index = {"format": "worker-nrs280-selected-contract-index-v1",
             "status": "cpu_preparation_incomplete", "cases": rows,
             "public_compatibility_passed": False, "delivery_ready": False}
    dump(SCRATCH / "selected-contract-index.json", index)
    os.replace(SCRATCH / "selected-contract-index.json", ROOT / "selected-contract-index.json")
    print(json.dumps({"selected_contracts": len(rows),
                      "index_sha256": digest(ROOT / "selected-contract-index.json")}))


if __name__ == "__main__":
    build()
