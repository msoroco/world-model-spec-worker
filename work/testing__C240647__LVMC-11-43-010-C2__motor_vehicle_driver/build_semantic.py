"""Author canonical exact C240647 semantic stage proposals."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
OUT=HERE/"proposals"
AID=HERE.name
LAW="LVMC-11-43-010-C2"
CELL="C240647"
ACTOR="motor_vehicle_driver"
QUOTE=("The following regulations pertain to the operation of vehicles within a roundabout: "
       "The operator of a vehicle who intends to exit a roundabout: Shall use the right lane to turn right.")
TEMPLATE=LAW+"@"+ACTOR
JUDGMENTS=[("right lane","The source map must identify the allocated right circulating lane; original actor use is measured."),
           ("turn right","The independently intended exit and first observed source connector remain distinct.")]

def write(name,value):
    path=OUT/name
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,sort_keys=True,indent=2)+"\n")
    return {"path":str(path.relative_to(HERE)),"sha256":hashlib.sha256(path.read_bytes()).hexdigest()}

def build():
    manifest=json.loads((HERE/"execution-manifest.json").read_text())
    plan=json.loads((HERE/"case-plan.json").read_text())
    relevance={"cell_id":CELL,"actor":ACTOR,"status":"draft",
               "relevant_laws":[{"law_id":LAW,"quote":QUOTE,"applies_to":[ACTOR],
                 "relevance_type":"independent right-exit intent, allocated circular lane and actual connector",
                 "confidence":"medium","notes":"Physical lane and connector readback and legal review remain separate."}],
               "borderline_excluded":[]}
    batch=write("relevance_batch.json",relevance)
    rel=write("relevance.json",relevance)
    template={"template_id":TEMPLATE,"law_id":LAW,"actor":ACTOR,"quote":QUOTE,
              "structure":{"law_id":LAW,"activation":{"condition":"Operator intends to exit a roundabout to turn right.","numeric_conditions":[]},
                           "obligation":{"description":"Use the right lane to turn right.","type":"must","numeric_conditions":[]},
                           "exceptions":[],"timing":{"description":"Measure circulating lane through the connected right-turn exit.","numeric_conditions":[]},
                           "judgment_calls_needed":[{"phrase":phrase,"note":note} for phrase,note in JUDGMENTS]},
              "parameter_refs":[{"name":"operator_intent_request","kind":"participant_behavior","range_or_domain":"independent right or through exit request"},
                                {"name":"roundabout_lane_request","kind":"world_setup","range_or_domain":"source-mapped right, left or lane transition"},
                                {"name":"actual_exit_request","kind":"participant_behavior","range_or_domain":"source-mapped right, through or no exit"}]}
    temp=write("template.json",template)
    jobs=[]
    for index,(phrase,note) in enumerate(JUDGMENTS,1):
        channel="original_ring_lane_history" if phrase=="right lane" else "actual_exit_connector"
        value={"template_id":TEMPLATE,"phrase":phrase,"note":note,"status":"draft",
               "observable_requirements":{"observables":[{"name":channel,"unit":"structured",
                          "description":"Original source-mapped actor readback at 20 Hz."}],
                 "context_inputs":[{"name":"reviewed_roundabout_map","unit":"source",
                                    "description":"Original OpenDRIVE lane and connector review."}],
                 "sweep_dimensions":[],"landmarks":[],"recording_needs":[{"name":"independent_operator_intent",
                                     "unit":"structured","description":"Operator source before movement."}],
                 "limitations":["No worker numeric threshold or legal judgment is asserted."]}}
        jobs.append(write(f"judgment-{index}.json",value))
    bindings={"cell_id":CELL,"actor":ACTOR,"status":"draft",
              "established_contexts":["Frozen roundabout right-turn cell; original map and independent operator intent require reviewed source packets."],
              "law_refs":[{"template_id":TEMPLATE,"binding_kind":"direct"}],"context_refs":[],
              "fixed_parameters":[{"name":"reviewed_roundabout_site","value":"source_packet_pending",
                                   "rationale":"Bind the same original map, vehicle, entry and four camera rig within each comparison."}],
              "variable_parameters":[{"name":name,"kind":kind,"range_or_domain":domain,"used_by_laws":[LAW]}
                  for name,kind,domain in (("operator_intent_request","participant_behavior","right_exit or through"),
                       ("roundabout_lane_request","world_setup","right, left, left_then_right, right_then_left or single_right"),
                       ("actual_exit_request","participant_behavior","right_exit, through_exit or no_exit"))]}
    binding=write("bindings.json",bindings)
    desc=json.loads((HERE/manifest["cases"][0]["construction"]).read_text())["recording_description"]
    baseline={"case_id":AID+"__baseline","paired_probe_id":"roundabout_right_lane_controls",
              "rationale":"Shared source map and operator reference for the exact selected controls.",
              "recording_description":desc,"target_law_id":LAW,"target_type":"baseline",
              "unresolved_judgment_calls":[x[0] for x in JUDGMENTS],
              "variable_assignments":{},"deliberate_differences":[],
              "probe":{"primary_variable":"roundabout_lane_request",
                       "comparison_or_standard":"reviewed allocated right lane and actual exit connector",
                       "target_value_or_branch":"right"}}
    cases=[baseline]
    for row in plan["cases"]:
        cases.append({"case_id":row["case_id"],"paired_probe_id":"roundabout_right_lane_controls",
          "rationale":"Measure independent operator intent, original circular lane and actual connector without prelabeling compliance.",
          "recording_description":desc,"target_law_id":LAW,"target_type":"boundary_probe",
          "unresolved_judgment_calls":[x[0] for x in JUDGMENTS],
          "variable_assignments":{name:{"kind":kind,"value":row[name]} for name,kind in
              (("operator_intent_request","participant_behavior"),("roundabout_lane_request","world_setup"),
               ("actual_exit_request","participant_behavior"))},
          "deliberate_differences":["operator_intent_request","roundabout_lane_request","actual_exit_request"],
          "probe":{"primary_variable":"roundabout_lane_request",
                   "comparison_or_standard":"source-bound intended, requested and observed roundabout operation",
                   "target_value_or_branch":row["roundabout_lane_request"]}})
    proposed={"cell_id":CELL,"actor":ACTOR,"status":"draft","cases":cases,
              "sweep_specs":[{"sweep_id":"mapped_right_lane_review","target_law_id":LAW,
                   "judgment_refs":[{"phrase":phrase,"note":note} for phrase,note in JUDGMENTS],
                   "status":"incomplete","rationale":"Source lane and connector identity is categorical; no legal numeric cutoff exists.",
                   "missing_inputs":["Original Native map allocation, intent record and local legal review."]}],
              "sweeps_expanded":True}
    cref=write("cases.json",proposed)
    index={"format":"worker-semantic-delivery","assignment_id":AID,
           "source":"Exact LVMC 11.43.010(C)(2) text and C240647 frozen cell","status":"draft",
           "stages":{"relevance_batch":batch,"relevance":rel,"template":temp,
                     "judgment_observables":jobs,"bindings":binding,"cases":cref}}
    write("semantic-index.json",index)
    return len(cases)-1

if __name__ == "__main__":
    print(build())
