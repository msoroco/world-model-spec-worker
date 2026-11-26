"""Author draft canonical stages for the exact restricted-zone comparison."""

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ASSIGNMENT = ROOT.name
LAW_ID = "NRS-484B-510"
ACTOR = "motor_vehicle_driver"
TEMPLATE_ID = LAW_ID + "@" + ACTOR


def dump(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assignment = json.loads((REPO / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    plan = json.loads((ROOT / "case-plan.json").read_text())
    manifest = json.loads((ROOT / "execution-manifest.json").read_text())
    folder = ROOT / "proposals"
    folder.mkdir(exist_ok=True)
    law_text = assignment["law"]["text"]
    relevance = {"cell_id": "C135087", "actor": ACTOR, "status": "draft",
        "relevant_laws": [{"law_id": LAW_ID, "quote": law_text, "applies_to": [ACTOR],
                           "relevance_type": "conditional restricted-zone branch",
                           "confidence": "medium",
                           "notes": "Original restricted-zone authority and participant status require source review."}],
        "borderline_excluded": []}
    dump(folder / "relevance.json", relevance)
    dump(folder / "relevance_batch.json", relevance)
    judgments = [
        {"phrase": "temporarily", "note": "duration of passenger-vehicle stop"},
        {"phrase": "interfere", "note": "effect on restricted-purpose entrant"},
        {"phrase": "about to enter", "note": "entrant approach to restricted zone"}]
    exception_clause = law_text[law_text.index("except that a driver"):]
    template = {"template_id": TEMPLATE_ID, "law_id": LAW_ID, "actor": ACTOR,
        "status": "draft", "quote": law_text,
        "structure": {"law_id": LAW_ID,
            "activation": {"condition": "vehicle stop, stand or park in source-confirmed restricted parking zone",
                           "numeric_conditions": []},
            "obligation": {"description": "no use outside the purpose to which zone is restricted",
                           "type": "must_not", "numeric_conditions": []},
            "exceptions": [{"trigger": "passenger-vehicle loading or unloading while actually engaged",
                            "effect": "exception subject to temporary stop and no interference with restricted-purpose entrant",
                            "replacement_obligation": "retain original source observations for later judgment",
                            "source_clause": exception_clause}],
            "timing": {"description": "any purpose or length of time; passenger exchange exception has temporal conditions",
                       "numeric_conditions": []},
            "judgment_calls_needed": judgments},
        "parameter_refs": [{"name": "entrant_departure_s", "kind": "controller",
                            "range_or_domain": "source-reviewed feasible approach timing"},
                           {"name": "subject_departure_s", "kind": "controller",
                            "range_or_domain": "source-reviewed feasible departure timing"}]}
    dump(folder / "template.json", template)
    for index, judgment in enumerate(judgments):
        phrase = judgment["phrase"]
        focus = {"temporarily": "subject_zone_dwell",
                 "interfere": "entrant_access",
                 "about to enter": "entrant_access"}[phrase]
        observables = {"observables": [{"name": focus, "unit": "state" if focus == "entrant_access" else "s",
                                          "description": "original 20 Hz physical history relevant to " + phrase}],
                       "context_inputs": [{"name": "reviewed_restricted_zone", "unit": "source record",
                                           "description": "original zone purpose, authority, boundaries and effective conditions"}],
                       "sweep_dimensions": [], "landmarks": [],
                       "recording_needs": [{"name": focus, "unit": "state" if focus == "entrant_access" else "s",
                                            "description": "full saved observation stream for " + phrase}],
                       "limitations": ["No legal cutoff or surrogate is inferred for " + phrase + "."]}
        dump(folder / ("judgment-" + str(index) + ".json"),
             {"template_id": TEMPLATE_ID, "phrase": phrase, "note": judgment["note"],
              "status": "draft", "observable_requirements": observables})
    binding = {"cell_id": "C135087", "actor": ACTOR, "status": "draft",
        "established_contexts": [], "law_refs": [{"template_id": TEMPLATE_ID,
                                              "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{"name": name, "kind": "controller",
                                 "range_or_domain": "site-tested timing in seconds",
                                 "used_by_laws": [TEMPLATE_ID]} for name in
                                ("entrant_departure_s", "subject_departure_s")]}
    dump(folder / "bindings.json", binding)
    description = json.loads((ROOT / manifest["cases"][0]["construction"]).read_text())["recording_description"]
    def assignments(entrant, subject):
        return {"entrant_departure_s": {"kind": "controller", "value": entrant, "unit": "s"},
                "subject_departure_s": {"kind": "controller", "value": subject, "unit": "s"}}
    canonical_cases = [{"case_id": ASSIGNMENT + "__baseline", "target_law_id": None,
                        "target_type": "baseline", "rationale": "neutral planning reference only",
                        "variable_assignments": assignments(6, 24),
                        "recording_description": description,
                        "unresolved_judgment_calls": [j["phrase"] for j in judgments]}]
    for case in plan["cases"]:
        parameters = case["scenario_parameters"]
        suffix = case["case_id"].removeprefix(ASSIGNMENT + "__")
        canonical_cases.append({"case_id": case["case_id"], "target_law_id": LAW_ID,
            "target_type": "boundary_probe", "rationale": case["purpose"],
            "paired_probe_id": "restricted_entrant_timing",
            "deliberate_differences": ["entrant_departure_s", "subject_departure_s"],
            "probe": {"primary_variable": "entrant_departure_s",
                      "comparison_or_standard": "restricted-purpose entrant relative to exchange",
                      "target_value_or_branch": suffix},
            "variable_assignments": assignments(parameters["entrant_departure_s"],
                                                parameters["subject_departure_s"]),
            "recording_description": description,
            "unresolved_judgment_calls": [j["phrase"] for j in judgments]})
    sweep_specs = [{"sweep_id": "pending-" + str(index), "target_law_id": LAW_ID,
                    "judgment_refs": [judgment], "status": "incomplete",
                    "rationale": "preserve qualitative physical coverage without invented legal bounds",
                    "missing_inputs": ["source-reviewed restricted zone and feasible original Native timing range"]}
                   for index, judgment in enumerate(judgments)]
    cases = {"cell_id": "C135087", "actor": ACTOR, "status": "draft",
             "cases": canonical_cases, "sweep_specs": sweep_specs,
             "sweeps_expanded": True}
    dump(folder / "cases.json", cases)
    stages = {name: {"path": "proposals/" + name + ".json",
                     "sha256": sha(folder / (name + ".json"))}
              for name in ("relevance_batch", "relevance", "template", "bindings", "cases")}
    stages["judgment_observables"] = [{"path": "proposals/judgment-" + str(i) + ".json",
                                       "sha256": sha(folder / ("judgment-" + str(i) + ".json"))}
                                      for i in range(len(judgments))]
    dump(folder / "semantic-index.json", {"format": "worker-semantic-delivery",
                                           "assignment_id": ASSIGNMENT,
                                           "status": "draft_source_gated", "stages": stages})
    print("draft canonical stages:", len(stages) + len(judgments) - 1)


if __name__ == "__main__":
    main()
