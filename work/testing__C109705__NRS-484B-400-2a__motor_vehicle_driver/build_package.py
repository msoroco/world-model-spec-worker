"""Deterministic local construction for one assigned exact case."""
import copy, hashlib, json, xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
ASSIGNMENT=json.loads((REPO/'inputs'/ROOT.name/'assignment.json').read_text())
AID=ASSIGNMENT['assignment_id']
CASE=AID+'__selected_left_turn'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def put(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def channel(name,unit,method):
    return {'name':name,'unit':unit,'sampling_rate_hz':20,'method':method,'time_window':'entire original 25-second approach and turn','reference_frame':'original CARLA world XY and frame/time','uncertainty':'20 Hz sampling; native geometry and physical visibility require local review'}
def make_scene():
    source=REPO/'references/accepted-sources/C111325/scene-stop257-v1.xodr'
    tree=ET.parse(source);root=tree.getroot()
    root.find('header').set('name','C109705-left400-two-directional-v1')
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
    desc={'channels':[channel('kin.speed','m/s','native actor velocity'),channel('roadway_geometry','structured','original map/topology plus road-direction survey'),channel('driver_control','structured','native VehicleControl and actor route history'),channel('approach_position','structured','original full body vertices relative to directed centerline')],'context_inputs':[],'limitations':['Native map topology, actual full body route and camera visibility remain GPU checks.','Synthetic public dedication is an authored condition, not a finding about a real highway.']}
    case={'case_id':CASE,'target_law_id':ASSIGNMENT['law_id'],'target_type':'boundary_probe','rationale':'Exact selected two-directional left-turn approach; observe full body relative to centerline without a legal lateral cutoff.','variable_assignments':{'approach_speed_mps':{'value':5.0,'unit':'m/s','kind':'controller'}},'unresolved_judgment_calls':['Which portion of the right half is nearest the centerline remains legal review; no threshold imposed.','Native intended and realized turn, public way and camera pixels need verification.'],'recording_description':desc}
    proposal={'cell_id':ASSIGNMENT['cell_id'],'actor':ASSIGNMENT['actor'],'status':'draft','sweep_specs':[],'cases':[case]}
    put(ROOT/'proposals/cases.json',proposal)
    config={'case':case,'case_id':CASE,'selected_case_id':CASE,'supported_case_ids':[CASE],'cell_id':ASSIGNMENT['cell_id'],'law_id':ASSIGNMENT['law_id'],'actor':ASSIGNMENT['actor'],'required_atoms':['kin.speed'],'source_packets':[],'duration_s':25,'camera':{'width':960,'height':540,'fov_deg':90},'recording_description':desc,'law_context':{'public_dedication':'synthetic Nevada public highway designation in authored scenario','public_vehicle_access':True,'non_alley':True},'public_way_road_ids':[1,2,3,4,11,12,13],'authored_test_context':{'core_assumptions':[['asm.public_highway',True]]}}
    put(ROOT/'config.json',config)
    dispositions=[
      {'requirement':'Establish public-highway status and a non-alley intersection','source':'NRS 484B.400(2)(a); accepted witness required_context','status':'selected_required','evidence_or_gap':'Authored public dedication/access and junction geometry; actual native map and public-way facts require local review.'},
      {'requirement':'Both intersecting highways permit opposite-direction travel','source':'NRS 484B.400(2)(a); selected witness branch','status':'selected_required','evidence_or_gap':'Four undivided approach roads with opposing lanes and a connected curved left-turn junction; native topology is a GPU check.'},
      {'requirement':'An identified driver controls a vehicle and intends a left turn','source':'NRS 484B.400(2)(a); accepted witness required_context','status':'selected_required','evidence_or_gap':'Native VehicleControl route from west approach to north exit; actor identity and realized motion require local check.'},
      {'requirement':'Approach within the right half nearest its centerline before intersection entry','source':'NRS 484B.400(2)(a); law text and supplied summary timing','status':'selected_required','evidence_or_gap':'Saved full body vertices and signed centerline distances for every approach frame; no invented legal lateral cutoff.'}
    ]
    term_channels={'drv.turning':['driver_control'],'st.intersection':['roadway_geometry'],'st.lane_enters':['roadway_geometry'],'st.centre_line':['roadway_geometry','approach_position'],'rel.occupies':['approach_position'],'kin.position':['approach_position'],'st.one_way_roadway':['roadway_geometry'],'st.lane_direction':['roadway_geometry']}
    mapping={t['term']:{'evidence':'Saved '+', '.join(term_channels[t['term']])+' from original frame and map; legal interpretation remains open','channels':term_channels[t['term']],'source_refs':['inputs/'+AID+'/assignment.json']} for t in ASSIGNMENT['source_observation_terms']}
    sources=[{'path':'inputs/'+AID+'/assignment.json','sha256':sha(REPO/'inputs'/AID/'assignment.json')},{'path':'references/accepted-sources/C111325/scene-stop257-v1.xodr','sha256':sha(REPO/'references/accepted-sources/C111325/scene-stop257-v1.xodr')},{'path':'references/accepted-sources/C111325/stop257_controller_v2.py','sha256':sha(REPO/'references/accepted-sources/C111325/stop257_controller_v2.py')}]
    plan={'assignment_id':AID,'actor':ASSIGNMENT['actor'],'cell_id':ASSIGNMENT['cell_id'],'law_id':ASSIGNMENT['law_id'],'selected_branch':ASSIGNMENT['branch'],'requirement_dispositions':dispositions,'cases':[{'case_id':CASE,'target_law_id':ASSIGNMENT['law_id']}],'comparisons':[],'observations':[{'name':c['name'],'mandatory':True} for c in desc['channels']],'sources':sources,'existing_evidence':ASSIGNMENT['existing_evidence'],'runtime_uncertainties':['No CARLA run performed; native route, full body motion, camera visibility and physical public-way context unverified.'],'source_observation_mapping':mapping}
    put(ROOT/'case-plan.json',plan)
    methods=['public_highway_context','bidirectional_intersection','left_turn_control','centerline_offset']
    outputs=['public_highway_context','two_directional_intersection','driver_left_turn_control','approach_centerline_geometry']
    inputs=[['law_context.json'],['road_geometry.json'],['route_control.json'],['road_geometry.json','body_vertices.jsonl']]
    kinds=['sourced_context','sourced_context','measured','measured']
    contract={'format':'worker-measurement-contract-v1','requirements':[{'disposition_index':i,'requirement':d['requirement'],'source':d['source'],'output_key':outputs[i],'method':methods[i],'kind':kinds[i],'value_type':'object','inputs':inputs[i]} for i,d in enumerate(dispositions)],'negative':{'remove':['road_geometry.json'],'error_contains':'Missing required source: road_geometry.json'}}
    put(ROOT/'measurement-contract.json',contract)
    (ROOT/'law_context.json').write_text(json.dumps(config['law_context'],indent=2)+'\n')
    road={'road_ids':[1,2,3,4,11,12,13],'directions_by_road':{'1':['east','west'],'2':['east','west'],'3':['north','south'],'4':['north','south']},'intersection_polygon_xy_m':[[-7,-7],[7,-7],[7,7],[-7,7]],'approach_direction_xy':[1,0],'approach_centerline_point_xy_m':[0,0]}
    put(ROOT/'road_geometry.json',road)
    put(ROOT/'route_control.json',{'actor_role':'subject','control_mode':'diagnostic authored controller route','intended_route':'west approach to north exit, left turn','recorded_frames':[1,2,3]})
    with (ROOT/'body_vertices.jsonl').open('w') as stream:
        for i,x in enumerate([-30,-29,-28]):
            stream.write(json.dumps({'frame':21714+i,'time_s':.05*(i+1),'body_vertices_xy_m':[[x-2,.6],[x-2,2.8],[x+2,.6],[x+2,2.8]]})+'\n')
    additions=[]
    for name in ('law_context.json','road_geometry.json','route_control.json','body_vertices.jsonl'):
        additions.append({'path':name,'source':'work/'+AID+'/'+name,'sha256':sha(ROOT/name)})
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
