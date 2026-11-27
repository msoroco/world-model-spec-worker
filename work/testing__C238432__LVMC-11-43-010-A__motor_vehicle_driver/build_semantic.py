"""Author exact counterclockwise circulation semantic stage proposals."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from direction import ASSIGNMENT, CASE_DIRECTIONS

HERE=Path(__file__).resolve().parent
OUT=HERE/"proposals"
LAW="LVMC-11-43-010-A"
CELL="C238432"
ACTOR="motor_vehicle_driver"
QUOTE=("The following regulations pertain to the operation of vehicles within a "
       "roundabout: All vehicular travel shall be in a counterclockwise direction.")
TEMPLATE=LAW+"@"+ACTOR
PHRASE="within a roundabout"
NOTE="Establish the original central island, circulatory roadway, entry geometry and Las Vegas jurisdiction."


def write(name,value):
    path=OUT/name
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,indent=2,allow_nan=False)+"\n")
    return {"path":str(path.relative_to(HERE)),
            "sha256":hashlib.sha256(path.read_bytes()).hexdigest()}


def build():
    manifest=json.loads((HERE/"execution-manifest.json").read_text())
    relevance={"cell_id":CELL,"actor":ACTOR,"status":"draft",
        "relevant_laws":[{"law_id":LAW,"quote":QUOTE,"applies_to":[ACTOR],
            "relevance_type":"vehicular circulation within a roundabout",
            "confidence":"medium","notes":"Actual roundabout and direction require source review."}],
        "borderline_excluded":[]}
    rbatch=write("relevance_batch.json",relevance)
    rref=write("relevance.json",relevance)
    template={"template_id":TEMPLATE,"law_id":LAW,"actor":ACTOR,"quote":QUOTE,
        "structure":{"law_id":LAW,
            "activation":{"condition":"A motor vehicle travels within an actual roundabout.",
                          "numeric_conditions":[]},
            "obligation":{"description":"All vehicular travel proceeds counterclockwise.",
                          "type":"must","numeric_conditions":[]},
            "exceptions":[],
            "timing":{"description":"Observe actual circulation while the vehicle occupies the roundabout.",
                      "numeric_conditions":[]},
            "judgment_calls_needed":[{"phrase":PHRASE,"note":NOTE}]},
        "parameter_refs":[{"name":"circulation_direction","kind":"world_setup",
                           "range_or_domain":"counterclockwise or clockwise original ring travel"}]}
    tref=write("template.json",template)
    judgment={"template_id":TEMPLATE,"phrase":PHRASE,"note":NOTE,"status":"draft",
        "observable_requirements":{"observables":[{"name":"original_ring_trajectory",
            "unit":"structured","description":"Source-bound 20 Hz actor XY and ring section history."}],
            "context_inputs":[{"name":"reviewed_roundabout_map","unit":"source",
                "description":"Original map geometry, island, roadway and jurisdiction."}],
            "sweep_dimensions":[],"landmarks":[],
            "recording_needs":[{"name":"original_four_camera_pixels","unit":"frame",
                "description":"Four synchronized original camera views through the ring."}],
            "limitations":["Map topology and physical circulation remain for original Native and local review."]}}
    jref=write("judgment-1.json",judgment)
    binding={"cell_id":CELL,"actor":ACTOR,"status":"draft",
        "established_contexts":["Frozen roundabout/circulate/traffic-island cell; actual site requires original source review."],
        "law_refs":[{"template_id":TEMPLATE,"binding_kind":"direct"}],
        "context_refs":[],
        "fixed_parameters":[{"name":"reviewed_roundabout_site","value":"source_packet_pending",
            "rationale":"Hold one source map, island, entry lane and four-view plan across both cases."}],
        "variable_parameters":[{"name":"circulation_direction","kind":"world_setup",
            "range_or_domain":"counterclockwise or clockwise original ring travel",
            "used_by_laws":[LAW]}]}
    bref=write("bindings.json",binding)
    desc=json.loads((HERE/"construction.json").read_text())["recording_description"]
    cases=[{"case_id":ASSIGNMENT+"__baseline","paired_probe_id":"baseline",
        "rationale":"Shared source-reviewed ring and operator reference for direction comparison.",
        "recording_description":desc,"target_law_id":LAW,"target_type":"baseline",
        "unresolved_judgment_calls":[PHRASE],
        "variable_assignments":{"circulation_direction":{"kind":"world_setup",
                                                     "value":"counterclockwise"}},
        "deliberate_differences":["circulation_direction"],
        "probe":{"primary_variable":"circulation_direction",
                 "comparison_or_standard":"source-bound opposite signed ring arcs",
                 "target_value_or_branch":"counterclockwise"}}]
    for name in ("counterclockwise","clockwise"):
        case=ASSIGNMENT+"__"+name
        cases.append({"case_id":case,"paired_probe_id":"roundabout_circulation_direction",
            "rationale":"Measure original signed travel around one surveyed central island without inferring a legal verdict.",
            "recording_description":desc,"target_law_id":LAW,"target_type":"boundary_probe",
            "unresolved_judgment_calls":[PHRASE],
            "variable_assignments":{"circulation_direction":{"kind":"world_setup","value":name}},
            "deliberate_differences":["circulation_direction"],
            "probe":{"primary_variable":"circulation_direction",
                     "comparison_or_standard":"source-bound opposite signed ring arcs",
                     "target_value_or_branch":name}})
    proposed={"cell_id":CELL,"actor":ACTOR,"status":"draft","cases":cases,
        "sweep_specs":[{"sweep_id":"roundabout_source_review","target_law_id":LAW,
            "judgment_refs":[{"phrase":PHRASE,"note":NOTE}],"status":"incomplete",
            "rationale":"Physical roundabout geometry and local application require original source review, not a numeric worker cutoff.",
            "missing_inputs":["Original Native map readback and local review of roundabout context."]}],
        "sweeps_expanded":True}
    cref=write("cases.json",proposed)
    index={"format":"worker-semantic-delivery","assignment_id":ASSIGNMENT,
        "source":"Exact LVMC 11.43.010(A) and frozen C238432 cell","status":"draft",
        "stages":{"relevance_batch":rbatch,"relevance":rref,"template":tref,
                  "judgment_observables":[jref],"bindings":bref,"cases":cref}}
    write("semantic-index.json",index)
    return len(cases)-1


if __name__=="__main__":
    print(build())
