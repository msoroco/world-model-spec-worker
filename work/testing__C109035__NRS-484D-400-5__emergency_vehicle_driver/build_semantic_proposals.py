"""Build source-bound draft semantic stages for the seven emergency-device cases."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
AID = ROOT.name
LAW = "NRS-484D-400-5"
ACTOR = "emergency_vehicle_driver"
TEMPLATE = f"{LAW}@{ACTOR}"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(assignment: dict, plan: dict) -> dict[str, dict]:
    if (assignment["assignment_id"], assignment["law_id"], assignment["actor"]) != (AID, LAW, ACTOR):
        raise ValueError("Frozen assignment identity mismatch")
    if (plan["assignment_id"], plan["law_id"], plan["actor"]) != (AID, LAW, ACTOR):
        raise ValueError("Case-plan identity mismatch")
    quote = plan["law_text"]
    for clause in ("not less than 500 feet", "must not be used except", "emergency call",
                   "immediate pursuit", "actual or suspected", "warning lamps without sounding the siren"):
        if clause not in quote:
            raise ValueError(f"Missing exact-law clause: {clause}")
    cases = plan["cases"]
    expected = {
        "response_siren_pedestrian": ("emergency_call", True, False),
        "response_lamps_only": ("emergency_call", False, True),
        "response_silent": ("emergency_call", False, False),
        "pursuit_actual_siren": ("immediate_pursuit_actual", True, False),
        "pursuit_suspected_siren": ("immediate_pursuit_suspected", True, False),
        "unqualified_siren": ("none", True, False),
        "unqualified_lamps_only": ("none", False, True),
    }
    by_suffix = {c["case_id"].removeprefix(AID + "__"): c for c in cases}
    if set(by_suffix) != set(expected) or len(cases) != len(expected):
        raise ValueError("Seven exact case IDs are required")
    params = [
        {"name": "documented_event_context", "kind": "source_context", "range_or_domain": list(dict.fromkeys(v[0] for v in expected.values()))},
        {"name": "requested_siren", "kind": "controller", "range_or_domain": [False, True]},
        {"name": "requested_warning_lamps", "kind": "controller", "range_or_domain": [False, True]},
    ]
    relevance = {
        "cell_id": assignment["cell_id"], "actor": ACTOR, "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": [ACTOR],
                           "relevance_type": "emergency vehicle equipment and conditional siren and lamp permissions",
                           "confidence": "medium",
                           "notes": "Vehicle authorization, actual event, purpose, device state and normal-condition audibility need independent original sources."}],
        "borderline_excluded": [],
    }
    template = {
        "template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR, "status": "draft", "quote": quote,
        "structure": {
            "activation": {"condition": "Authorized emergency vehicle and driver; device and event facts are source-reviewed."},
            "obligation": {"type": "conditional_siren_restriction", "description": "Siren must not be used except during emergency-call response or immediate pursuit of an actual or suspected violator; qualifying use may warn pedestrians and other drivers."},
            "exceptions": ["Response to an emergency call", "Immediate pursuit of an actual violator", "Immediate pursuit of a suspected violator"],
            "permissions": ["The vehicle may be equipped with a qualifying audible device", "Warning lamps may operate without sounding the siren"],
            "timing": {"description": "Join each original siren-on frame to an independently documented event interval."},
            "judgment_calls_needed": ["Vehicle authorization", "Immediate pursuit", "Warning purpose", "Normal-condition 500-foot audibility"],
        },
        "parameter_refs": params,
    }
    bindings = {
        "cell_id": assignment["cell_id"], "actor": ACTOR, "status": "draft",
        "established_contexts": ["C109035 intersection response route", "pedestrian approach-warning recipient"],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{**p, "used_by_laws": [LAW]} for p in params],
    }
    proposals = []
    for suffix, (event, siren, lamps) in expected.items():
        case = by_suffix[suffix]
        if (case["authored_event_context"], case["requested_siren"], case["requested_warning_lamps"]) != (event, siren, lamps):
            raise ValueError(f"Case-plan variables changed: {suffix}")
        if case["target_law_id"] != LAW or case["physical_status"] != "unverified":
            raise ValueError(f"Case-plan target or physical status changed: {suffix}")
        construction = ROOT / f"construction-{suffix}.json"
        if not construction.is_file() or json.loads(construction.read_text())["case_id"] != case["case_id"]:
            raise ValueError(f"Missing exact construction: {suffix}")
        proposals.append({
            "case_id": case["case_id"], "target_law_id": LAW, "target_type": "boundary_probe", "status": "draft",
            "rationale": case["branch"] + "; requested controls are not observed device states or legal findings.",
            "variable_assignments": {
                "documented_event_context": {"kind": "source_context", "value": event},
                "requested_siren": {"kind": "controller", "value": siren},
                "requested_warning_lamps": {"kind": "controller", "value": lamps},
            },
            "recording_description": "Original 45-second 20-Hz four-camera emergency vehicle and pedestrian approach capture",
            "construction": {"path": construction.name, "sha256": digest(construction)},
            "unresolved_judgment_calls": template["structure"]["judgment_calls_needed"],
        })
    comparisons = []
    variables = {c["case_id"]: c["variable_assignments"] for c in proposals}
    expected_changed = {"response_device_choice": {"requested_siren", "requested_warning_lamps"},
                        "qualifying_event_for_siren": {"documented_event_context"},
                        "lamps_without_siren": {"documented_event_context"}}
    if {c["comparison_id"] for c in plan["comparisons"]} != set(expected_changed):
        raise ValueError("Comparison set changed")
    for comparison in plan["comparisons"]:
        members = comparison["case_ids"]
        if len(members) < 2 or any(member not in variables for member in members):
            raise ValueError("Comparison has missing exact case")
        changed = {name for name in variables[members[0]] if len({json.dumps(variables[member][name], sort_keys=True) for member in members}) > 1}
        if changed != expected_changed[comparison["comparison_id"]]:
            raise ValueError(f"Comparison variables changed: {comparison['comparison_id']}")
        comparisons.append({"comparison_id": comparison["comparison_id"], "case_ids": members,
                            "fixed_conditions": comparison["fixed_conditions"],
                            "changed_variables": sorted(changed), "interpretation": comparison["interpretation"]})
    case_stage = {"cell_id": assignment["cell_id"], "actor": ACTOR, "status": "draft",
                  "cases": proposals, "comparisons": comparisons, "sweep_specs": []}
    return {"relevance_batch": relevance, "relevance": relevance, "template": template,
            "bindings": bindings, "cases": case_stage}


def main() -> None:
    assignment_path = PROJECT / "inputs" / AID / "assignment.json"
    plan_path = ROOT / "case-plan.json"
    coverage_path = PROJECT / "inputs" / "coverage" / "branch-sources.json"
    assignment = json.loads(assignment_path.read_text())
    plan = json.loads(plan_path.read_text())
    frozen_quote = json.loads(coverage_path.read_text())["laws"][LAW]["law"]["text"]
    if plan["law_text"] != frozen_quote:
        raise ValueError("Case-plan quote differs from frozen exact law")
    payloads = prepare(assignment, plan)
    destination = ROOT / "proposals"
    destination.mkdir(exist_ok=True)
    refs = {}
    for stage, payload in payloads.items():
        path = destination / f"{stage}.json"
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
        refs[stage] = {"path": str(path.relative_to(ROOT)), "sha256": digest(path)}
    refs["judgment_observables"] = []
    index = {"format": "worker-semantic-delivery", "assignment_id": AID,
             "status": "draft", "sources": [
                 {"path": str(assignment_path.relative_to(PROJECT)), "sha256": digest(assignment_path)},
                 {"path": str(plan_path.relative_to(PROJECT)), "sha256": digest(plan_path)},
                 {"path": str(coverage_path.relative_to(PROJECT)), "sha256": digest(coverage_path)}],
             "stages": refs, "physical_acceptance": "unverified"}
    (destination / "semantic-index.json").write_text(json.dumps(index, indent=2, ensure_ascii=False) + "\n")
    print("source-bound draft semantic stages: seven exact cases, three controlled comparisons")


if __name__ == "__main__":
    main()
