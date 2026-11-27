"""Build exact three-case diagnostic bundles for the speed extension.

This draft manifest is separate from the pinned four selected cases until all
new receipts pass. It never alters an existing selected construction.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def write(path: Path, value: dict) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def speed_measurement_source() -> str:
    original = (HERE / "nonthrough_stop.py").read_text()
    before, rest = original.split("CASES = (\n", 1)
    _, after = rest.split("\n)\n\n\n", 1)
    extension = json.loads((HERE / "speed-sweep-extension.json").read_text())
    lines = ["CASES = ("]
    for row in extension["cases"]:
        suffix = row["case_id"].removeprefix(HERE.name + "__")
        lines.append(f"    Case({suffix!r}, 'approaching', 'stop', 8),")
    lines.append(")")
    return before + "\n".join(lines) + "\n\n\n" + after


def build() -> dict:
    extension = json.loads((HERE / "speed-sweep-extension.json").read_text())
    anchor = json.loads((HERE / "cases/approaching_near_response/construction.json").read_text())
    anchor_config = json.loads((HERE / "cases/approaching_near_response/config.json").read_text())
    base_plan = json.loads((HERE / "case-plan.json").read_text())
    known_cases = {item["case_id"] for item in base_plan["cases"]}
    anchor_plan_case = next(item for item in base_plan["cases"]
                            if item["case_id"] == anchor_config["selected_case_id"])
    for row in extension["cases"]:
        if row["case_id"] not in known_cases:
            plan_case = json.loads(json.dumps(anchor_plan_case))
            plan_case["case_id"] = row["case_id"]
            plan_case["draft_variables"] = row["draft_variables"]
            plan_case["target_type"] = "crossing_speed_judgment_sweep_attempt"
            base_plan["cases"].append(plan_case)
            base_plan["requirement_dispositions"][0]["case_ids"].append(row["case_id"])
    write(HERE / "case-plan.json", base_plan)
    proposal_path = HERE / "proposals/cases.json"
    proposals = json.loads(proposal_path.read_text())
    proposal_anchor = next(item for item in proposals["cases"]
                           if item["case_id"] == anchor_config["selected_case_id"])
    known_proposals = {item["case_id"] for item in proposals["cases"]}
    for row in extension["cases"]:
        if row["case_id"] not in known_proposals:
            proposed = json.loads(json.dumps(proposal_anchor))
            proposed["case_id"] = row["case_id"]
            proposed["rationale"] = "Source-gated crossing speed judgment sweep; realized speed and legal meaning require original capture."
            proposed["variable_assignments"]["requested_ego_crossing_speed_mps"] = {
                "kind": "controller", "note": "Requested target; original result measured separately",
                "value": row["draft_variables"]["requested_ego_crossing_speed_mps"]}
            proposals["cases"].append(proposed)
    write(proposal_path, proposals)
    runner = (HERE / "speed_sweep_runner.py").read_text()
    analysis = (HERE / "analysis.py").read_text().replace(
        "from nonthrough_stop import CASES, measure_frozen_windows",
        "from speed_case_measurement import CASES, measure_frozen_windows")
    if "from speed_case_measurement import CASES, measure_frozen_windows" not in analysis:
        raise ValueError("speed finalizer import replacement failed")
    measurement = speed_measurement_source()
    entries = []
    for row in extension["cases"]:
        case_id = row["case_id"]
        suffix = case_id.removeprefix(HERE.name + "__")
        config = json.loads(json.dumps(anchor_config))
        config["selected_case_id"] = case_id
        config["supported_case_ids"] = [case_id]
        config["case"]["case_id"] = case_id
        config["case"]["draft_variables"] = row["draft_variables"]
        config["control"]["requested_ego_crossing_speed_mps"] = row["draft_variables"][
            "requested_ego_crossing_speed_mps"]
        case_plan = base_plan
        files = []
        for item in anchor["files"]:
            item = dict(item)
            if item["path"] == "config.json":
                item["content"] = json.dumps(config, indent=2, sort_keys=True) + "\n"
            elif item["path"] == "case-plan.json":
                item["content"] = json.dumps(case_plan, indent=2, sort_keys=True) + "\n"
                item.pop("source", None)
            elif item["path"] == "runner.py":
                item["content"] = runner
                item["source"] = f"work/{HERE.name}/speed_sweep_runner.py"
            elif item["path"] == "analysis.py":
                item["content"] = analysis
                item.pop("source", None)
            files.append(item)
        files.extend([
            {"path": "speed_case_measurement.py", "content": measurement},
            {"path": "speed-sweep-extension.json",
             "content": (HERE / "speed-sweep-extension.json").read_text(),
             "source": f"work/{HERE.name}/speed-sweep-extension.json"},
            {"path": "cases/approaching_near_response/config.json",
             "content": (HERE / "cases/approaching_near_response/config.json").read_text(),
             "source": f"work/{HERE.name}/cases/approaching_near_response/config.json"},
        ])
        construction = json.loads(json.dumps(anchor))
        construction.update(case_id=case_id, candidate_id="primary", files=files)
        construction["measurement_plan"]["case_id"] = case_id
        path = f"speed-sweep/{suffix}/construction.json"
        digest = write(HERE / path, construction)
        (HERE / f"speed-sweep/{suffix}/config.json").write_text(
            json.dumps(config, indent=2, sort_keys=True) + "\n")
        fallback = json.loads(json.dumps(construction))
        fallback["candidate_id"] = "fallback1"
        fallback_config = json.loads(json.dumps(config))
        fallback_config["control"]["approach_hold_margin_m"] = 2.0
        next(item for item in fallback["files"] if item["path"] == "config.json")["content"] = (
            json.dumps(fallback_config, indent=2, sort_keys=True) + "\n")
        fallback_path = f"speed-sweep/{suffix}/fallback1/construction.json"
        fallback_digest = write(HERE / fallback_path, fallback)
        contract = json.loads((HERE / "measurement-approaching_near_response.json").read_text())
        contract["case_id"] = case_id
        contract_path = f"speed-sweep/measurement-{suffix}.json"
        write(HERE / contract_path, contract)
        entries.append({"case_id": case_id, "kind": "delivery", "construction": path,
                        "construction_sha256": digest, "diagnostic_only": True,
                        "fixture_recipe": f"work/{HERE.name}/diagnostic-{suffix}-recipe.json",
                        "measurement_contract": contract_path,
                        "measurement_procedure": {"entrypoint": "analysis.py"},
                        "candidate_risk": {"status": "physical",
                           "reason": "Original low-speed crossing can overshoot the reviewed stop reference."},
                        "candidates": [{"id": "fallback1", "construction": fallback_path,
                                        "construction_sha256": fallback_digest,
                                        "trigger": {"source": "original Native history",
                                                    "metric": "body-front position at first low-speed frame",
                                                    "failure_condition": "body front crosses reviewed reference before stop response"},
                                        "changed_knobs": ["approach_hold_margin_m: 1.0 to 2.0"]}],
                        "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                           "host_env_var": "CARLA_HOST", "port_env_var": "CARLA_PORT"}})
    manifest = {"format": "worker-execution-manifest", "assignment_id": HERE.name,
                "runtime_manifest_sha256": hashlib.sha256(
                    (REPO / "runtime/SOURCE-MANIFEST.json").read_bytes()).hexdigest(),
                "diagnostic_only": True, "cases": entries}
    digest = write(HERE / "speed-sweep-manifest.draft.json", manifest)
    return {"cases": len(entries), "manifest_sha256": digest}


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
