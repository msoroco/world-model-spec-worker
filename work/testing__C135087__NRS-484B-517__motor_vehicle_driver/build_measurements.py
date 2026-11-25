"""Bind exact stand witness requirements to saved source measurements."""
from __future__ import annotations

import json
from pathlib import Path

from build_bundles import HERE, AID


REQUIREMENTS = (
    ("Officially designated and appropriately signed taxicab stand", "stand_designation", "measure_designation"),
    ("Passenger vehicle with identified driver and non-taxicab use", "subject_classification", "measure_subject"),
    ("Taxicab waiting to enter or about to enter the stand", "taxicab_entrant", "measure_entrant"),
    ("Temporary stop while actually loading or unloading passengers expeditiously", "passenger_loading", "measure_loading"),
    ("No interference with the waiting or approaching taxicab", "access_effect", "measure_access"),
    ("Original synchronized actor history and four camera views", "original_four_view_media", "measure_media"),
)
INPUTS = ["attempt-source.json", "site-original.json", "vehicle-original.json", "actor-rows.json",
          "frame-map.json", "overview.mkv", "approach.mkv", "reference_corner.mkv", "driver_reference.mkv"]


def write(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def build():
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    source = "inputs/" + AID + "/assignment.json"
    plan["selected_branch"] = "Passenger loading with a taxicab entrant"
    plan["requirement_dispositions"] = [
        {"requirement": phrase, "source": source, "status": "selected_required",
         "evidence_or_gap": "No accepted exact-branch recording; original site, actor and media sources pending review"}
        for phrase, _, _ in REQUIREMENTS
    ]
    write(plan_path, plan)
    for case in plan["cases"]:
        suffix = case["case_id"].removeprefix(AID + "__")
        contract = {"format": "worker-measurement-contract", "case_id": case["case_id"],
                    "requirements": [
                        {"disposition_index": index, "requirement": phrase, "source": source,
                         "output_key": key, "method": method, "value_type": "object",
                         "kind": "measured", "inputs": INPUTS}
                        for index, (phrase, key, method) in enumerate(REQUIREMENTS)],
                    "negative": {"remove": ["site-original.json"],
                                 "error_contains": "Missing required source: site-original.json"}}
        write(HERE / "contracts" / (suffix + ".json"), contract)
    print("bound", len(plan["cases"]), "measurement contracts")


if __name__ == "__main__":
    build()
