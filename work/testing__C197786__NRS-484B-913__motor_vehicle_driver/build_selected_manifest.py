"""Bind exact diagnostic constructions into a truthful selected draft manifest."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    diagnostic = json.loads((ROOT / "diagnostic-execution-manifest.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    planned = {item["case_id"]: item for item in plan["cases"]}
    if not plan.get("requirement_dispositions"):
        plan["requirement_dispositions"] = [{
            "requirement": "Original body passage over a qualifying fire-department hose on the fixed private way, with protection, purpose and command consent measured separately",
            "source": "NRS 484B.913",
            "status": "selected_required",
            "case_ids": [item["case_id"] for item in plan["cases"]],
            "evidence_or_gap": "No accepted original source packet; all six constituent facts require independent original review",
        }]
        (ROOT / "case-plan.json").write_text(json.dumps(plan, indent=2) + "\n")
    cases = []
    for selected in diagnostic["cases"]:
        cid = selected["case_id"]
        short = cid.removeprefix(ROOT.name + "__")
        log = ROOT / ("cpu-offline-" + short + ".log")
        construction = ROOT / selected["construction"]
        if sha(construction) != selected["construction_sha256"] or not log.is_file():
            raise ValueError("selected construction or offline proof changed: " + cid)
        case = planned[cid]
        source_inputs = ["saved-packet.json", "frames.jsonl"] + [
            "original-context/" + name + ".json" for name in
            ("private_way", "hose", "incident", "official", "consent", "vehicle")]
        contract = {"format": "worker-measurement-contract", "assignment_id": ROOT.name,
                    "case_id": cid, "requirements": [{
                        "disposition_index": 0,
                        "requirement": plan["requirement_dispositions"][0]["requirement"],
                        "source": "NRS 484B.913", "output_key": "hose_passage_history",
                        "method": "measure_hose_passage", "value_type": "object",
                        "kind": "measured", "inputs": source_inputs}],
                    "negative": {"remove": ["original-context/hose.json"],
                                 "error_contains": "Missing required source: original-context/hose.json"},
                    "scope": "Original source-bound geometry and context measurements; no legal verdict"}
        contract_path = ROOT / "cases" / short / "measurement-contract.json"
        contract_path.write_text(json.dumps(contract, indent=2) + "\n")
        cases.append({
            "case_id": cid,
            "kind": "delivery",
            "construction": selected["construction"],
            "construction_sha256": selected["construction_sha256"],
            "candidate_risk": selected["candidate_risk"],
            "candidates": case["candidates"],
            "offline": {
                "command": f".venv-cpu/bin/python runtime.py offline --manifest work/{ROOT.name}/execution-manifest.json --case {cid} --output .runtime-work/hose-913-selected-{short}-v1",
                "construction_sha256": selected["construction_sha256"],
                "diagnostic_command": f".venv-cpu/bin/python runtime.py offline --manifest work/{ROOT.name}/diagnostic-execution-manifest.json --case {cid} --output .runtime-work/hose-913-offline-{short}-v14",
                "diagnostic_exit_code": 0,
                "diagnostic_log": log.name,
                "diagnostic_log_sha256": sha(log),
                "scope": "source-gated CPU construction only; selected compatibility pending",
            },
            "measurement_contract": "cases/" + short + "/measurement-contract.json",
            "measurement_procedure": {"entrypoint": "analysis.py"},
            "fixture_recipe": "work/" + ROOT.name + "/cases/" + short + "/fixture-recipe.json",
            "native_handoff": {"host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT",
                               "python_env_var": "CARLA_PYTHON"},
            "acquisition": {name: {"entrypoint": "native_capture.py",
                                    "method": "source-joined original Native observation",
                                    "evidence": "frames.jsonl and six original-context JSON sources"}
                            for name in ("original_ego_body_footprint", "actual_hose_segment",
                                         "hose_protection", "incident_purpose", "command_official",
                                         "consent_source", "private_way_access")},
            "post_capture": {"recorded_only": True, "status": "pending_saved_processing_proof"},
            "delivery_acceptance": {"case_id": cid, "sets": ["full-test"],
                                    "checks": ["native_source", "all_participants", "time_join",
                                               "full_video_decode", "actual_pixels", "physical_completion"],
                                    "status": "pending_source_bound_positive_negative_receipts"},
        })
    manifest = {"format": "worker-execution-manifest", "assignment_id": ROOT.name,
                "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
                "selected_draft": True, "cases": cases,
                "comparisons": diagnostic["comparisons"]}
    (ROOT / "execution-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(json.dumps({"selected_cases": len(cases), "receipts_pending": True}))


if __name__ == "__main__":
    build()
