"""Build source-backed, conditional canonical stage proposals for C111662.

The frozen cell does not establish a business district. These artifacts retain
that guard and do not activate the law or assert a legal verdict.
"""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / "runtime/pipeline/scenario_pipeline"))
from batch_pipeline import stages  # noqa: E402


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(name, value):
    path = ROOT / "proposals" / (name + ".json")
    path.write_text(json.dumps(value, indent=2) + "\n")
    return {"path": str(path.relative_to(ROOT)), "sha256": sha(path)}


def build():
    assignment_path = REPO / "inputs" / ROOT.name / "assignment.json"
    assignment = json.loads(assignment_path.read_text())
    law = assignment["law_record"]
    law_id, cell_id, actor = assignment["law_id"], assignment["cell_id"], assignment["actor"]
    quote = law["text"]
    assert law["id"] == law_id and "business district" in quote
    request = {"cell": assignment["cell"], "actor": actor}
    relevance = {
        "cell_id": cell_id, "actor": actor, "status": "draft",
        "relevant_laws": [{"law_id": law_id, "quote": quote,
                           "applies_to": [actor], "relevance_type": "specific_match",
                           "confidence": "low",
                           "notes": "The U-turn/intersection cell is compatible; business-district use and boundaries are not established by the frozen cell."}],
        "borderline_excluded": []}
    common = {"request": request, "law_records": {law_id: law}, "dependencies": []}
    stages.validate("relevance_batch", relevance, common)
    stages.validate("relevance", relevance, common)
    relevance_batch_ref = write("relevance_batch", relevance)
    relevance_ref = write("relevance", relevance)

    opening_phrase = "appropriate opening or crossing place"
    opening_note = "Qualitative condition in the divided-highway exception; geometry alone does not settle it."
    template = {
        "template_id": law_id + "@" + actor, "law_id": law_id, "actor": actor,
        "status": "draft", "quote": quote,
        "structure": {
            "activation": {"context": "in a business district",
                           "subject": "driver of a vehicle"},
            "obligation": {"type": "must_not", "action": "make a U-turn",
                           "source_clause": "shall not make a U-turn"},
            "exceptions": [
                {"name": "intersection", "source_clause": "except at an intersection",
                 "replacement_obligation": "none stated"},
                {"name": "divided_highway_opening",
                 "source_clause": "on a divided highway where an appropriate opening or crossing place exists",
                 "replacement_obligation": "none stated"}],
            "timing": {"description": "at the place where the U-turn is made",
                       "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": opening_phrase, "note": opening_note}]},
        "parameter_refs": [
            {"name": "business_district_context", "kind": "world_setup", "range_or_domain": "source-verified jurisdictional context"},
            {"name": "intersection_footprint", "kind": "world_setup", "range_or_domain": "generated joined-highway geometry"},
            {"name": "divided_highway_opening", "kind": "world_setup", "range_or_domain": "generated divided-highway crossing geometry"},
            {"name": "ego_trajectory", "kind": "subject_behavior", "range_or_domain": "observed original vehicle path"}]}
    rules = json.loads((stages.ROOT / "data/canonical_parameter_aliases.json").read_text())
    stages.validate("template", template, {"request": {"law_id": law_id, "actor": actor},
                                          "law_record": law, "canonical_parameter_rules": rules,
                                          "dependencies": []})
    template_ref = write("template", template)

    observable = {
        "template_id": template["template_id"], "phrase": opening_phrase,
        "note": opening_note, "status": "draft",
        "observable_requirements": {
            "observables": [
                {"name": "ego_pose", "unit": "structured", "description": "Saved original vehicle body and heading history around the crossing."},
                {"name": "u_turn_at_intersection_or_opening", "unit": "bool", "description": "Measured spatial relation of the vehicle turn to the recorded candidate crossing area."}],
            "context_inputs": [
                {"name": "authored_road", "unit": "structured", "description": "Source-hashed road request, to be checked against generated Native topology."},
                {"name": "authored_frontage", "unit": "structured", "description": "Source-hashed frontage request; actual use and district boundaries need separate review."}],
            "sweep_dimensions": [], "landmarks": [],
            "recording_needs": [
                {"name": "ego_pose", "unit": "structured", "description": "Original frame-joined body path and heading."},
                {"name": "u_turn_at_intersection_or_opening", "unit": "bool", "description": "Saved spatial relation with source geometry."}],
            "limitations": ["The statute gives no numeric meaning for appropriate; retained geometry and pixels require independent review.",
                            "An authored opening or frontage plan does not establish generated geometry, business use, or legal applicability."]}}
    stages.validate("judgment_observables", observable,
                    {"request": {"template_id": template["template_id"],
                                 "phrase": opening_phrase, "note": opening_note},
                     "dependencies": []})
    observable_ref = write("judgment_observables_opening", observable)

    binding = {
        "cell_id": cell_id, "actor": actor, "status": "draft",
        "established_contexts": [{"name": "intersection_layout", "source": "frozen catalog cell"}],
        "law_refs": [],
        "context_refs": [{"template_id": template["template_id"],
                          "missing_guards": ["business_district_building_use_and_boundaries"]}],
        "fixed_parameters": [], "variable_parameters": []}
    stages.validate("bindings", binding,
                    {"request": dict(request, template_ids=[template["template_id"]]),
                     "canonical_parameter_rules": rules, "dependencies": [template]})
    binding_ref = write("bindings", binding)
    receipt = {
        "format": "c111662-semantic-foundation-proof-v1",
        "assignment_id": ROOT.name,
        "assignment_sha256": sha(assignment_path),
        "stages_validated": ["relevance_batch", "relevance", "template",
                             "judgment_observables", "bindings"],
        "references": {"relevance_batch": relevance_batch_ref,
                       "relevance": relevance_ref, "template": template_ref,
                       "judgment_observables": [observable_ref],
                       "bindings": binding_ref},
        "conditional_guard": "business_district_building_use_and_boundaries",
        "canonical_cases_and_index_complete": False,
        "legal_verdict": None,
        "scope": "validated source-backed draft stages only; no active law binding or accepted original"}
    output = ROOT / "proposals/semantic-foundation-proof.json"
    output.write_text(json.dumps(receipt, indent=2) + "\n")
    return {"stages_validated": len(receipt["stages_validated"]),
            "proof_sha256": sha(output)}


if __name__ == "__main__":
    print(json.dumps(build()))
