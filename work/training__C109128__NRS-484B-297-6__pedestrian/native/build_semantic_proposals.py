"""Draft the exact-law canonical stage chain without resolving judgments."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
FOLDER = HERE.parent
REPO = FOLDER.parents[1]
AID = FOLDER.name
LAW = "NRS-484B-297-6"
TEMPLATE = LAW + "@pedestrian"
VARIABLES = ("pedestrian_bypass_path", "sidewalk_travel_direction",
             "intervening_area_passability")
JUDGMENTS = (
    ("obstruction to his or her mobility on the sidewalk", "Original obstruction, pedestrian width and passable sidewalk geometry require review.", "st.obstruction"),
    ("due care", "Original traffic, sight lines, body motion and camera pixels require independent review.", "drv.time_to_conflict"),
    ("immediately adjacent highway", "Original Native lane adjacency and public highway status require independent review.", "st.highway"),
    ("as far to the side of the highway near the sidewalk as possible", "Original road edge, full pedestrian footprint and feasible lateral alternatives require review.", "st.road_edge"),
    ("if the area between the lane and the sidewalk is impassable", "Original intervening surface and obstruction geometry require physical review.", "st.bicycle_lane_or_path"),
    ("as soon as practicable", "Original full-footprint return timing and feasible earlier opportunities require review.", "st.sidewalk"))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n")


def reference(path):
    return {"path": path.name, "sha256": sha(path)}


def main():
    assignment = json.loads((REPO / "inputs" / AID / "assignment.json").read_text())
    law = assignment["law"]["text"]
    proposals = FOLDER / "proposals"
    relevance = {"cell_id": "C109128", "actor": "pedestrian", "status": "draft",
                 "relevant_laws": [{"law_id": LAW,
                                    "quote": "A pedestrian walking or otherwise traveling on a sidewalk who encounters an obstruction to his or her mobility on the sidewalk",
                                    "applies_to": ["pedestrian"],
                                    "relevance_type": "specific_match", "confidence": "high",
                                    "notes": "Exact sidewalk obstruction and adjacent-highway branch; physical and judgment review pending."}],
                 "borderline_excluded": []}
    write(proposals / "relevance.json", relevance)
    write(proposals / "relevance-batch.json", relevance)
    template = {"template_id": TEMPLATE, "law_id": LAW, "actor": "pedestrian",
                "status": "draft", "quote": law,
                "structure": {"activation": {"description": "A pedestrian traveling on the sidewalk encounters an obstruction to mobility.",
                                             "source_clause": "A pedestrian walking or otherwise traveling on a sidewalk who encounters an obstruction to his or her mobility on the sidewalk"},
                              "obligation": {"description": "Observe adjacent-highway bypass, near-side travel, optional travel direction and conditional bicycle-lane use, then full sidewalk return.",
                                             "source_clause": "may proceed with due care on the immediately adjacent highway to move around such an obstruction"},
                              "exceptions": [],
                              "timing": {"description": "Join original approach, road entry, obstruction bypass and first full sidewalk return.",
                                         "source_clause": "Must return to the sidewalk as soon as practicable."},
                              "judgment_calls_needed": [{"phrase": phrase, "note": note}
                                                        for phrase, note, _ in JUDGMENTS]},
                "parameter_refs": [{"name": name, "kind": "world_setup",
                                    "range_or_domain": "authored physical alternative with original source review"}
                                   for name in VARIABLES]}
    write(proposals / "template.json", template)
    judgment_refs = []
    for index, (phrase, note, channel) in enumerate(JUDGMENTS, 1):
        observable = {"template_id": TEMPLATE, "phrase": phrase, "note": note,
                      "status": "draft",
                      "observable_requirements": {
                          "observables": [{"name": channel, "unit": "structured",
                                           "description": "Original source-bound observations for this unresolved phrase."}],
                          "context_inputs": [{"name": "sidewalk_context", "unit": "source",
                                              "description": "Original map and obstruction actor readback."}],
                          "sweep_dimensions": [], "landmarks": [],
                          "recording_needs": [{"name": channel, "unit": "structured",
                                               "description": "Retained original source observations and camera/frame join."}],
                          "limitations": ["Physical feasibility, pixels and legal meaning require independent review."]}}
        path = proposals / f"judgment-{index}.json"
        write(path, observable)
        judgment_refs.append({"path": "proposals/" + path.name, "sha256": sha(path)})
    bindings = {"cell_id": "C109128", "actor": "pedestrian", "status": "draft",
                "established_contexts": [],
                "law_refs": [{"template_id": TEMPLATE, "binding_kind": "direct"}],
                "context_refs": [], "fixed_parameters": [],
                "variable_parameters": [{"name": name, "kind": "world_setup",
                                         "range_or_domain": "authored alternate request and original measurement",
                                         "used_by_laws": [LAW]} for name in VARIABLES]}
    write(proposals / "bindings.json", bindings)
    cases = json.loads((proposals / "cases.json").read_text())
    selected = [item for item in cases["cases"] if item["target_type"] != "baseline"]
    recording = selected[0]["recording_description"]
    baseline = {"case_id": AID + "__baseline", "target_law_id": None,
                "target_type": "baseline", "rationale": "Unselected shared sidewalk context; no recording requested.",
                "variable_assignments": {name: {"kind": "world_setup", "value": None}
                                         for name in VARIABLES},
                "unresolved_judgment_calls": [phrase for phrase, _, _ in JUDGMENTS],
                "recording_description": recording}
    for item in selected:
        suffix = item["case_id"].rsplit("__", 1)[-1]
        variable = item["deliberate_differences"][0]
        values = {"pedestrian_bypass_path": "near_shoulder",
                  "sidewalk_travel_direction": "east",
                  "intervening_area_passability": "passable"}
        values[variable] = suffix
        item["target_type"] = "judgment_sweep"
        item["variable_assignments"] = {name: {"kind": "world_setup", "value": values[name]}
                                        for name in VARIABLES}
        item["unresolved_judgment_calls"] = [phrase for phrase, _, _ in JUDGMENTS]
        item["probe"] = {"primary_variable": variable,
                         "comparison_or_standard": item["paired_probe_id"],
                         "target_value_or_branch": suffix}
    cases["cases"] = [baseline] + selected
    cases["sweep_specs"] = [{"sweep_id": AID + "__unresolved_judgments",
                             "target_law_id": LAW, "status": "incomplete",
                             "judgment_refs": [{"phrase": phrase, "note": note}
                                               for phrase, note, _ in JUDGMENTS],
                             "rationale": "Raw evidence probes are planned; legal judgment ranges and physical review remain open.",
                             "missing_inputs": ["Original Native physical and pixel review"]}]
    cases["sweeps_expanded"] = True
    write(proposals / "cases.json", cases)
    paths = {"relevance_batch": proposals / "relevance-batch.json",
             "relevance": proposals / "relevance.json", "template": proposals / "template.json",
             "judgment_observables": judgment_refs,
             "bindings": proposals / "bindings.json", "cases": proposals / "cases.json"}
    index = {"format": "worker-semantic-delivery", "assignment_id": AID,
             "stages": {key: (value if isinstance(value, list) else
                              {"path": "proposals/" + value.name, "sha256": sha(value)})
                        for key, value in paths.items()}}
    write(proposals / "semantic-index.json", index)
    print(json.dumps({"judgments": len(JUDGMENTS), "selected_cases": len(selected),
                      "index_sha256": sha(proposals / "semantic-index.json")}))


if __name__ == "__main__":
    main()
