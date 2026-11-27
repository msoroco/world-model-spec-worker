"""Canonical semantic chain for the signed roadway riding witness pair."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent.parent
REPO = HERE.parents[1]
AID = HERE.name


def put(name, value):
    path = HERE / "proposals" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")
    return {"path": str(path.relative_to(HERE)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    original = json.loads((REPO / "inputs" / AID / "assignment.json").read_text())
    law = original["law"]
    law_id = law["id"]
    actor = original["actor"]
    tid = law_id + "@" + actor
    rec = json.loads((HERE / "construction.json").read_text())["recording_description"]
    relevance = {"cell_id": original["cell_id"], "actor": actor, "status": "draft",
                 "relevant_laws": [{"law_id": law_id, "quote": law["text"],
                                    "applies_to": [actor], "relevance_type": "direct",
                                    "confidence": "high", "notes": "Signed roadway riding branch in frozen cell."}],
                 "borderline_excluded": []}
    refs = {"relevance_batch": put("relevance-batch.json", relevance),
            "relevance": put("relevance.json", relevance)}
    judgment = {"phrase": "impede or interfere with the flow of pedestrian or vehicular traffic",
                "note": "Director determination and consultation require source review; no numerical cutoff is supplied."}
    template = {"template_id": tid, "law_id": law_id, "actor": actor,
                "status": "draft", "quote": law["text"],
                "structure": {"activation": {"description": "A reviewed prohibition sign is physically in place on the roadway and governs the covered rider."},
                              "obligation": {"type": "must_not",
                                             "description": "Do not disobey the physically erected applicable prohibition sign by riding in its governed roadway interval.",
                                             "numeric_conditions": []},
                              "exceptions": [],
                              "timing": {"description": "At each instant of actual riding within the sign-governed interval."},
                              "judgment_calls_needed": [judgment]},
                "parameter_refs": [
                    {"name": "signed_roadway_context", "kind": "world_setup",
                     "range_or_domain": "reviewed sign, roadway and Director sources"},
                    {"name": "requested_route_kind", "kind": "controller",
                     "range_or_domain": ["outside", "enter"]},
                    {"name": "observed_ridden_signed_frames", "kind": "subject_behavior",
                     "range_or_domain": "source-joined nonnegative frame count"}]}
    refs["template"] = put("template.json", template)
    observable = {"template_id": tid, "phrase": judgment["phrase"],
                  "note": judgment["note"], "status": "draft",
                  "observable_requirements": {
                      "observables": [{"name": "dev.regulatory_sign", "unit": "structured",
                                       "description": "Original physical sign and governed roadway source."},
                                      {"name": "rel.occupies", "unit": "structured",
                                       "description": "Rider source position relative to signed interval."}],
                      "context_inputs": [{"name": "sign_source_review", "unit": "structured",
                                          "description": "Hash-bound sign pixels and Director determination sources."}],
                      "sweep_dimensions": [], "landmarks": [],
                      "recording_needs": [{"name": "dev.position", "unit": "structured",
                                           "description": "Original sign position."},
                                          {"name": "st.roadway", "unit": "structured",
                                           "description": "Original governed roadway geometry."}],
                      "limitations": ["Director traffic-flow determination is administrative and cannot be inferred from synthetic riding frames."]}}
    refs["judgment_observables"] = [put("judgment-flow.json", observable)]
    binding = {"cell_id": original["cell_id"], "actor": actor, "status": "draft",
               "established_contexts": [],
               "law_refs": [{"template_id": tid, "binding_kind": "direct"}],
               "context_refs": [], "fixed_parameters": [],
               "variable_parameters": [{"name": name, "kind": kind,
                                        "range_or_domain": domain,
                                        "used_by_laws": [law_id]}
                                       for name, kind, domain in (
                                           ("signed_roadway_context", "world_setup", "source reviewed sign and authority"),
                                           ("requested_route_kind", "controller", "outside or enter"),
                                           ("observed_ridden_signed_frames", "subject_behavior", "source measured frames"))]}
    refs["bindings"] = put("bindings.json", binding)
    base = {"signed_roadway_context": {"kind": "world_setup", "value": "original review required"},
            "requested_route_kind": {"kind": "controller", "value": "outside"},
            "observed_ridden_signed_frames": {"kind": "subject_behavior", "value": None}}
    cases = [{"case_id": AID + "__neutral_baseline", "target_law_id": None,
              "target_type": "baseline", "rationale": "Unselected neutral source reference.",
              "variable_assignments": base, "unresolved_judgment_calls": [],
              "recording_description": rec}]
    for suffix, route in (("witness_1", "outside"), ("witness_2", "enter")):
        assignments = json.loads(json.dumps(base))
        assignments["requested_route_kind"]["value"] = route
        cases.append({"case_id": AID + "__" + suffix, "target_law_id": law_id,
                      "target_type": "judgment_sweep",
                      "rationale": "Source-joined controlled route outside or into one reviewed signed roadway interval; no legal verdict.",
                      "variable_assignments": assignments,
                      "unresolved_judgment_calls": [judgment["phrase"]],
                      "recording_description": rec,
                      "paired_probe_id": AID + "__witness_comparison",
                      "deliberate_differences": ["requested_route_kind"],
                      "probe": {"primary_variable": "requested_route_kind",
                                "comparison_or_standard": "physical sign-governed roadway occupancy",
                                "target_value_or_branch": route}})
    proposal = {"cell_id": original["cell_id"], "actor": actor,
                "status": "draft", "sweeps_expanded": True,
                "sweep_specs": [{"sweep_id": "director-flow-determination",
                                 "target_law_id": law_id, "judgment_refs": [judgment],
                                 "status": "incomplete",
                                 "rationale": "Original Director and consultation sources remain to review.",
                                 "missing_inputs": ["Original Director determination and sign authority sources."]}],
                "cases": cases}
    refs["cases"] = put("cases.json", proposal)
    put("semantic-index.json", {"format": "worker-semantic-delivery",
                                "assignment_id": AID, "stages": refs})


if __name__ == "__main__":
    build()
