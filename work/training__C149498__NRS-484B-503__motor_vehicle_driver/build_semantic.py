"""Source-quoted semantic proposals with unresolved passenger loading judgments."""

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AID = HERE.name
OUT = HERE / "proposals"
assignment = json.loads((REPO / "inputs" / AID / "assignment.json").read_text())
LAW, CELL, ACTOR = (assignment[key] for key in ("law_id", "cell_id", "actor"))
QUOTE = assignment["law"]["text"]
TEMPLATE = LAW + "@" + ACTOR


def write(name, value):
    OUT.mkdir(exist_ok=True)
    path = OUT / (name + ".json")
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    return {"path": str(path.relative_to(HERE)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def reference(name):
    path = OUT / (name + ".json")
    return {"path": str(path.relative_to(HERE)),
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def observable(phrase, note, name, source):
    return {"template_id": TEMPLATE, "phrase": phrase, "note": note,
        "status": "draft", "observable_requirements": {
            "observables": [{"name": name, "unit": "structured",
                "description": "Original 600-frame body, actor, sign and camera source measurements."}],
            "context_inputs": [{"name": source, "unit": "structured",
                "description": "Original Native source readback and independent review context."}],
            "sweep_dimensions": [{"name": name, "unit": "category",
                "description": "Controlled request contrast, never a legal classification."}],
            "landmarks": [],
            "recording_needs": [{"name": name, "unit": "structured",
                "description": "Original synchronized cameras, body history and civil-time evidence."}],
            "limitations": ["Physical realization and statutory judgment remain unassessed; no numeric legal cutoff is invented."]}}


def main():
    relevance = {"actor": ACTOR, "cell_id": CELL, "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": QUOTE, "applies_to": [ACTOR],
            "relevance_type": "direct", "confidence": "high",
            "notes": "Frozen one-way passenger curb loading cell; zone and sign authority require original review."}],
        "borderline_excluded": []}
    refs = {"relevance_batch": write("relevance-batch", relevance),
            "relevance": write("relevance", relevance)}
    judgments = [
        ("place marked as a passenger curb loading zone",
         "Authored curb and sign readback does not establish legal regulatory authority.",
         "st.curb_zone", "loading_zone"),
        ("during hours when the regulations applicable to such passenger curb loading zone are effective",
         "The source sign schedule and civil clock are measured; legal effect requires original source review.",
         "drv.condition_in_effect", "env.civil_time"),
        ("expeditious loading or unloading of passengers",
         "Door commands and a pedestrian near the vehicle do not establish actual exchange or expeditiousness.",
         "ru.pedestrian", "ru.occupant_count")]
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR,
        "quote": QUOTE, "status": "draft",
        "structure": {"activation": {"description": "Stop, stand or park in marked passenger curb zone during effective signed hours",
            "source_clause": "shall not stop, stand or park a vehicle for any purpose or period of time ... in any place marked as a passenger curb loading zone during hours when the regulations ... are effective"},
            "obligation": {"description": "Refrain from stopping, standing or parking except for expeditious passenger loading or unloading",
                "type": "must_not", "source_clause": "shall not stop, stand or park a vehicle for any purpose or period of time except for the expeditious loading or unloading of passengers"},
            "exceptions": [{"description": "Expeditious loading or unloading of passengers",
                            "source_clause": "except for the expeditious loading or unloading of passengers"}],
            "timing": {"description": "Effective zone hours from original sign and measured civil time; no statutory minimum stop duration"},
            "judgment_calls_needed": [{"phrase": phrase, "note": note}
                                      for phrase, note, _, _ in judgments]},
        "parameter_refs": [{"name": "actual_passenger_loading", "kind": "controller",
                            "range_or_domain": ["requested", "not_requested"]},
                           {"name": "signed_effective_hours", "kind": "world_setup",
                            "range_or_domain": ["inside", "outside"]},
                           {"name": "action_and_measured_duration", "kind": "controller",
                            "range_or_domain": ["brief_stop", "standing_episode", "extended_park"]}]}
    refs["template"] = write("template", template)
    refs["judgment_observables"] = [write("judgment_observables_" + str(i),
        observable(phrase, note, name, source)) for i, (phrase, note, name, source) in
        enumerate(judgments, 1)]
    binding = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
        "established_contexts": [{"name": "passenger_curb_loading_request",
            "source": "frozen one-way loading-zone cell and authored curb/sign readback request"}],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{"name": name, "kind": kind,
            "range_or_domain": domain, "used_by_laws": [LAW]} for name, kind, domain in
            (("actual_passenger_loading", "controller", ["requested", "not_requested"]),
             ("signed_effective_hours", "world_setup", ["inside", "outside"]),
             ("action_and_measured_duration", "controller", ["brief_stop", "standing_episode", "extended_park"]))]}
    refs["bindings"] = write("bindings", binding)
    refs["cases"] = reference("cases")
    index = {"assignment_id": AID, "format": "worker-semantic-delivery", "stages": refs}
    path = OUT / "semantic-index.json"
    path.write_text(json.dumps(index, indent=2, allow_nan=False) + "\n")
    return {"index_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "selected_cases": 6, "judgment_observables": len(judgments)}


if __name__ == "__main__":
    print(json.dumps(main(), sort_keys=True))
