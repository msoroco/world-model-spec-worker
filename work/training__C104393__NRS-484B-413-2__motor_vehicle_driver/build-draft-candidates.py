"""Materialize 24 unselected exact hill-crest Native construction bundles."""
import hashlib
import json
from pathlib import Path
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parent.parent
NATIVE=HERE/"native"
sys.path.insert(0,str(NATIVE))
from candidate_design import designs
from geometry import open_drive,route,signal_start

NAMES=("primary","fallback1","fallback2","fallback3")
SOURCES=("runner.py","geometry.py","controller.py","cameras.py",
         "engineering.py","signal_control.py","saved_measure.py","fallback_triggers.py",
         "finalize.py")

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def digest(value):return hashlib.sha256(value).hexdigest()
def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2)+"\n")

def main():
    plan=json.loads((HERE/"case-plan.json").read_text())
    common={name:(NATIVE/name).read_text() for name in SOURCES}
    common["tests/test_bundle.py"]=(NATIVE/"test_bundle.py").read_text()
    recording={"channels":[{"name":name,"unit":"structured","sampling_rate_hz":20,
        "method":"Retain original Native state and synchronized frame source for saved verification",
        "time_window":"entire 42 s / 840-frame attempt",
        "reference_frame":"original Native frame and time",
        "uncertainty":"50 ms sampled state; physical and pixel review pending"}
        for name in ("sig.turn_indicator","drv.distance_while","kin.path_length",
            "drv.turning","env.precipitation","kin.speed","native_body_pose_control",
            "camera_frame_join")],
        "context_inputs":[{"name":"area_classification","unit":"categorical",
            "method":"authored any-other-area context joined to surveyed Native map; review pending"}],
        "limitations":["No legal conclusion from offline or synthetic data",
            "Original body, indicator and pixel review required"]}
    manifest={"format":"worker-unselected-draft-construction-manifest-v1",
        "assignment_id":plan["assignment_id"],
        "runtime_manifest_sha256":sha(ROOT/"runtime/pipeline/SOURCE-MANIFEST.json"),
        "status":"draft_not_selected","cases":[]}
    proposals=[]
    for case in plan["cases"]:
        case_id=case["case_id"]; feet=case["requested_setting"]
        suffix=str(feet); variants=designs(feet)
        proposals.append({"case_id":case_id,"target_law_id":plan["law_id"],
            "target_type":"boundary_probe","rationale":"Unselected exact 100/300-foot source threshold; no legal verdict",
            "variable_assignments":{"commanded_signal_distance_ft":{"kind":"controller","value":feet,"unit":"ft"},
                "area_classification":{"kind":"world_setup","value":"any_other_area","unit":"categorical"},
                "actual_signal_distance_ft":{"kind":"subject_behavior","value":None,"unit":"ft"}},
            "recording_description":recording,
            "unresolved_judgment_calls":["Original Native map, body, signal, weather and pixels require review"]})
        contract_rel=f"draft-candidates/{suffix}/measurement-contract.json"
        requirements=[]
        methods={"text-0":("continuous_signal_distance_ft","measure_signal_distance","number"),
            "text-1":("weather_context","measure_weather_context","text"),
            "reviewed-scope-0":("other_area_coverage","measure_other_area_coverage","object"),
            "reviewed-scope-1":("other_area_duplicate","measure_other_area_duplicate","object")}
        for i,d in enumerate(plan["requirement_dispositions"]):
            if case_id in d.get("case_ids",[]):
                output_key,method,value_type=methods[d["requirement"]]
                requirements.append({"disposition_index":i,"requirement":d["requirement"],
                    "source":d["source"],"output_key":output_key,
                    "method":method,"value_type":value_type,
                    "kind":"measured" if d["requirement"]=="text-0" else "sourced_context",
                    "inputs":["native_samples.jsonl","road_geometry.json"]})
        write(HERE/contract_rel,{"format":"worker-measurement-contract-v1",
            "case_id":case_id,"target_distance_ft":feet,"area":"any_other_area",
            "rate_hz":20,"duration_s":42,"requirements":requirements,
            "negative":{"remove":["native_samples.jsonl"],
                "error_contains":"Missing required source: native_samples.jsonl"},
            "status":"unselected_contract_draft"})
        entry={"case_id":case_id,"kind":"draft_not_selected",
            "candidate_risk":{"status":"physical","reason":"Native map, body, indicator and pixels require original observation"},
            "measurement_contract":contract_rel,
            "measurement_procedure":{"entrypoint":"finalize.py","status":"saved_source_diagnostic"},
            "candidates":[]}
        for candidate in NAMES:
            settings=variants[candidate]["config"]
            radius=24.0 if candidate=="fallback1" else 20.0
            request={"case_id":case_id,"candidate_id":candidate,"law_id":plan["law_id"],
                "cell_id":plan["cell_id"],"actor":plan["actor"],
                "rate_hz":20,"duration_s":42,"signal_start_ft":feet,
                "signal_start_station_m":signal_start(feet),"turn_radius_m":radius,
                "controller_lookahead_m":settings["controller_lookahead_m"],
                "camera_height_m":settings["camera_height_m"],
                "camera_fov_deg":settings["camera_fov_deg"],
                "map_sha256":digest(open_drive(radius).encode()),
                "route_sha256":digest(json.dumps(route(radius),separators=(",", ":")).encode()),
                "weather":"clear_noon","area":"any_other_area"}
            request_rel=f"native-constructions/{suffix}-{candidate}.json"
            write(HERE/request_rel,request)
            config={"case_id":case_id,"selected_case_id":case_id,"candidate_id":candidate,
                "law_id":plan["law_id"],"cell_id":plan["cell_id"],"actor":plan["actor"],
                "rate_hz":20,"duration_s":42,"required_atoms":["sig.turn_indicator","drv.turning","kin.speed"],
                "source_packets":[],"mandatory_channels":[c["name"] for c in recording["channels"]],
                "cameras":[{"name":name,"width":width,"height":height} for name,width,height in
                    (("overview",1920,1080),("approach",1280,720),
                     ("signal_close",1280,720),("driver_reference",1280,720))],
                "case":{"case_id":case_id},"recording_description":recording,
                "native_request":request,"status":"unselected_native_runner_prototype"}
            files=[{"path":name,"content":content} for name,content in common.items()]
            files.append({"path":"config.json","content":json.dumps(config,indent=2)+"\n"})
            construction={"case_id":case_id,"cell_id":plan["cell_id"],
                "law_id":plan["law_id"],"actor":plan["actor"],"entrypoint":"runner.py",
                "files":files,"recording_description":recording,
                "measurement_plan":{"method":"saved original indicator/path/turn interval","status":"draft"},
                "static_checks":["owned hill-crest OpenDRIVE","exact request identity",
                    "four synchronized cameras","840 original Native frames"],
                "termination_rules":["retain failed capture and restore world"],
                "status":"unselected_cpu_draft"}
            relative=f"draft-candidates/{suffix}/{candidate}/construction.json"
            write(HERE/relative,construction)
            selected={"id":candidate,"construction":relative,
                "construction_sha256":sha(HERE/relative)}
            if candidate=="primary":entry.update(selected)
            else:
                selected.update(trigger=variants[candidate]["trigger"],
                    changed_knobs=variants[candidate]["changed_knobs"])
                entry["candidates"].append(selected)
        manifest["cases"].append(entry)
    write(HERE/"draft-execution-manifest.json",manifest)
    write(HERE/"proposals/cases.json",{"cell_id":plan["cell_id"],"actor":plan["actor"],
        "status":"unselected_draft","cases":proposals})
    print(json.dumps({"cases":len(manifest["cases"]),"candidates":len(manifest["cases"])*4,
        "status":manifest["status"]}))

if __name__=="__main__":main()
