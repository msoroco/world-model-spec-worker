"""Deterministic local construction for one assigned exact case."""
import copy, hashlib, json, xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
ASSIGNMENT=json.loads((REPO/'inputs'/ROOT.name/'assignment.json').read_text())
AID=ASSIGNMENT['assignment_id']
CASE=AID+'__selected_initial_yield'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def put(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def channel(name,unit,method):
    return {'name':name,'unit':unit,'sampling_rate_hz':20,'method':method,'time_window':'entire original 25-second approach and turn','reference_frame':'original CARLA world XY and frame/time','uncertainty':'20 Hz sampling; native geometry and physical visibility require local review'}
def make_scene():
    source=REPO/'references/accepted-sources/C111325/scene-stop257-v1.xodr'
    tree=ET.parse(source);root=tree.getroot()
    root.find('header').set('name','C109749-left253-opposing-inside-v1')
    for road in root.findall('road'):
        for group in ('objects','signals'):road.find(group).clear()
    original=next(r for r in root.findall('road') if r.attrib['id']=='11')
    turn=copy.deepcopy(original);turn.set('name','left_turn_west_to_north');turn.set('id','13');turn.set('length',str(7*3.141592653589793/2))
    link=turn.find('link');link.find('predecessor').set('elementId','1');link.find('successor').set('elementId','4')
    geo=turn.find('planView/geometry');geo.set('length',str(7*3.141592653589793/2))
    geo.remove(geo.find('line'));ET.SubElement(geo,'arc',curvature=str(1/7))
    root.insert(list(root).index(root.find('junction')),turn)
    junction=root.find('junction')
    conn=ET.SubElement(junction,'connection',id='4',incomingRoad='1',connectingRoad='13',contactPoint='start')
    ET.SubElement(conn,'laneLink',{'from':'-1','to':'-1'})
    # Native map may still need a route-specific connection/readback review.
    ET.indent(tree,space='  ')
    tree.write(ROOT/'scene.xodr',encoding='unicode',xml_declaration=True)
def main():
    make_scene()
    desc={'channels':[channel('kin.speed','m/s','native subject actor velocity'),channel('intersection_occupancy','structured','original full-body polygon overlap'),channel('oncoming_geometry','structured','opposing full-body intersection occupancy and speed'),channel('yield_timing','structured','original subject and opposing motion, control and indicator sequence')],'context_inputs':[],'limitations':['Physical yielding and immediate hazard are legal judgments, not inferred from a three-frame fixture.','Signal timing and actual oncoming clearance remain GPU checks.']}
    case={'case_id':CASE,'target_law_id':ASSIGNMENT['law_id'],'target_type':'boundary_probe','rationale':'Exact initial duty with opposing vehicle within the intersection; record subject hold and later turn after opposing clearance.','variable_assignments':{'approach_speed_mps':{'value':5.0,'unit':'m/s','kind':'controller'}},'unresolved_judgment_calls':['Physical yield and signal sufficiency require local review.','No numerical immediate-hazard threshold is imposed because the selected opposite vehicle is within the intersection.'],'recording_description':desc}
    proposal={'cell_id':ASSIGNMENT['cell_id'],'actor':ASSIGNMENT['actor'],'status':'draft','sweep_specs':[],'cases':[case]}
    put(ROOT/'proposals/cases.json',proposal)
    config={'case':case,'case_id':CASE,'selected_case_id':CASE,'supported_case_ids':[CASE],'cell_id':ASSIGNMENT['cell_id'],'law_id':ASSIGNMENT['law_id'],'actor':ASSIGNMENT['actor'],'required_atoms':['kin.speed'],'source_packets':[],'duration_s':25,'camera':{'width':960,'height':540,'fov_deg':90},'recording_description':desc,'law_context':{'public_dedication':'synthetic Nevada public highway designation in authored scenario','public_vehicle_access':True,'non_alley':True},'public_way_road_ids':[1,2,3,4,11,12,13],'authored_test_context':{'core_assumptions':[['asm.public_highway',True]]}}
    put(ROOT/'config.json',config)
    dispositions=[
      {'requirement':'Driver is within the intersection intending a left turn','source':'NRS 484B.253; selected witness branch','status':'selected_required','evidence_or_gap':'Original full-body polygon occupancy, route intent, speed and controls are saved; physical realization is a GPU check.'},
      {'requirement':'An opposing vehicle is within the intersection','source':'NRS 484B.253; selected witness branch','status':'selected_required','evidence_or_gap':'Opposing native actor body, speed, direction and intersection occupancy are saved on original frames.'},
      {'requirement':'Subject yields before making the left turn while opposing vehicle occupies the intersection','source':'NRS 484B.253; initial yield duty','status':'selected_required','evidence_or_gap':'Original overlap speeds, clearance and turn-progress ordering are measured; no legal yield verdict is assigned.'},
      {'requirement':'After having yielded and signalled when required, other oncoming drivers yield to turning vehicle','source':'NRS 484B.253; subsequent clause','status':'alternative_pending','evidence_or_gap':'Subsequent branch is not selected; indicator history is retained but signal sufficiency and reciprocal duty are not established.'}
    ]
    term_channels={'drv.in_intersection':['intersection_occupancy'],'st.lane_enters':['intersection_occupancy'],'drv.turning':['yield_timing'],'sig.turn_indicator':['yield_timing'],'rel.oncoming':['oncoming_geometry'],'drv.approaching':['oncoming_geometry'],'drv.time_to_conflict':['oncoming_geometry'],'drv.yields_to':['yield_timing'],'drv.arrival_order':['yield_timing'],'kin.speed':['kin.speed']}
    mapping={t['term']:{'evidence':'Saved '+', '.join(term_channels[t['term']])+' from original frame; legal immediate-hazard and yield standards remain open','channels':term_channels[t['term']],'source_refs':['inputs/'+AID+'/assignment.json']} for t in ASSIGNMENT['source_observation_terms']}
    sources=[{'path':'inputs/'+AID+'/assignment.json','sha256':sha(REPO/'inputs'/AID/'assignment.json')},{'path':'references/accepted-sources/C111325/scene-stop257-v1.xodr','sha256':sha(REPO/'references/accepted-sources/C111325/scene-stop257-v1.xodr')},{'path':'examples/judgment/README.md','sha256':sha(REPO/'examples/judgment/README.md')}]
    plan={'assignment_id':AID,'actor':ASSIGNMENT['actor'],'cell_id':ASSIGNMENT['cell_id'],'law_id':ASSIGNMENT['law_id'],'selected_branch':ASSIGNMENT['branch'],'requirement_dispositions':dispositions,'cases':[{'case_id':CASE,'target_law_id':ASSIGNMENT['law_id']}],'comparisons':[],'observations':[{'name':c['name'],'mandatory':True} for c in desc['channels']],'sources':sources,'existing_evidence':ASSIGNMENT['existing_evidence'],'runtime_uncertainties':['No CARLA run performed; native route, full body motion, camera visibility and physical public-way context unverified.'],'source_observation_mapping':mapping}
    put(ROOT/'case-plan.json',plan)
    methods=['subject_interval','opposing_interval','yield_sequence']
    outputs=['subject_inside_left_turn','opposing_vehicle_inside','yield_and_turn_sequence']
    inputs=[['left253_history.jsonl']]*3
    kinds=['measured','measured','measured']
    contract={'format':'worker-measurement-contract-v1','requirements':[{'disposition_index':i,'requirement':d['requirement'],'source':d['source'],'output_key':outputs[i],'method':methods[i],'kind':kinds[i],'value_type':'object','inputs':inputs[i]} for i,d in enumerate(dispositions) if d['status']=='selected_required'],'negative':{'remove':['left253_history.jsonl'],'error_contains':'Missing required source: left253_history.jsonl'}}
    put(ROOT/'measurement-contract.json',contract)
    fixture=[
      {'frame':21714,'time_s':.05,'intersection_polygon_xy_m':[[-7,-7],[7,-7],[7,7],[-7,7]],'ego_body_xy_m':[[-4,0],[-4,2],[-2,0],[-2,2]],'oncoming_body_xy_m':[[1,-2],[1,0],[3,-2],[3,0]],'ego_speed_mps':.2,'oncoming_speed_mps':3.5,'ego_turn_intent':'left','ego_turn_progress':False,'ego_left_blinker':True},
      {'frame':21715,'time_s':.1,'intersection_polygon_xy_m':[[-7,-7],[7,-7],[7,7],[-7,7]],'ego_body_xy_m':[[-4,0],[-4,2],[-2,0],[-2,2]],'oncoming_body_xy_m':[[-2,-2],[-2,0],[0,-2],[0,0]],'ego_speed_mps':0.0,'oncoming_speed_mps':3.5,'ego_turn_intent':'left','ego_turn_progress':False,'ego_left_blinker':True},
      {'frame':21716,'time_s':.15,'intersection_polygon_xy_m':[[-7,-7],[7,-7],[7,7],[-7,7]],'ego_body_xy_m':[[-2,-2],[-2,0],[0,-2],[0,0]],'oncoming_body_xy_m':[[-12,-2],[-12,0],[-10,-2],[-10,0]],'ego_speed_mps':2.0,'oncoming_speed_mps':3.5,'ego_turn_intent':'left','ego_turn_progress':True,'ego_left_blinker':True},
    ]
    (ROOT/'left253_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in fixture))
    additions=[{'path':'left253_history.jsonl','source':'work/'+AID+'/left253_history.jsonl','sha256':sha(ROOT/'left253_history.jsonl')}]
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
