"""Write source-quoted draft stages for the exact six selected probes."""
import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "runtime/scenario_pipeline"))
from batch_pipeline import stages


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(name, obj):
    path = HERE / "proposals" / name
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n")
    return {"path": "proposals/" + name, "sha256": sha(path)}


def named(name, description):
    return {"name": name, "unit": "structured record", "description": description}


def requirements(phrase):
    detail = ("Retain both direction Native ray samples, actor bodies and source frames; "
              "virtual eye visibility is a proxy and cannot establish driver recognition.")
    if phrase == "near the crest of a grade":
        detail = ("Retain original map grade/crest geometry and turn pose history; "
                  "whether the turn is legally near the crest remains unresolved.")
    return {"observables": [named("sight_distance", "Two direction sampled sight and occlusion evidence"),
                             named("u_turn_motion", "Original ego pose and heading through the turn"),
                             named("approaching_actors", "Original approaching actor poses, lanes and velocities")],
            "context_inputs": [], "sweep_dimensions": [], "landmarks": [],
            "recording_needs": [named("sight_distance", "Source-bound ray and visibility samples"),
                                named("u_turn_motion", "Source-bound U-turn motion"),
                                named("approaching_actors", "Both approaching directions")],
            "limitations": [detail]}


def build():
    assignment = json.loads((ROOT / "inputs" / HERE.name / "assignment.json").read_text())
    law, actor, cell = assignment["law"], assignment["actor"], assignment["cell_id"]
    aid, law_id, quote = assignment["assignment_id"], assignment["law_id"], law["text"]
    template_id = law_id + "@" + actor
    relevance = {"cell_id": cell, "actor": actor, "status": "draft", "relevant_laws": [{
        "law_id": law_id, "quote": quote, "applies_to": [actor],
        "relevance_type": "direct selected U-turn restriction", "confidence": "high",
        "notes": "Selected cell has a U-turn on a mountain road; Native map and visibility require review."}],
        "borderline_excluded": []}
    refs = {"relevance_batch": write("relevance-batch.json", relevance),
            "relevance": write("relevance.json", relevance)}
    judgments = [
        {"phrase": "near the crest of a grade", "note": "No invented distance defines near; retain source geometry and pose."},
        {"phrase": "cannot be seen by the driver", "note": "Virtual eye rays are physical proxies; driver recognition is unresolved."},
    ]
    template = {"template_id": template_id, "law_id": law_id, "actor": actor, "status": "draft",
                "quote": quote, "structure": {
                    "law_id": law_id,
                    "activation": {"condition": "U-turn upon curve or approach to/near grade crest",
                                   "numeric_conditions": []},
                    "obligation": {"type": "must_not", "description": "Vehicle shall not be turned to proceed opposite direction in the stated visibility circumstance",
                                   "approach_distance_condition": {"variable": "approach_distance_ft", "operator": "<=",
                                                                   "value": 500, "unit": "ft"}},
                    "exceptions": [], "timing": {"description": "at the turn and approaches from either direction",
                                                  "numeric_conditions": []},
                    "judgment_calls_needed": judgments},
                "parameter_refs": [
                    {"name": "feature", "kind": "world_setup", "range_or_domain": "curve or crest"},
                    {"name": "probe", "kind": "world_setup", "range_or_domain": "below, at or beyond 500 ft"}]}
    refs["template"] = write("template.json", template)
    observation_refs = []
    for index, j in enumerate(judgments, start=1):
        observation_refs.append(write("judgment-observables-" + str(index) + ".json", {
            "template_id": template_id, "phrase": j["phrase"], "note": j["note"],
            "status": "draft", "observable_requirements": requirements(j["phrase"])}))
    refs["judgment_observables"] = observation_refs
    binding = {"cell_id": cell, "actor": actor, "status": "draft",
               "established_contexts": ["Frozen mountain-road U-turn cell; source road geometry and visibility unconfirmed"],
               "law_refs": [{"template_id": template_id, "binding_kind": "direct"}], "context_refs": [],
               "fixed_parameters": [{"name": "selected_cell", "value": cell, "rationale": "Frozen assignment cell"}],
               "variable_parameters": [
                   {"name": "feature", "kind": "world_setup", "range_or_domain": "curve or crest",
                    "used_by_laws": [law_id]},
                   {"name": "probe", "kind": "world_setup", "range_or_domain": "short, at or beyond 500 ft",
                    "used_by_laws": [law_id]}]}
    refs["bindings"] = write("bindings.json", binding)
    cases = json.loads((HERE / "proposals/cases.json").read_text())
    if len(cases["cases"]) not in (6, 7):
        raise ValueError("Unexpected selected case count")
    selected = [c for c in cases["cases"] if c["target_type"] != "baseline"]
    if len(selected) != 6:
        raise ValueError("Exact six selected cases required")
    baseline = {"case_id": aid + "__neutral_baseline", "target_law_id": law_id,
                "target_type": "baseline", "rationale": "Shared fixed conditions for source comparison",
                "variable_assignments": selected[0]["variable_assignments"],
                "recording_description": selected[0]["recording_description"],
                "unresolved_judgment_calls": [j["phrase"] for j in judgments]}
    cases["cases"] = [baseline] + selected
    for case in selected:
        probe = case["variable_assignments"]["probe"]["value"]
        case["target_type"] = "boundary_probe"
        case["paired_probe_id"] = "nrs-484b-407-two-direction-boundary"
        case["deliberate_differences"] = ["feature", "probe"]
        case["probe"] = {"primary_variable": "probe", "comparison_or_standard": "statutory 500-foot approach distance; actual driver visibility unresolved",
                         "target_value_or_branch": probe, "threshold_ref": "obligation.approach_distance_condition",
                         "test_value": {"short_of_500ft": 490, "at_500ft": 500, "beyond_500ft": 525}[probe],
                         "operator": "<=", "unit": "ft"}
        case["epsilon_used"] = {"value": 10, "unit": "ft", "rationale": "Engineering probe separation, not legal tolerance"}
        case["unresolved_judgment_calls"] = [j["phrase"] for j in judgments]
    cases["sweep_specs"] = [{"sweep_id": "nrs-484b-407-driver-visibility", "target_law_id": law_id,
                             "judgment_refs": judgments, "status": "incomplete",
                             "rationale": "Driver recognition and proximity to a crest need source-grounded range selection without a numerical legal threshold.",
                             "missing_inputs": ["Reviewed Native map/camera/actor evidence to bound a meaningful physical sweep and its feasibility."]}]
    cases["sweeps_expanded"] = True  # No complete sweep points exist to expand yet.
    refs["cases"] = write("cases.json", cases)
    refs_path = HERE / "proposals/semantic-index.json"
    refs_path.write_text(json.dumps({"format": "worker-semantic-delivery", "assignment_id": aid,
                                     "stages": refs}, indent=2, sort_keys=True) + "\n")
    from worker_exchange import semantic_delivery
    # Stage and source quote validation is CPU-only. The temporary manifest is
    # only an identity list; canonical execution manifest is built separately.
    report = semantic_delivery.validate(HERE, assignment, {"cases": [
        {"case_id": c["case_id"], "construction": "construction" + (
            "-crest-" if c["variable_assignments"]["feature"]["value"] == "crest" else
            "-" if c["variable_assignments"]["probe"]["value"] != "short_of_500ft" else "") +
            (c["variable_assignments"]["probe"]["value"].replace("_of_500ft", "").replace("_500ft", "")
             if c["variable_assignments"]["feature"]["value"] == "crest" or
                c["variable_assignments"]["probe"]["value"] != "short_of_500ft" else "") + ".json"}
        for c in selected]})
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    build()
