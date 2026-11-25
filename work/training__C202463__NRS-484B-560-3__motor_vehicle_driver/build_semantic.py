"""Draft canonical rail-stop semantics from the exact supplied statutory clause."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
LAW = "NRS-484B-560-3"
TEMPLATE = LAW + "@motor_vehicle_driver"
QUOTE = ("When stopping is required at a railroad crossing the driver shall keep as far "
    "to the right of the highway as possible and shall not form two lanes of traffic "
    "unless the highway is marked for four or more lanes of traffic.")


def write(name, value):
    path = HERE / "proposals" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + "\n")
    return {"path": str(path.relative_to(HERE)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    relevance = {"cell_id": "C202463", "actor": "motor_vehicle_driver",
        "status": "draft", "relevant_laws": [{"law_id": LAW, "quote": QUOTE,
            "applies_to": ["motor_vehicle_driver"], "relevance_type": "specific_match",
            "confidence": "medium", "notes": "Frozen rail crossing and gate cell; required-stop authority and rightmost possible judgment require original source review."}],
        "borderline_excluded": []}
    rel = write("relevance.json", relevance)
    rel_batch = write("relevance_batch.json", relevance)
    judgments = [{"phrase": "stopping is required at a railroad crossing",
                  "note": "independent original authority, gate and crossing source needed"},
                 {"phrase": "as far to the right of the highway as possible",
                  "note": "review available right-side space and surrounding traffic"}]
    template = {"template_id": TEMPLATE, "law_id": LAW,
        "actor": "motor_vehicle_driver", "status": "draft", "quote": QUOTE,
        "structure": {"activation": {"condition": "A stop is required at a railroad crossing.",
            "numeric_conditions": []},
            "obligation": {"type": "must", "description": "Keep as far right as possible; do not form two traffic lanes unless the highway has at least four marked lanes.",
                "numeric_conditions": [{"variable": "marked_lane_count", "operator": ">=",
                    "value": 4, "unit": "lanes"}]},
            "exceptions": [{"trigger": "highway marked for four or more lanes",
                "effect": "qualifies only the two-lanes prohibition; far-right duty remains",
                "replacement_obligation": "keep as far right as possible",
                "source_clause": "unless the highway is marked for four or more lanes of traffic"}],
            "timing": {"description": "During the required railroad-crossing stop.",
                       "numeric_conditions": []},
            "judgment_calls_needed": judgments}, "parameter_refs": []}
    template_ref = write("template.json", template)
    observable_refs = []
    for index, (judgment, name) in enumerate(zip(judgments,
            ("st.railway_crossing", "st.road_edge"))):
        observable_refs.append(write(f"judgment-{index}.json", {
            "template_id": TEMPLATE, "phrase": judgment["phrase"],
            "note": judgment["note"], "status": "draft",
            "observable_requirements": {"observables": [{"name": name, "unit": "structured",
                "description": "Original Native frame joined to reviewed road and authority source"}],
                "context_inputs": [], "sweep_dimensions": [], "landmarks": [],
                "recording_needs": [{"name": name, "unit": "structured",
                    "description": "Source recording needed for independent judgment"}],
                "limitations": ["Synthetic gate state cannot establish legal stop authority or rightmost possibility."]}}))
    binding = {"cell_id": "C202463", "actor": "motor_vehicle_driver",
        "status": "draft", "established_contexts": [{"name": "rail_gate_crossing",
            "source": "frozen cell; original gate, crossing and stop authority review pending"}],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{"name": "queue_mode", "kind": "controller",
            "range_or_domain": "right or left, single or abreast stop queue",
            "used_by_laws": [LAW]},
            {"name": "marked_lane_count", "kind": "world_setup",
             "range_or_domain": "two, four or five reviewed marked highway lanes",
             "used_by_laws": [LAW]}]}
    binding_ref = write("bindings.json", binding)
    selected = json.loads((HERE / "proposals/cases.json").read_text())
    selected["sweep_specs"] = [{"sweep_id": f"c202463-original-review-{i}",
        "target_law_id": LAW, "judgment_refs": [judgment],
        "status": "incomplete", "mode": "one_dimensional", "axes": [],
        "rationale": "Original stop authority or available-right source is required before freezing this judgment sweep.",
        "missing_inputs": ["Original Native source bytes and independent reviewer identity"]}
        for i, judgment in enumerate(judgments)]
    selected["cases"].insert(0, {"case_id": ASSIGNMENT + "__baseline",
        "target_law_id": LAW, "target_type": "baseline",
        "rationale": "Neutral nonselected rail-stop comparison anchor",
        "probe": {"primary_variable": "queue_mode",
            "comparison_or_standard": "rightward single queue at required rail stop",
            "target_value_or_branch": "baseline"},
        "variable_assignments": {"queue_mode": {"kind": "controller", "value": "right_single"},
            "marked_lane_count": {"kind": "world_setup", "value": 2}},
        "recording_description": selected["cases"][0]["recording_description"],
        "unresolved_judgment_calls": ["original required-stop authority"]})
    cases_ref = write("canonical-cases.json", selected)
    return write("semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": ASSIGNMENT,
        "stages": {"relevance_batch": rel_batch, "relevance": rel,
            "template": template_ref, "judgment_observables": observable_refs,
            "bindings": binding_ref, "cases": cases_ref}})


if __name__ == "__main__":
    print(json.dumps(build()))
