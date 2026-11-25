"""Author source-gated exact NRS 484B.293 semantic stage proposals."""

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
P = ROOT / "proposals"
LAW = "NRS-484B-293"
ACTOR = "pedestrian"
TEMPLATE = LAW + "@" + ACTOR


def write(name, value):
    path = P / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    return {"path": str(path.relative_to(ROOT)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    plan = json.loads((ROOT / "case-plan.json").read_text())
    quote = plan["law_text"]
    common = {"status": "draft", "cell_id": "C150911", "actor": ACTOR}
    relevance = dict(common, relevant_laws=[{"law_id": LAW, "quote": quote,
        "applies_to": [ACTOR], "confidence": "low", "relevance_type": "specific_match",
        "notes": "Original crosswalk qualification, access, passage and obstruction context require review."}],
        borderline_excluded=[])
    relevance_ref = write("relevance.json", relevance)
    batch_ref = write("relevance_batch.json", relevance)
    template_ref = write("template.json", {"status": "draft", "law_id": LAW,
        "actor": ACTOR, "template_id": TEMPLATE, "quote": quote,
        "parameter_refs": [{"name": n, "kind": "world_setup",
            "range_or_domain": domain} for n, domain in (
                ("direction", "forward or reverse passage"),
                ("target_half", "direction-relative right or left"),
                ("obstacle_context", "clear or source-observed obstruction"))],
        "structure": {"activation": {"condition": "A person afoot moves on a qualified crosswalk.",
            "numeric_conditions": []},
            "obligation": {"type": "must", "description": quote,
                "numeric_conditions": []},
            "exceptions": [], "timing": {"description": "Observe full crossing and available passage context at 20 Hz.",
                "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": "whenever practicable",
                "note": "No legal numeric practicability cutoff is supplied."}]}})
    judgment_ref = write("judgment-1.json", {"status": "draft",
        "template_id": TEMPLATE, "phrase": "whenever practicable",
        "note": "No legal numeric practicability cutoff is supplied.",
        "observable_requirements": {"observables": [
            {"name": "direction_relative_lateral_position", "unit": "m",
             "description": "Original walker position relative to passage direction and qualified crosswalk."},
            {"name": "available_right_width", "unit": "m",
             "description": "Original obstacle and open-passage geometry over time."}],
            "context_inputs": [{"name": "crosswalk_source", "unit": "source",
                "description": "Map, crosswalk, access, signal, pedestrian and participant source."}],
            "recording_needs": [{"name": "pedestrian_crosswalk_motion", "unit": "m",
                "description": "Original 20 Hz walker motion across a qualified crosswalk."},
                {"name": "right_half_space", "unit": "m",
                "description": "Original obstacle and available passage geometry."},
                {"name": "nearby_participants", "unit": "inventory",
                "description": "Original same-frame participant inventory."}],
            "sweep_dimensions": [], "landmarks": [],
            "limitations": ["Original site and legal practicability interpretation pending."]}})
    bindings_ref = write("bindings.json", dict(common,
        law_refs=[{"template_id": TEMPLATE, "binding_kind": "direct"}],
        context_refs=[],
        established_contexts=["Frozen one-way road/crosswalk cell; original site pending."],
        fixed_parameters=[{"name": "assigned_cell", "value": "C150911",
            "rationale": "Frozen catalog identity, not Native qualification."}],
        variable_parameters=[{"name": n, "kind": "world_setup",
            "range_or_domain": d, "used_by_laws": [LAW]} for n, d in (
                ("direction", "forward or reverse"), ("target_half", "right or left"),
                ("obstacle_context", "clear or obstructed"))]))
    cases = []
    baseline_description = json.loads((ROOT / "cases/forward_right/construction.json").read_text())["recording_description"]
    cases.append({"case_id": ROOT.name + "__baseline", "target_law_id": None,
        "target_type": "baseline", "rationale": "Shared directional crosswalk reference.",
        "variable_assignments": {name: {"kind": "world_setup", "value": value}
            for name, value in (("direction", "forward"), ("target_half", "right"),
                                ("obstacle_context", "clear"))},
        "recording_description": baseline_description,
        "unresolved_judgment_calls": ["whenever practicable"]})
    for case in plan["cases"]:
        short = case["case_id"].split("__")[-1]
        construction = json.loads((ROOT / "cases" / short / "construction.json").read_text())
        recording_description = construction["recording_description"]
        values = {key: case[key] for key in ("direction", "target_half", "obstacle_context")}
        cases.append({"case_id": case["case_id"], "target_law_id": LAW,
            "target_type": "judgment_sweep", "rationale": str(case["recording_description"]),
            "variable_assignments": {key: {"kind": "world_setup", "value": value}
                                     for key, value in values.items()},
            "paired_probe_id": "source-gated-direction-and-obstruction",
            "deliberate_differences": ["direction", "target_half", "obstacle_context"],
            "unresolved_judgment_calls": ["whenever practicable"],
            "recording_description": recording_description,
            "probe": {"primary_variable": "target_half",
                "comparison_or_standard": "same reviewed crosswalk, participants and four-camera policy",
                "target_value_or_branch": values}})
    sweep = {"sweep_id": "source-gated-practicability-context",
        "target_law_id": LAW, "judgment_refs": [{"phrase": "whenever practicable",
            "note": "No legal numeric practicability cutoff is supplied."}], "status": "incomplete",
        "rationale": "Obstruction and direction are physical probes, not a legal cutoff.",
        "missing_inputs": ["reviewed original qualified crosswalk and obstruction geometry",
            "source-bound full pedestrian passage and camera readback",
            "applicable legal practicability assessment"]}
    write("pending-source-judgment-sweep.json", sweep)
    cases_ref = write("cases.json", dict(common, sweep_specs=[sweep],
        sweeps_expanded=True, sweep_expansion_scope="Five selected physical probes; legal judgment unresolved.",
        cases=cases))
    write("semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": ROOT.name, "stages": {"relevance_batch": batch_ref,
            "relevance": relevance_ref, "template": template_ref,
            "judgment_observables": [judgment_ref], "bindings": bindings_ref,
            "cases": cases_ref}})


if __name__ == "__main__":
    build()
    print("source-gated crosswalk semantic proposals authored")
