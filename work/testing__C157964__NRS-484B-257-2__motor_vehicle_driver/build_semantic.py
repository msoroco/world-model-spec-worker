"""Author the assigned officer exception's canonical draft stage proposals."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
OUT = ROOT / "proposals"


def write(name, value):
    OUT.mkdir(exist_ok=True)
    path = OUT / name
    raw = (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()
    path.write_bytes(raw)
    return {"path": str(path.relative_to(ROOT)),
            "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    assignment = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    recording = json.loads((ROOT / "construction.json").read_text())["recording_description"]
    law = assignment["law"]
    ident = law["id"] + "@" + plan["actor"]
    quote = law["text"]
    relevance = {"cell_id": plan["cell_id"], "actor": plan["actor"],
                 "status": "draft", "relevant_laws": [{
                     "law_id": law["id"], "quote": quote,
                     "applies_to": [plan["actor"]],
                     "relevance_type": "assigned police-officer exception at non-through intersection",
                     "confidence": "medium", "notes": "Active original officer control and directive require independent review."}],
                 "borderline_excluded": []}
    refs = {"relevance_batch": write("relevance_batch.json", relevance),
            "relevance": write("relevance.json", relevance)}
    params = [{"name": name, "kind": kind, "range_or_domain": domain}
              for name, kind, domain in (
                  ("control", "world_setup", "frozen police_officer"),
                  ("officer_controls_traffic", "world_setup", "source-reviewed active"),
                  ("officer_directive", "controller", "stop or proceed requested; original readback required"),
                  ("other_phase", "world_setup", "within or approaching at original entry"),
                  ("requested_other_station_m", "world_setup", "0, 8 or 35 m engineering target"),
                  ("signal_controls", "world_setup", "false, source-reviewed"),
                  ("non_through_highway", "world_setup", "true, source-reviewed"),
                  ("other_obligated_to_stop_or_yield", "world_setup", "false, source-reviewed"))]
    phrases = [
        ("immediate hazard", ("other_phase", "other_station", "ego_entry")),
        ("proceed cautiously", ("ego_speed", "ego_entry", "officer_directive")),
        ("yielding to vehicles not so obligated to stop or yield",
         ("other_phase", "other_station", "entrance_controls"))]
    template = {"template_id": ident, "law_id": law["id"],
                "actor": plan["actor"], "quote": quote,
                "structure": {"law_id": law["id"],
                    "activation": {"condition": "Sign-governed vehicle entry at a non-through intersection only when neither officer nor signal controls traffic.",
                                   "numeric_conditions": []},
                    "obligation": {"description": "When activated, obey the applicable sign in subsection 1 manner, proceed cautiously and yield to non-obligated traffic within or immediately approaching during across-or-within movement.",
                                   "type": "must", "numeric_conditions": []},
                    "exceptions": [{"trigger": "Traffic controlled by police officer or traffic-control signal",
                                    "effect": "This subsection yields to that control",
                                    "replacement_obligation": "Follow controlling officer or signal under its applicable law",
                                    "source_clause": "Except when traffic is being controlled by a police officer or a traffic-control signal"}],
                    "timing": {"description": "Before entry for sign obedience and throughout across-or-within movement when the subsection is activated; officer control is an exception context.",
                               "numeric_conditions": []},
                    "judgment_calls_needed": [{"phrase": phrase, "note": ""}
                                              for phrase, _ in phrases]},
                "parameter_refs": params}
    refs["template"] = write("template.json", template)
    units = {row["name"]: row["unit"] for row in recording["channels"]}
    judgments = []
    for index, (phrase, channels) in enumerate(phrases):
        needs = [{"name": name, "unit": units[name],
                  "description": "Original source-bound measurement for " + phrase}
                 for name in channels]
        judgments.append(write(f"judgment-{index}.json", {
            "template_id": ident, "phrase": phrase, "note": "", "status": "draft",
            "observable_requirements": {"observables": needs,
                "context_inputs": [{"name": "reviewed_officer_site_packet",
                                    "unit": "source record",
                                    "description": "Reviewed officer, map, all entrances and routes"}],
                "sweep_dimensions": [{"name": "requested_other_station_m", "unit": "m",
                                      "description": "Requested station, measured independently"}],
                "landmarks": [], "recording_needs": needs,
                "limitations": ["No numeric legal hazard or caution threshold is supplied.",
                                "The officer exception prevents assuming the sign duty applies during active control."]}}))
    refs["judgment_observables"] = judgments
    binding = {"cell_id": plan["cell_id"], "actor": plan["actor"],
               "status": "draft",
               "established_contexts": ["Original active officer governance and directive review pending"],
               "law_refs": [{"template_id": ident, "binding_kind": "direct"}],
               "context_refs": [], "fixed_parameters": [],
               "variable_parameters": [{**row, "used_by_laws": [law["id"]]}
                                       for row in params]}
    refs["bindings"] = write("bindings.json", binding)

    def variables(values):
        return {p["name"]: {"kind": p["kind"], "value": values[p["name"]],
                            "note": "Requested setup; original source measured separately"}
                for p in params}

    baseline = plan["cases"][0]["draft_variables"]
    cases = [{"case_id": ROOT.name + "__baseline", "target_law_id": None,
              "target_type": "baseline", "rationale": "Neutral source context, no legal label or execution.",
              "variable_assignments": variables(baseline),
              "unresolved_judgment_calls": [],
              "recording_description": recording}]
    for row in plan["cases"]:
        values = row["draft_variables"]
        changed = [key for key in baseline if values[key] != baseline[key]]
        comparison = next((c["comparison_id"] for c in plan["comparisons"]
                           if row["case_id"] in c["case_ids"]), "officer_context")
        variable = changed[0] if changed else "other_phase"
        cases.append({"case_id": row["case_id"], "target_law_id": law["id"],
                      "target_type": "boundary_probe",
                      "rationale": "Original officer directive and counterpart phase probe; physical/legal result unresolved.",
                      "paired_probe_id": comparison,
                      "deliberate_differences": changed or ["other_phase"],
                      "probe": {"primary_variable": variable,
                                "comparison_or_standard": "same reviewed officer intersection and original measured response",
                                "target_value_or_branch": values[variable]},
                      "variable_assignments": variables(values),
                      "unresolved_judgment_calls": [phrase for phrase, _ in phrases],
                      "recording_description": recording})
    sweeps = [{"sweep_id": name, "target_law_id": law["id"],
               "judgment_refs": [{"phrase": phrase, "note": ""}],
               "status": "incomplete",
               "rationale": "Original officer/participant measurements and physical range targets need a reviewed site and Native capture.",
               "missing_inputs": ["Reviewed original officer gesture, body motion and independent source-video coverage"]}
              for name, phrase in (("immediate_hazard_source_review", phrases[0][0]),
                                   ("caution_source_review", phrases[1][0]),
                                   ("non_obligated_yield_source_review", phrases[2][0]))]
    refs["cases"] = write("cases.json", {
        "cell_id": plan["cell_id"], "actor": plan["actor"], "status": "draft",
        "cases": cases, "sweep_specs": sweeps, "sweeps_expanded": True,
        "semantic_status": "partial_source_gated_officer_exception"})
    write("semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": ROOT.name, "stages": refs,
        "status": "partial_source_gated_officer_exception"})
    print("authored", len(cases) - 1, "officer semantic cases")


if __name__ == "__main__":
    main()
