"""Build canonical source-bound proposals for the selected bicycle witness."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
PLAN = json.loads((ROOT / "case-plan.json").read_text())
ASSIGNMENT = REPO / "inputs" / PLAN["assignment_id"] / "assignment.json"
OUT = ROOT / "proposals"
OUT.mkdir(exist_ok=True)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(name: str, value: dict) -> dict:
    path = OUT / name
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return {"path": "proposals/" + name, "sha256": sha(path)}


def main() -> None:
    aid, law, cell, actor = (PLAN[key] for key in ("assignment_id", "law_id", "cell_id", "actor"))
    quote = PLAN["law_text"]
    relevance = dump("relevance.json", {"cell_id": cell, "actor": actor, "status": "draft",
        "relevant_laws": [{"law_id": law, "quote": quote, "applies_to": [actor],
            "relevance_type": "source-selected human-powered bicycle at governed intersection device",
            "confidence": "medium",
            "notes": "Original municipal site, official vehicle-applicable device, participant classification and officer authority remain source gates."}],
        "borderline_excluded": []})
    variable_kinds = {"device_type": "world_setup", "device_instruction": "world_setup",
                      "officer_direction": "world_setup", "operator_motion": "controller"}
    parameter_refs = [{"name": name, "kind": kind,
                       "range_or_domain": "reviewed exact-case source or commanded bicycle motion"}
                      for name, kind in variable_kinds.items()]
    template = dump("template.json", {"template_id": law + "@" + actor,
        "law_id": law, "actor": actor, "status": "draft", "quote": quote,
        "structure": {"law_id": law,
            "activation": {"condition": "A documented human-powered bicycle operator encounters an official control device applicable to vehicles.",
                           "numeric_conditions": []},
            "obligation": {"description": "Obey the actual instruction of the applicable official signal, sign or other control device.",
                           "type": "must", "numeric_conditions": []},
            "exceptions": [{"trigger": "otherwise directed by a Police Officer",
                "effect": "A source-verified officer direction may replace the device instruction for its recipient and time.",
                "replacement_obligation": "Retain the observed officer command, actor, recipient and timing for independent review.",
                "source_clause": "unless otherwise directed by a Police Officer"}],
            "timing": {"description": "Observe device and any officer direction during the original approach and crossing or hold response.",
                       "numeric_conditions": []},
            "judgment_calls_needed": []}, "parameter_refs": parameter_refs})
    bindings = dump("bindings.json", {"cell_id": cell, "actor": actor, "status": "draft",
        "established_contexts": ["The frozen witness selects a human-powered bicycle; original classification and device authority are required before Native capture."],
        "law_refs": [{"template_id": law + "@" + actor, "binding_kind": "direct"}],
        "context_refs": [],
        "fixed_parameters": [{"name": "participant_class", "kind": "world_setup",
                              "value": "human_powered_bicycle", "source": "frozen witness index 289"}],
        "variable_parameters": [dict(item, used_by_laws=[law]) for item in parameter_refs]})
    entries = json.loads((ROOT / "execution-manifest.json").read_text())["cases"]
    descriptions = {entry["case_id"]: json.loads((ROOT / entry["construction"]).read_text())["recording_description"]
                    for entry in entries}
    baseline = {"case_id": aid + "__baseline", "target_law_id": None,
        "target_type": "baseline", "rationale": "Nonexecuted neutral semantic reference for the exact instruction pairs.",
        "variable_assignments": {name: {"kind": kind, "value": "unselected"}
                                 for name, kind in variable_kinds.items()},
        "unresolved_judgment_calls": [], "recording_description": next(iter(descriptions.values()))}
    cases = [baseline]
    for case in PLAN["cases"]:
        suffix = case["case_id"].split("__")[-1]
        target_type = ("compliant_attempt" if suffix == "signal_red_stop" else
                       "violating_attempt" if suffix == "signal_red_cross" else "boundary_probe")
        pair = "red_operator_motion" if suffix in {"signal_red_stop", "signal_red_cross"} else suffix
        cases.append({"case_id": case["case_id"], "target_law_id": law,
            "target_type": target_type,
            "rationale": "Source-gated observed device and bicycle response; no legal outcome is asserted.",
            "variable_assignments": {name: {"kind": kind, "value": case[name]}
                                     for name, kind in variable_kinds.items()},
            "unresolved_judgment_calls": [], "paired_probe_id": pair,
            "deliberate_differences": ["operator_motion"],
            "probe": {"primary_variable": "operator_motion",
                      "comparison_or_standard": "reviewed source-bound device instruction and any officer exception",
                      "target_value_or_branch": case["operator_motion"]},
            "recording_description": descriptions[case["case_id"]]})
    cases_ref = dump("cases.json", {"cell_id": cell, "actor": actor, "status": "draft",
                                   "cases": cases, "sweep_specs": []})
    index = {"format": "worker-semantic-delivery", "assignment_id": aid,
        "source": {"path": str(ASSIGNMENT.relative_to(REPO)), "sha256": sha(ASSIGNMENT)},
        "stages": {"relevance_batch": relevance, "relevance": relevance,
                   "template": template, "judgment_observables": [],
                   "bindings": bindings, "cases": cases_ref},
        "status": "draft_original_site_and_authority_review_pending"}
    dump("semantic-index.json", index)


if __name__ == "__main__":
    main()
