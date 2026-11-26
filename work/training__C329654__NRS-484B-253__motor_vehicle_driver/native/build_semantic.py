"""Author draft canonical semantic stages for the exact two-case turn probe."""
import hashlib
import json
from pathlib import Path

from build_draft import RECORDING_DESCRIPTION


HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = FOLDER.parents[1]
ASSIGNMENT = FOLDER.name
LAW = "NRS-484B-253"
CELL = "C329654"
ACTOR = "motor_vehicle_driver"
TEMPLATE = LAW + "@" + ACTOR
PAIR = ASSIGNMENT + "__selected_d457f261__comparison"
CASES = [ASSIGNMENT + "__selected_d457f261__condition_" + s for s in ("a", "b")]
NOTES = {
    "immediate hazard": "Opposing distance, speed and occupancy are measured; legal closeness remains unresolved.",
    "having so yielded": "Original wait, signal, turn and later opposing response are measured without a priority verdict."}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(name, value):
    path = FOLDER / "proposals" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    return {"path": str(path.relative_to(FOLDER)), "sha256": sha(path)}


def judgment(phrase, needs):
    return {"template_id": TEMPLATE, "phrase": phrase, "note": NOTES[phrase],
        "status": "draft", "observable_requirements": {
            "observables": [{"name": name, "unit": unit,
                "description": "Original timestamp-joined participant and map observation"}
                for name, unit in needs],
            "context_inputs": [{"name": "intersection_context", "unit": "structured",
                "description": "Original intersection polygon and opposite-lane survey"}],
            "sweep_dimensions": [{"name": "turn_release_s", "unit": "s",
                "description": "Observed first nonzero left-turn progress time; authored release is separate"}],
            "landmarks": [],
            "recording_needs": [{"name": name, "unit": unit,
                "description": "Full original actor sequence before and after turn"}
                for name, unit in needs] + [{"name": "turn_release_s", "unit": "s",
                    "description": "Full observed turn-onset history"}],
            "limitations": ["Distance and passage order are not a legal immediate-hazard threshold.",
                "Signal adequacy, yielding and physical completion require independent review."]}}


def case(case_id, release, rank):
    assignments = {"turn_release_s": {"kind": "controller", "unit": "s",
            "value": release},
        "opposing_stream_context": {"kind": "world_setup", "unit": "categorical",
            "value": "same two-way intersection, initial and subsequent opposing actors"}}
    return {"case_id": case_id, "target_law_id": LAW,
        "target_type": "judgment_sweep",
        "rationale": "Compare requested turn release against an initially approaching and later opposing stream; original passage, signal and response remain observations.",
        "paired_probe_id": PAIR, "deliberate_differences": ["turn_release_s"],
        "probe": {"primary_variable": "turn_release_s",
            "comparison_or_standard": "measured initial passage, signal and later opposing response; no legal verdict",
            "target_value_or_branch": release},
        "variable_assignments": assignments,
        "unresolved_judgment_calls": sorted(NOTES),
        "recording_description": RECORDING_DESCRIPTION,
        "sweep_id": PAIR, "sweep_point": {"turn_release_s": release},
        "selection_rank": rank,
        "sweep_measurements": [{"variable": "turn_release_s",
            "observable": "turn_release_s", "unit": "s",
            "measurement": {"method": "first observed nonzero left-turn progress from saved actor frames",
                "time_window": "600 original frames", "statistic": "max"}}]}


def build():
    assignment = json.loads((REPO / "inputs" / ASSIGNMENT / "assignment.json").read_text())
    law_text = assignment["law"]["text"]
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": law_text,
            "applies_to": [ACTOR], "relevance_type": "specific_match",
            "confidence": "high",
            "notes": "The selected cell calls for a motor-vehicle left turn at a two-way intersection."}],
        "borderline_excluded": []}
    refs = {"relevance_batch": write("relevance_batch.json", relevance),
            "relevance": write("relevance.json", relevance)}
    refs["template"] = write("template.json", {
        "template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR,
        "status": "draft", "quote": law_text,
        "structure": {"activation": {"description": "Driver within an intersection intending a left turn",
            "source_clause": "within an intersection intending to turn to the left"},
            "obligation": {"description": "Yield to opposite-direction immediate hazard, then may turn after yielding and required signal; later opposing drivers yield",
                "source_clause": "shall yield the right-of-way to any vehicle approaching from the opposite direction"},
            "exceptions": [],
            "timing": {"description": "Original opposing approach, ego wait/commit and later response sequence",
                "source_clause": "having so yielded and having given a signal when and as required"},
            "judgment_calls_needed": [{"phrase": phrase, "note": NOTES[phrase]}
                for phrase in sorted(NOTES)]},
        "parameter_refs": [{"name": "turn_release_s", "kind": "controller",
            "range_or_domain": "authored request in seconds, actual onset measured separately"},
            {"name": "opposing_stream_context", "kind": "world_setup",
             "range_or_domain": "fixed two-way intersection and two opposing actors"}]})
    refs["judgment_observables"] = [write("judgment_observables_" + str(i) + ".json",
        judgment(phrase, needs)) for i, (phrase, needs) in enumerate((
            ("having so yielded", [("drv.yields_to", "structured"),
                ("sig.turn_indicator", "structured"),
                ("drv.arrival_order", "structured")]),
            ("immediate hazard", [("rel.oncoming", "structured"),
                ("drv.approaching", "structured"),
                ("drv.time_to_conflict", "structured")])))]
    refs["bindings"] = write("bindings.json", {
        "cell_id": CELL, "actor": ACTOR, "status": "draft",
        "established_contexts": [{"name": "two_way_left_turn_candidate",
            "source": "Frozen catalog cell; original Native map and actor source review pending"}],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{"name": "turn_release_s", "kind": "controller",
            "range_or_domain": "requested seconds", "used_by_laws": [LAW]},
            {"name": "opposing_stream_context", "kind": "world_setup",
             "range_or_domain": "fixed two-way intersection and two opposing actors",
             "used_by_laws": [LAW]}]})
    spec = {"sweep_id": PAIR, "target_law_id": LAW,
        "judgment_refs": [{"phrase": phrase, "note": NOTES[phrase]}
            for phrase in sorted(NOTES)],
        "rationale": "Sample two requested release times across initial-hazard passage while retaining the later opposing vehicle and signal phase.",
        "status": "complete", "mode": "one_dimensional",
        "axes": [{"variable": "turn_release_s", "observable": "turn_release_s",
            "unit": "s", "min": 9.0, "max": 15.0, "spacing": 6.0,
            "range_rationale": "Two contrasting requested releases around the fixed initial passage; no legal time threshold.",
            "spacing_rationale": "180 and 300 frame requests at 20 Hz.",
            "feasibility_evidence": "Exact CPU offline bundles and synthetic saved-source comparison.",
            "measurement": {"method": "first observed nonzero left-turn progress from saved actor frames",
                "time_window": "600 original frames", "statistic": "max"}}],
        "landmarks": [], "variable_assignments": case(CASES[1], 9.0, 0)["variable_assignments"],
        "recording_description": RECORDING_DESCRIPTION,
        "planned_case_count": 2, "selection_order": [CASES[1], CASES[0]]}
    original_spec = {key: value for key, value in spec.items()
                     if key not in ("planned_case_count", "selection_order")}
    spec["spec_version"] = hashlib.sha256(json.dumps(original_spec,
        sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    selected_b = case(CASES[1], 9.0, 0)
    selected_a = case(CASES[0], 15.0, 1)
    selected_b["sweep_spec_version"] = spec["spec_version"]
    selected_a["sweep_spec_version"] = spec["spec_version"]
    baseline = {"case_id": ASSIGNMENT + "__baseline",
        "target_law_id": None, "target_type": "baseline",
        "rationale": "Shared source geometry and opposing-stream context without a priority judgment.",
        "variable_assignments": case(CASES[1], 9.0, 0)["variable_assignments"],
        "unresolved_judgment_calls": sorted(NOTES),
        "recording_description": RECORDING_DESCRIPTION}
    refs["cases"] = write("cases.json", {"cell_id": CELL, "actor": ACTOR,
        "status": "draft", "sweep_specs": [spec], "sweeps_expanded": True,
        "cases": [baseline, selected_b, selected_a]})
    return write("semantic-index.json", {"format": "worker-semantic-delivery",
        "assignment_id": ASSIGNMENT, "stages": refs})


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
