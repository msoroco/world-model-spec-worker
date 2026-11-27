"""Build source-quoted draft semantic stages for the exact red-X pair."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
LAW = "NRS-484B-307-12b"
ACTOR = "motor_vehicle_driver"
CELL = "C230247"
TEMPLATE = LAW + "@" + ACTOR


def write(name, value):
    path = ROOT / "proposals" / name
    path.write_text(json.dumps(value, indent=2) + "\n")
    return {"path": "proposals/" + name,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    original = json.loads((REPO / "inputs" / ROOT.name / "assignment.json").read_text())
    quote = original["law"]["text"]
    relevance = {"cell_id": CELL, "actor": ACTOR, "status": "draft",
        "relevant_laws": [{"law_id": LAW, "quote": quote, "applies_to": [ACTOR],
            "relevance_type": "specific_match", "confidence": "high",
            "notes": "Individual highway lane signal and facing driver are source-bound observations."}],
        "borderline_excluded": []}
    references = {"relevance_batch": write("relevance_batch.json", relevance),
                  "relevance": write("relevance.json", relevance)}
    parameters = [{"name": "red_x_lane_occupancy", "kind": "world_setup",
                   "range_or_domain": "outside or enter the red-X-governed lane"},
                  {"name": "rel.occupies", "kind": "subject_behavior",
                   "range_or_domain": "original actor body and waypoint lane identity"}]
    references["template"] = write("template.json", {
        "template_id": TEMPLATE, "law_id": LAW, "actor": ACTOR, "status": "draft",
        "quote": quote, "structure": {
            "activation": {"description": "Signals placed over individual highway lanes; driver faces a red X symbol",
                           "source_clause": "Whenever signals are placed over the individual lanes of a highway"},
            "obligation": {"description": "Facing driver must not enter or drive in the lane over which the red X is shown",
                           "source_clause": "must not enter or drive in any lane over which the red signal is shown"},
            "exceptions": [],
            "timing": {"description": "Original signal state and lane occupancy throughout the proposed travel window",
                       "source_clause": "A red “X” symbol means"},
            "judgment_calls_needed": [{"phrase": "facing the signal",
                "note": "Actual original device pixels and driver-facing geometry require independent review."}]},
        "parameter_refs": parameters})
    references["judgment_observables"] = [write("judgment_observables_0.json", {
        "template_id": TEMPLATE, "phrase": "facing the signal",
        "note": "Actual original device pixels and driver-facing geometry require independent review.",
        "status": "draft", "observable_requirements": {
            "observables": [{"name": "signal_facing_driver", "unit": "structured",
                "description": "Original signal position, indication and actor travel direction"}],
            "context_inputs": [],
            "sweep_dimensions": [{"name": "rel.occupies", "unit": "lane overlap",
                "description": "Measured original actor body and waypoint lane identity"}],
            "landmarks": [],
            "recording_needs": [{"name": "dev.lane_control_signal", "unit": "structured",
                "description": "Original signal state joined to four synchronized camera pixels"}],
            "limitations": ["Synthetic fixtures cannot establish actual pixels or official device authority."]}})]
    references["bindings"] = write("bindings.json", {
        "cell_id": CELL, "actor": ACTOR, "status": "draft",
        "established_contexts": [{"name": "individual_lane_control_red_x_candidate",
            "source": "Frozen assignment; official device and original pixels require local review"}],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{**row, "used_by_laws": [LAW]} for row in parameters]})
    cases = json.loads((ROOT / "proposals" / "cases.json").read_text())
    cases["cases"] = [item for item in cases["cases"] if item["case_id"].endswith(("__probe_1", "__probe_2"))]
    for item in cases["cases"]:
        item["target_type"] = "boundary_probe"
        item["probe"] = {"primary_variable": "red_x_lane_occupancy",
                         "comparison_or_standard": "entry into the lane governed by the red X",
                         "target_value_or_branch": item["variable_assignments"]["red_x_lane_occupancy"]["value"]}
        item["variable_assignments"]["red_x_lane_occupancy"]["kind"] = "world_setup"
        if item.get("target_type") != "baseline":
            tag = item["case_id"].rsplit("_", 1)[-1]
            source = ROOT / "construction.json" if tag == "1" else ROOT / "cases/probe_2/construction.json"
            item["recording_description"] = json.loads(source.read_text())["recording_description"]
        item["unresolved_judgment_calls"] = ["facing the signal"]
        item["variable_assignments"].pop("observed_occupied_lane_id", None)
        item["variable_assignments"]["rel.occupies"] = {
            "kind": "subject_behavior", "unit": "lane overlap", "value": None}
    cases["cases"].sort(key=lambda item: item["variable_assignments"]["red_x_lane_occupancy"]["value"])
    selected = [item for item in cases["cases"] if item["target_type"] != "baseline"]
    sweep_id = ROOT.name + "__selected_378a10ff__comparison"
    spec = {"sweep_id": sweep_id, "target_law_id": LAW,
        "judgment_refs": [{"phrase": "facing the signal",
            "note": "Actual original device pixels and driver-facing geometry require independent review."}],
        "rationale": "Vary measured entry into the red-X-governed lane while holding the signal, road, actor, and cameras fixed.",
        "status": "complete", "mode": "one_dimensional",
        "axes": [{"variable": "red_x_lane_occupancy", "observable": "rel.occupies",
            "unit": "lane overlap", "min": 0, "max": 1, "spacing": 1,
            "range_rationale": "Two planned occupancy outcomes: remaining outside or entering the governed lane.",
            "spacing_rationale": "The binary entry event distinguishes the two exact cases.",
            "feasibility_evidence": "Both exact offline constructions and source-bound diagnostic finalization pass.",
            "measurement": {"method": "original actor body and lane map",
                "time_window": "600 original frames", "statistic": "max"}}],
        "landmarks": [], "variable_assignments": selected[0]["variable_assignments"],
        "recording_description": selected[0]["recording_description"],
        "planned_case_count": len(selected),
        "selection_order": [item["case_id"] for item in selected]}
    version_source = {key: value for key, value in spec.items()
                      if key not in ("planned_case_count", "selection_order")}
    spec["spec_version"] = hashlib.sha256(json.dumps(version_source,
        sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
    cases["status"] = "draft"
    cases["sweep_specs"] = [spec]
    cases["sweeps_expanded"] = True
    for item in selected:
        item["sweep_id"] = sweep_id
        item["sweep_point"] = {"red_x_lane_occupancy": item["variable_assignments"]["red_x_lane_occupancy"]["value"]}
        item["sweep_spec_version"] = spec["spec_version"]
        item["sweep_measurements"] = [{"variable": "red_x_lane_occupancy",
            "observable": "rel.occupies", "unit": "lane overlap",
            "measurement": {"method": "original actor body and lane map",
                "time_window": "600 original frames", "statistic": "max"}}]
    if not any(case.get("target_type") == "baseline" for case in cases["cases"]):
        baseline = dict(cases["cases"][0])
        baseline.update({"case_id": ROOT.name + "__baseline", "target_law_id": None,
                         "target_type": "baseline", "rationale": "Shared lane signal and roadway context without a legal verdict"})
        for key in ("paired_probe_id", "deliberate_differences", "probe"):
            baseline.pop(key, None)
        cases["cases"].insert(0, baseline)
    references["cases"] = write("cases.json", cases)
    return write("semantic-index.json", {
        "format": "worker-semantic-delivery", "assignment_id": ROOT.name,
        "stages": references})


if __name__ == "__main__":
    print(json.dumps(build(), sort_keys=True))
