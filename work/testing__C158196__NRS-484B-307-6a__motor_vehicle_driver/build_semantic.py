"""Author canonical draft stages for the seven exact yellow/red signal cases."""

import hashlib
import json
from pathlib import Path

from construction import CASE_PROFILES
from package_spec import RECORDING

HERE = Path(__file__).resolve().parent
PROPOSALS = HERE / "proposals"


def put(name, value):
    PROPOSALS.mkdir(exist_ok=True)
    path = PROPOSALS / name
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
    return {"path": str(path.relative_to(HERE)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def assignment(value):
    return {"kind": "world_setup", "value": value, "unit": "source request"}


def build():
    plan_path = HERE / "case-plan.json"
    plan = json.loads(plan_path.read_text())
    aid, law, actor = plan["assignment_id"], plan["law_id"], plan["actor"]
    quote = plan["law_text"]
    case_ids = [case["case_id"] for case in plan["cases"]]
    if len(case_ids) != 7 or len(set(case_ids)) != 7:
        raise ValueError("seven exact signal cases required")
    plan["source_observation_mapping"] = {}
    plan["camera_plan"] = {"profile": "overview1080-capability", "duration_s": 45,
        "composition": "synchronized_four_view_primary",
        "coverage": [
            {"view": "overview", "subject": "ego, intersection and official head",
             "interval": "startup through final frame"},
            {"view": "approach", "subject": "ego front and surveyed entry",
             "interval": "approach through entry or stop"},
            {"view": "reference_corner", "subject": "selected and other route signal heads",
             "interval": "green through red"},
            {"view": "driver_reference", "subject": "driver-facing indication and route",
             "interval": "startup through final frame"}],
        "limitation": "Original physical visibility and legal judgment require local review"}
    plan_path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n")
    relevance = {"cell_id": plan["cell_id"], "actor": actor, "status": "draft",
        "relevant_laws": [{"law_id": law, "quote": quote, "applies_to": [actor],
                           "confidence": "high"}], "borderline_excluded": []}
    relevance_ref = put("relevance.json", relevance)
    put("relevance-batch.json", relevance)
    template_id = law + "@" + actor
    parameters = [{"name": name, "kind": "world_setup", "range_or_domain": domain,
                   "unit": "source request"} for name, domain in (
        ("entry_phase", "green, steady yellow or red source observation"),
        ("ego_behavior", "traverse or stop before surveyed entry"),
        ("companion_indication", "source-bound absent or observed"),
        ("other_route_red", "separate route red source observation"))]
    template_ref = put("template.json", {"template_id": template_id,
        "law_id": law, "actor": actor, "status": "draft", "quote": quote,
        "structure": {"law_id": law,
            "activation": {"condition": "Vehicular traffic faces a steady yellow signal alone on its governed route.",
                           "numeric_conditions": []},
            "obligation": {"description": "Warning of related green termination or immediately following red; no entry when red is exhibited.",
                           "type": "must_not", "numeric_conditions": []},
            "exceptions": [{"source_clause": "steady yellow signal alone",
                            "disposition": "companion indication changes applicability; original readback required"}],
            "timing": {"description": "Original selected route signal state at surveyed body entry.",
                       "numeric_conditions": []},
            "judgment_calls_needed": [
                {"phrase": "enter the intersection", "note": "20 Hz front/polygon bracket is evidence, not a legal boundary."},
                {"phrase": "immediately thereafter", "note": "Observed phase delay is not a statutory numeric cutoff."}]},
        "parameter_refs": parameters})
    judgment_refs = []
    for slug, phrase, note, channels in (
        ("entry", "enter the intersection", "Surveyed front/polygon bracket does not resolve legal entry alone.",
         ("intersection_entry_bracket", "camera_frame_identity")),
        ("immediately", "immediately thereafter", "Observed yellow duration does not define a legal threshold.",
         ("selected_facing_signal_sequence", "signal_vs_entry"))):
        judgment_refs.append(put("judgment-" + slug + ".json", {
            "template_id": template_id, "phrase": phrase, "note": note, "status": "draft",
            "observable_requirements": {
                "observables": [{"name": name, "unit": next(c["unit"] for c in RECORDING["channels"] if c["name"] == name),
                                 "description": "Original source-joined " + name.replace("_", " ")}
                                for name in channels],
                "context_inputs": [{"name": "reviewed_native_signal_scene", "unit": "source record",
                                    "description": "Source-hashed map, polygon, routes and official devices"}],
                "sweep_dimensions": [], "landmarks": [],
                "recording_needs": [{"name": name, "unit": next(c["unit"] for c in RECORDING["channels"] if c["name"] == name),
                                     "description": "Original 20 Hz " + name.replace("_", " ")}
                                    for name in channels],
                "limitations": ["Original physical and legal review remains unresolved."]}}))
    bindings_ref = put("bindings.json", {"cell_id": plan["cell_id"], "actor": actor,
        "status": "draft", "law_refs": [{"template_id": template_id, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [dict(parameter, used_by_laws=[law]) for parameter in parameters]})
    baseline_values = {"entry_phase": "yellow", "ego_behavior": "traverse",
                       "companion_indication": "absent", "other_route_red": "unobserved"}
    baseline = {"case_id": aid + "__baseline", "target_law_id": None,
        "target_type": "baseline", "status": "draft",
        "rationale": "Common surveyed route/head baseline; no original acceptance or legal verdict.",
        "variable_assignments": {name: assignment(value) for name, value in baseline_values.items()},
        "unresolved_judgment_calls": ["enter the intersection", "immediately thereafter"],
        "recording_description": RECORDING}
    selected = [baseline]
    for case in plan["cases"]:
        slug = case["case_id"].removeprefix(aid + "__")
        profile = CASE_PROFILES[slug]
        values = {"entry_phase": profile["entry_phase"],
                  "ego_behavior": profile["behavior"],
                  "companion_indication": "observed" if slug == "yellow_non_alone" else "absent",
                  "other_route_red": "observed" if slug == "red_other_route" else "unobserved"}
        selected.append({"case_id": case["case_id"], "target_law_id": law,
            "target_type": "boundary_probe", "status": "draft",
            "rationale": "Original selected-route signal and body entry are measured; legal reading unresolved.",
            "paired_probe_id": slug,
            "deliberate_differences": [name for name in values if values[name] != baseline_values[name]],
            "variable_assignments": {name: assignment(value) for name, value in values.items()},
            "unresolved_judgment_calls": ["enter the intersection", "immediately thereafter"],
            "recording_description": RECORDING,
            "probe": {"primary_variable": "entry_phase",
                      "comparison_or_standard": "Compare original governed head, other route, phase and body-entry brackets.",
                      "target_value_or_branch": slug}})
    sweep = {"sweep_id": "signal-timing-review", "target_law_id": law,
        "judgment_refs": [{"phrase": phrase, "note": note} for phrase, note in (
            ("enter the intersection", "Source body/polygon ambiguity remains."),
            ("immediately thereafter", "No statutory numeric timing cutoff.") )],
        "status": "incomplete", "rationale": "Original timing and visual ranges are unavailable for a judgment sweep.",
        "missing_inputs": ["Reviewed original physical phase/entry brackets and legal scope decisions"]}
    cases_ref = put("cases.json", {"cell_id": plan["cell_id"], "actor": actor,
        "status": "draft", "sweep_specs": [sweep], "sweeps_expanded": True,
        "cases": selected})
    put("semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": aid,
        "stages": {"relevance_batch": relevance_ref, "relevance": relevance_ref,
                   "template": template_ref, "judgment_observables": judgment_refs,
                   "bindings": bindings_ref, "cases": cases_ref},
        "status": "source_gated_draft"})
    return len(plan["cases"])


if __name__ == "__main__":
    print("semantic exact cases:", build())
