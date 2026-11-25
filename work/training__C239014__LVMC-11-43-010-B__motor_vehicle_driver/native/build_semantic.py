"""Source-based canonical stage proposals for the frozen roundabout law."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
ASSIGNMENT = FOLDER.name
LAW = "LVMC-11-43-010-B"
TEMPLATE = LAW + "@motor_vehicle_driver"
QUOTE = ("The following regulations pertain to the operation of vehicles within a "
         "roundabout: The operator of a vehicle entering a roundabout shall yield "
         "the right-of-way to vehicles already in the roundabout and wait for a "
         "gap in traffic before entering.")


def write(name, value):
    path = FOLDER / "proposals" / name
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def reference(path):
    return {"path": str(path.relative_to(FOLDER)), "sha256": sha(path)}


def build():
    relevance = {"cell_id": "C239014", "actor": "motor_vehicle_driver",
        "status": "draft", "relevant_laws": [{"law_id": LAW, "quote": QUOTE,
            "applies_to": ["motor_vehicle_driver"], "relevance_type": "specific_match",
            "confidence": "high", "notes": "Frozen roundabout-entry cell with another vehicle; "
            "original occupancy and boundary require review."}], "borderline_excluded": []}
    rel = write("relevance.json", relevance)
    rel_batch = write("relevance_batch.json", relevance)
    judgments = [
        {"phrase": "vehicles already in the roundabout",
         "note": "Original map, actor identity and occupancy timing must establish precedence.",
         "observables": ["roundabout_map", "raw_circulating_motion", "frame_join"]},
        {"phrase": "gap in traffic",
         "note": "Source frames bracket the entry; no statutory sufficient-gap cutoff is declared.",
         "observables": ["raw_ego_motion", "raw_circulating_motion", "frame_join"]}]
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": "motor_vehicle_driver",
        "status": "draft", "quote": QUOTE, "structure": {
            "activation": {"condition": "An operator is entering a roundabout while vehicles are already within it.",
                           "numeric_conditions": []},
            "obligation": {"type": "must", "description": "Yield right-of-way to vehicles already in the roundabout and wait for a gap in traffic before entering.",
                           "numeric_conditions": []},
            "exceptions": [], "timing": {"description": "Yield and wait before the entering vehicle crosses the roundabout boundary.",
                                         "numeric_conditions": []},
            "judgment_calls_needed": [{"phrase": item["phrase"], "note": item["note"]}
                                      for item in judgments]}, "parameter_refs": []}
    template_ref = reference(write("template.json", template))
    judgment_refs = []
    for index, item in enumerate(judgments, 1):
        requirements = {"observables": [{"name": name, "unit": "source_record" if name == "roundabout_map" else "structured",
              "description": item["note"]} for name in item["observables"]],
            "context_inputs": [], "sweep_dimensions": [], "landmarks": [],
            "recording_needs": [{"name": name, "unit": "source_record" if name == "roundabout_map" else "structured",
              "description": item["note"]} for name in item["observables"]],
            "limitations": ["Original physical geometry and legal gap sufficiency need independent review."]}
        judgment_refs.append(reference(write("judgment-" + str(index) + ".json", {
            "template_id": TEMPLATE, "phrase": item["phrase"], "note": item["note"],
            "status": "draft", "observable_requirements": requirements})))
    binding = {"cell_id": "C239014", "actor": "motor_vehicle_driver",
        "status": "draft", "established_contexts": [{"name": "roundabout_entry_with_other_vehicle",
            "source": "frozen C239014 catalog cell; actual occupancy and geometry unverified"}],
        "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
        "context_refs": [], "fixed_parameters": [],
        "variable_parameters": [{"name": "entry_release_time", "kind": "controller",
            "range_or_domain": "12.5 or 17.0 seconds, engineering request only",
            "used_by_laws": [LAW]}]}
    binding_ref = reference(write("bindings.json", binding))
    selected = json.loads((FOLDER / "proposals/cases.json").read_text())
    baseline = {"case_id": ASSIGNMENT + "__baseline", "target_law_id": LAW,
        "target_type": "baseline", "rationale": "Canonical nonselected comparison anchor",
        "probe": {"primary_variable": "entry_release_time",
                  "comparison_or_standard": "source-observed entry chronology",
                  "target_value_or_branch": "baseline"},
        "variable_assignments": {"entry_release_time": {"kind": "controller", "value": 17.0}},
        "recording_description": selected["cases"][0]["recording_description"],
        "unresolved_judgment_calls": ["original roundabout boundary and gap sufficiency"]}
    selected["cases"].insert(0, baseline)
    selected["sweep_specs"] = [{"sweep_id": "c239014_gap_judgment",
        "target_law_id": LAW, "status": "incomplete",
        "judgment_refs": [{"phrase": item["phrase"], "note": item["note"]}
                          for item in judgments],
        "rationale": "Original traffic occupancy and an authoritative sufficient-gap standard are not established by a CPU fixture.",
        "missing_inputs": ["original Native roundabout entry and circulating actor readback",
                           "independent legal review of sufficient gap"]}]
    cases_ref = reference(write("canonical-cases.json", selected))
    index = {"format": "worker-semantic-delivery", "assignment_id": ASSIGNMENT,
        "stages": {"relevance_batch": reference(rel_batch), "relevance": reference(rel),
                   "template": template_ref, "judgment_observables": judgment_refs,
                   "bindings": binding_ref, "cases": cases_ref}}
    path = write("semantic-index.json", index)
    return {"semantic_index_sha256": sha(path), "judgments": len(judgments)}


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
