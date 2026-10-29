"""Deterministic local construction for one assigned exact case."""
import copy, hashlib, json, xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
ASSIGNMENT=json.loads((REPO/'inputs'/ROOT.name/'assignment.json').read_text())
AID=ASSIGNMENT['assignment_id']
CASE=AID+'__selected_marked_lane_change'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def put(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def channel(name,unit,method):
    return {'name':name,'unit':unit,'sampling_rate_hz':20,'method':method,'time_window':'entire original 25-second approach and turn','reference_frame':'original CARLA world XY and frame/time','uncertainty':'20 Hz sampling; native geometry and physical visibility require local review'}
def make_scene():
    source=REPO/'references/accepted-sources/C111325/scene-stop257-v1.xodr'
    tree=ET.parse(source);root=tree.getroot()
    root.find('header').set('name','C144550-marked-two-lane-change-v1')
    road=next(r for r in root.findall('road') if r.attrib['id']=='1')
    for child in list(root):
        if child.tag=='road' and child is not road or child.tag=='junction':root.remove(child)
    road.set('name','synthetic_public_two_lane_highway');road.set('length','400')
    road.find('link').clear()
    geo=road.find('planView/geometry');geo.set('x','-200');geo.set('length','400')
    road.find('objects').clear();road.find('signals').clear()
    ET.indent(tree,space='  ');tree.write(ROOT/'scene.xodr',encoding='unicode',xml_declaration=True)
def main():
    make_scene()
    desc={'channels':[channel('kin.speed','m/s','native actor velocity'),channel('lane_markings','structured','native two same-direction lane boundaries and painted markings'),channel('signal_timing','structured','original indicator and full-body boundary crossing frames'),channel('target_lane_gap','structured','original target-lane actor body gap, closing speed and check telemetry')],'context_inputs':[],'limitations':['Driver ascertainment is not inferred from a numerical gap.','Indicator pixels and target-lane safety need local review.']}
    case={'case_id':CASE,'target_law_id':ASSIGNMENT['law_id'],'target_type':'boundary_probe','rationale':'Exact marked two-lane selected branch; indicator precedes a full-body lane departure and target-lane gap is retained without a legal safety threshold.','variable_assignments':{'approach_speed_mps':{'value':5.0,'unit':'m/s','kind':'controller'}},'unresolved_judgment_calls':['Whether the driver ascertained safety is not resolved by a gap proxy.','Original pixels, lane marks, body movement and nearby traffic need GPU review.'],'recording_description':desc}
    proposal={'cell_id':ASSIGNMENT['cell_id'],'actor':ASSIGNMENT['actor'],'status':'draft','sweep_specs':[],'cases':[case]}
    put(ROOT/'proposals/cases.json',proposal)
    config={'case':case,'case_id':CASE,'selected_case_id':CASE,'supported_case_ids':[CASE],'cell_id':ASSIGNMENT['cell_id'],'law_id':ASSIGNMENT['law_id'],'actor':ASSIGNMENT['actor'],'required_atoms':['kin.speed'],'source_packets':[],'duration_s':25,'camera':{'width':960,'height':540,'fov_deg':90},'recording_description':desc,'law_context':{'public_dedication':'synthetic Nevada public highway designation in authored scenario','public_vehicle_access':True,'non_alley':True},'public_way_road_ids':[1],'authored_test_context':{'core_assumptions':[['asm.public_highway',True]]}}
    put(ROOT/'config.json',config)
    dispositions=[
      {'requirement':'Highway has two or more clearly marked lanes for traffic in one direction','source':'NRS 484B.223(1)(b); activation','status':'selected_required','evidence_or_gap':'Native road has two same-direction driving lanes and a marked separating line; original rendered marking visibility needs GPU review.'},
      {'requirement':'Appropriate turn signal is given before the vehicle moves from its lane','source':'NRS 484B.223(1)(b); first conjunct','status':'selected_required','evidence_or_gap':'Original indicator state and first body-boundary departure frame/time are saved; legal appropriateness remains local review.'},
      {'requirement':'Driver ascertains lane movement can be made with safety','source':'NRS 484B.223(1)(b); second conjunct','status':'selected_required','evidence_or_gap':'Target-lane vehicle full-body gap and relative speed are measured; actual driver check and safety judgment remain unresolved.'}
    ]
    term_channels={'drv.laned_roadway':['lane_markings'],'st.lane':['lane_markings'],'drv.lane_change':['signal_timing'],'sig.turn_indicator':['signal_timing'],'drv.distance_while':['signal_timing'],'drv.lane_change_feasible':['target_lane_gap'],'rel.surface_gap':['target_lane_gap'],'drv.time_to_conflict':['target_lane_gap']}
    mapping={t['term']:{'evidence':'Saved '+', '.join(term_channels[t['term']])+' from original frame; driver ascertainment and safety require review','channels':term_channels[t['term']],'source_refs':['inputs/'+AID+'/assignment.json']} for t in ASSIGNMENT['source_observation_terms']}
    sources=[{'path':'inputs/'+AID+'/assignment.json','sha256':sha(REPO/'inputs'/AID/'assignment.json')},{'path':'references/accepted-sources/C111325/scene-stop257-v1.xodr','sha256':sha(REPO/'references/accepted-sources/C111325/scene-stop257-v1.xodr')},{'path':'references/accepted-sources/C111325/stop257_controller_v2.py','sha256':sha(REPO/'references/accepted-sources/C111325/stop257_controller_v2.py')}]
    plan={'assignment_id':AID,'actor':ASSIGNMENT['actor'],'cell_id':ASSIGNMENT['cell_id'],'law_id':ASSIGNMENT['law_id'],'selected_branch':ASSIGNMENT['branch'],'requirement_dispositions':dispositions,'cases':[{'case_id':CASE,'target_law_id':ASSIGNMENT['law_id']}],'comparisons':[],'observations':[{'name':c['name'],'mandatory':True} for c in desc['channels']],'sources':sources,'existing_evidence':ASSIGNMENT['existing_evidence'],'runtime_uncertainties':['No CARLA run performed; native route, full body motion, camera visibility and physical public-way context unverified.'],'source_observation_mapping':mapping}
    put(ROOT/'case-plan.json',plan)
    methods=['marked_lane_context','signal_before_departure','target_lane_gap']
    outputs=['marked_same_direction_lanes','indicator_precedes_lane_departure','target_lane_safety_observations']
    inputs=[['lane_geometry.json'],['lane_geometry.json','lane_change_history.jsonl'],['lane_change_history.jsonl']]
    kinds=['sourced_context','measured','measured']
    contract={'format':'worker-measurement-contract-v1','requirements':[{'disposition_index':i,'requirement':d['requirement'],'source':d['source'],'output_key':outputs[i],'method':methods[i],'kind':kinds[i],'value_type':'object','inputs':inputs[i]} for i,d in enumerate(dispositions)],'negative':{'remove':['lane_change_history.jsonl'],'error_contains':'Missing required source: lane_change_history.jsonl'}}
    put(ROOT/'measurement-contract.json',contract)
    put(ROOT/'lane_geometry.json',{'road_id':1,'same_direction_lane_ids':[-1,-2],'lane_boundary_marking':'broken white','lane_boundary_y_m':3.5})
    fixture=[
      {'frame':21714,'time_s':.05,'ego_body_xy_m':[[-12,4.2],[-12,6.3],[-8,4.2],[-8,6.3]],'target_body_xy_m':[[-26,.6],[-26,2.8],[-22,.6],[-22,2.8]],'ego_speed_mps':4.0,'target_speed_mps':5.0,'left_blinker':True,'driver_check_recorded':False},
      {'frame':21715,'time_s':.1,'ego_body_xy_m':[[-11,3.2],[-11,5.3],[-7,3.2],[-7,5.3]],'target_body_xy_m':[[-25,.6],[-25,2.8],[-21,.6],[-21,2.8]],'ego_speed_mps':4.0,'target_speed_mps':5.0,'left_blinker':True,'driver_check_recorded':False},
      {'frame':21716,'time_s':.15,'ego_body_xy_m':[[-10,1.2],[-10,3.3],[-6,1.2],[-6,3.3]],'target_body_xy_m':[[-24,.6],[-24,2.8],[-20,.6],[-20,2.8]],'ego_speed_mps':4.0,'target_speed_mps':5.0,'left_blinker':True,'driver_check_recorded':False},
    ]
    (ROOT/'lane_change_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in fixture))
    additions=[{'path':n,'source':'work/'+AID+'/'+n,'sha256':sha(ROOT/n)} for n in ('lane_geometry.json','lane_change_history.jsonl')]
    recipe={'format':'worker-fixture-recipe-v1','base':'runtime/main-pipeline-v1/fixtures/retained-speed','remove':['case.json','config.json','result.json'],'additions':additions}
    put(ROOT/'fixture-recipe.json',recipe)
    files=[]
    for name in ('config.json','runner.py','analyze.py','scene.xodr','tests/test_case.py'):
        files.append({'path':name,'content':(ROOT/name).read_text()})
    construction={'case_id':CASE,'cell_id':ASSIGNMENT['cell_id'],'actor':ASSIGNMENT['actor'],'entrypoint':'runner.py','files':files,'measurement_plan':{'selected_requirement_contract':'measurement-contract.json','physical_acceptance':False},'recording_description':desc,'static_checks':['connected OpenDRIVE left-turn arc','opposing traffic lanes','camera resolution','complete planned channels'],'termination_rules':['25 seconds or explicit native failure; retain source and restore world'],'mechanisms':['native VehicleControl steering along curved junction','PipelineCapture original source channels','FrameMap and original RGB FFV1 video']}
    put(ROOT/'construction.json',construction)
    manifest={'format':'worker-execution-manifest-v1','assignment_id':AID,'runtime_manifest_sha256':sha(REPO/'runtime/main-pipeline-v1/SOURCE-MANIFEST.json'),'cases':[{'case_id':CASE,'kind':'capability','construction':'construction.json','construction_sha256':sha(ROOT/'construction.json'),'measurement_procedure':{'entrypoint':'analyze.py','output_schema':'analysis-report.json'},'measurement_contract':'measurement-contract.json','fixture_recipe':'work/'+AID+'/fixture-recipe.json','native_handoff':{'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'},'acquisition':{c['name']:{'entrypoint':'runner.py','method':c['method'],'evidence':'original frame capture and saved finalizer'} for c in desc['channels']}}]}
    put(ROOT/'execution-manifest.json',manifest)
if __name__=='__main__':main()
