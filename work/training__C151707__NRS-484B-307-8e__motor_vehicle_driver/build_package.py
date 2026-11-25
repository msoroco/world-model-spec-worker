"""Bind both selected route cases to the current public CPU compatibility path."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
NATIVE = ROOT / "native"
ASSIGNMENT = ROOT.name


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def put(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def main() -> None:
    property_construction = json.loads((NATIVE / "construction.json").read_text())
    road_construction = json.loads((NATIVE / "cases/probe_01/construction.json").read_text())
    (ROOT / "construction.json").write_bytes((NATIVE / "construction.json").read_bytes())
    for name in ("config.json", "runner.py"):
        (ROOT / name).write_bytes((NATIVE / name).read_bytes())
    (ROOT / "tests/test_runner.py").write_bytes((NATIVE / "tests/test_runner.py").read_bytes())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    proposals = []
    entries = []
    for suffix, construction, construction_path in (
            ("01", road_construction, "native/cases/probe_01/construction.json"),
            ("02", property_construction, "construction.json")):
        case = ASSIGNMENT + "__probe_" + suffix
        route_property = suffix == "02"
        proposals.append({
            "case_id": case, "target_law_id": "NRS-484B-307-8e",
            "target_type": "controlled_attempt",
            "rationale": "Same surveyed map and signal inventory; selected route changes property traversal.",
            "paired_probe_id": ASSIGNMENT + "__planned_comparison",
            "deliberate_differences": ["route through property to avoid signal"],
            "probe": {"primary_variable": "property_traversal_route",
                      "comparison_or_standard": "surveyed road-only versus property route",
                      "target_value_or_branch": route_property},
            "variable_assignments": {"property_traversal_route": {
                "kind": "controller", "value": route_property}},
            "recording_description": construction["recording_description"],
            "unresolved_judgment_calls": ["physical property authority and lens facing",
                                          "avoidance purpose authenticity"]})
        contract_path = ROOT / f"measurement-{suffix}.json"
        put(contract_path, {"format": "worker-measurement-contract", "case_id": case,
                            "requirements": [{"disposition_index": 0,
                              "requirement": plan["requirement_dispositions"][0]["requirement"],
                              "source": plan["requirement_dispositions"][0]["source"],
                              "output_key": "property_bypass_observation",
                              "method": "measure_property_route", "value_type": "object",
                              "kind": "measured",
                              "inputs": ["property-route-native.jsonl", "property-survey.json",
                                         "purpose-declaration.json"]}],
                            "negative": {"remove": ["property-survey.json"],
                              "error_contains": "Missing required source: property-survey.json"}})
        entries.append({"case_id": case, "kind": "delivery",
                        "construction": construction_path,
                        "construction_sha256": sha(ROOT / construction_path),
                        "measurement_contract": contract_path.name,
                        "measurement_procedure": {"entrypoint": "finalize.py"},
                        "fixture_recipe": "work/" + ASSIGNMENT + f"/diagnostic-{suffix}-recipe.json",
                        "candidate_risk": {"status": "physical",
                           "reason": "Original Native route following, parcel location, signal facing and pixels require live review"},
                        "candidates": [],
                        "native_handoff": {"python_env_var": "CARLA_PYTHON",
                                           "host_env_var": "CARLA_HOST",
                                           "port_env_var": "CARLA_PORT"}})
    put(ROOT / "proposals/cases.json", {"format": "worker-case-proposals",
        "cell_id": "C151707", "actor": "motor_vehicle_driver", "status": "draft",
        "sweep_specs": [], "sweeps_expanded": True, "cases": proposals})
    put(ROOT / "execution-manifest.json", {"format": "worker-execution-manifest",
        "assignment_id": ASSIGNMENT, "status": "partial_public_cpu_scaffold",
        "runtime_manifest_sha256": sha(REPO / "runtime/SOURCE-MANIFEST.json"),
        "cases": entries})
    print(json.dumps({"manifest_sha256": sha(ROOT / "execution-manifest.json"),
                      "case_constructions": {entry["case_id"]: entry["construction_sha256"]
                                             for entry in entries}}, sort_keys=True))


if __name__ == "__main__":
    main()
