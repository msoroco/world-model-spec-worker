"""Draft the original semantic stages for source review, without a verdict."""
from __future__ import annotations

import hashlib
import json
import copy
from pathlib import Path
from build_constructions import description

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
ASSIGNMENT=HERE.name
LAW="NRS-484B-440-1"
ACTOR="motor_vehicle_driver"


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,ensure_ascii=False,allow_nan=False)+"\n")


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    source=ROOT/"inputs"/ASSIGNMENT/"assignment.json"
    assignment=json.loads(source.read_text())
    quote=assignment["law"]["text"]
    if assignment["law"]["id"]!=LAW or assignment["cell_id"]!="C135705":
        raise ValueError("frozen law/cell differs")
    scenes={suffix:json.loads((HERE/"cases"/suffix/"scene.json").read_text())
            for suffix in ("passage_clear_view","passage_blocked","view_occluded_both")}
    template_id=LAW+"@"+ACTOR
    relevance={"cell_id":"C135705","actor":ACTOR,"status":"draft",
        "relevant_laws":[{"law_id":LAW,"quote":quote,"applies_to":[ACTOR],
            "relevance_type":"conditional standing-vehicle passage and two-sided clear-view obligations",
            "confidence":"low","notes":"Highway/district, practicability and subsection (2) disability facts require source review; geometry is not a legal verdict."}],
        "borderline_excluded":[]}
    template={"template_id":template_id,"law_id":LAW,"actor":ACTOR,"quote":quote,
        "structure":{"law_id":LAW,
            "activation":{"condition":"Stopping, parking or leaving a vehicle standing on a highway outside a business or residence district.","numeric_conditions":[]},
            "obligation":{"description":"When practicable, leave the paved or main-traveled part; in every event retain unobstructed opposite width for free passage and clear view of the stopped vehicle from 200 feet in each direction.",
                          "type":"standing_location_passage_and_visibility","numeric_conditions":[{"name":"two_sided_clear_view_distance","value":200,"unit":"ft","metres":60.96}]},
            "exceptions":[{"source_clause":quote[quote.index("This section shall not apply"):],
                           "description":"Mechanical disability alone is insufficient; onset while on traveled portion, impossibility and temporary duration need independent evidence."}],
            "timing":{"description":"Observe stopped body and passing traffic across every original frame; assess both approach directions at 200 feet.","numeric_conditions":[]},
            "judgment_calls_needed":[{"phrase":phrase,"note":note} for phrase,note in (
                ("outside of a business or residence district","Administrative road/district source required."),
                ("practicable","Shoulder geometry and real vehicle/traffic conditions plus contextual review required."),
                ("unobstructed width ... free passage","Measure actual remaining width and full-body passage; no statutory width cutoff supplied."),
                ("clear view ... 200 feet in each direction","At-boundary two-sided original visibility and physical occluders must be reviewed."),
                ("disabled ... impossible to avoid ... temporarily","Mechanism, onset, failed movement and elapsed duration must be separately observed and judged."))]},
        "parameter_refs":[{"name":name,"kind":"world_setup","range_or_domain":domain} for name,domain in (
            ("standing_body_position","road edge versus opposing route intrusion"),
            ("two_sided_occluders","absent versus two constructed prop footprints"),
            ("passing_body_route","westbound full-body passage, fixed within comparisons"),
            ("disability_mechanism","engine off and brake lock attempt; exception facts unverified"))]}
    judgment_specs=[
        (["district_review"],["authored_road","district_review"],
         "An authored OpenDRIVE road does not establish administrative district status."),
        (["standing_body_xy_m","authored_road"],["authored_road"],
         "No fixed geometric proxy determines practicability."),
        (["standing_body_xy_m","other_vehicle_body_xy_m"],["authored_road"],
         "No statutory width cutoff is supplied."),
        (["two_sided_200ft_sight"],["authored_road"],
         "XY line intersection alone does not establish optical visibility."),
        (["mechanical_failure_attempt","standing_body_xy_m"],["district_review"],
         "Worker disable command alone does not establish the subsection (2) exception.")]
    judgments=[]
    calls=template["structure"]["judgment_calls_needed"]
    description_by_name={item["name"]:item for section in ("channels","context_inputs")
                         for item in description()[section]}
    for call,(names,context_names,limitation) in zip(calls,judgment_specs):
        phrase=call["phrase"]
        observable=lambda name:{"name":name,"unit":description_by_name[name]["unit"],
                                "description":description_by_name[name]["method"]}
        judgments.append({"template_id":template_id,"phrase":phrase,"note":call["note"],"status":"draft",
            "observable_requirements":{"observables":[observable(name) for name in names],
                "context_inputs":[observable(name) for name in context_names],"sweep_dimensions":[],
                "landmarks":[],
                "recording_needs":[observable(name) for name in names],
                "limitations":[limitation]}})
    bindings={"cell_id":"C135705","actor":ACTOR,"status":"draft",
        "established_contexts":["assigned narrow-road standing branch; district and highway classification pending"],
        "law_refs":[{"template_id":template_id,"binding_kind":"direct"}],"context_refs":[],
        "fixed_parameters":[{"name":"paved_road_and_shoulders","kind":"world_setup","range_or_domain":"source-hashed candidate OpenDRIVE"},
                            {"name":"passing_body_route","kind":"world_setup","range_or_domain":"westbound opposite side"}],
        "variable_parameters":[{"name":name,"kind":"world_setup","range_or_domain":domain,"used_by_laws":[LAW]} for name,domain in (
            ("standing_body_position","road edge versus opposite-lane intrusion"),
            ("two_sided_occluders","none versus two physical props"))]}
    cases={"cell_id":"C135705","actor":ACTOR,"status":"draft","sweeps_expanded":True,
           "sweep_specs":[{"sweep_id":f"c135705-judgment-{index}",
               "target_law_id":LAW,"status":"incomplete",
               "judgment_refs":[{"phrase":call["phrase"],"note":call["note"]}],
               "rationale":"Original physical and source review are needed; no judgment threshold inferred from fixture geometry.",
               "missing_inputs":["original Native capture and independent source review"]}
               for index,call in enumerate(calls,1)],
           "cases":[]}
    for suffix,scene in scenes.items():
        cases["cases"].append({"case_id":scene["case_id"],"target_law_id":LAW,
            "target_type":"boundary_probe",
            "rationale":{"passage_clear_view":"Reference: measured passage and both 200-foot sight rays clear.",
                "passage_blocked":"Car-sized standing body intrudes into westbound passing route.",
                "view_occluded_both":"Two actual props obstruct opposite 200-foot approach rays."}[suffix],
            "variable_assignments":{"standing_body_position":{"kind":"world_setup","value":scene["standing_body_xy_m"]},
                "two_sided_occluders":{"kind":"world_setup","value":scene["sight_occluders_xy_m"]}},
            "paired_probe_id":"standing_passage_sight_contrasts",
            "deliberate_differences":([] if suffix=="passage_clear_view" else
                ["standing_body_position"] if suffix=="passage_blocked" else ["two_sided_occluders"]),
            "probe":{"primary_variable":"two_sided_occluders" if suffix=="view_occluded_both" else "standing_body_position",
                     "comparison_or_standard":"controlled physical contrast under one exact law branch",
                     "target_value_or_branch":suffix},
            "unresolved_judgment_calls":[call["phrase"] for call in calls],
            "recording_description":description()})
    baseline=copy.deepcopy(cases["cases"][0])
    baseline["case_id"]=ASSIGNMENT+"__semantic_baseline"
    baseline["target_type"]="baseline"
    baseline["rationale"]="Shared semantic reference for the two selected physical comparisons; no additional recording."
    baseline.pop("paired_probe_id",None)
    baseline.pop("probe",None)
    cases["cases"].append(baseline)
    proposal_dir=HERE/"proposals";stages={}
    values={"relevance_batch":relevance,"relevance":relevance,"template":template,
            "bindings":bindings,"cases":cases}
    for name,value in values.items():
        path=proposal_dir/(name+".json");write(path,value)
        stages[name]={"path":"proposals/"+path.name,"sha256":sha(path)}
    stages["judgment_observables"]=[]
    for index,value in enumerate(judgments,1):
        path=proposal_dir/f"judgment-{index}.json";write(path,value)
        stages["judgment_observables"].append({"path":"proposals/"+path.name,"sha256":sha(path)})
    write(proposal_dir/"semantic-index.json",{"format":"worker-semantic-delivery",
          "assignment_id":ASSIGNMENT,"source":{"path":str(source.relative_to(ROOT)),"sha256":sha(source)},
          "stages":stages,"status":"draft_local_source_and_physical_review_pending"})
    print(json.dumps({"proposal_stages":len(values)+len(judgments),"case_count":len(cases["cases"]),
                      "source_sha256":sha(source)}))


if __name__=="__main__":main()
