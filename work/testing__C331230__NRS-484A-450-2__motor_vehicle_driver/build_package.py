"""Deterministic local construction for one assigned exact case."""
import copy, hashlib, json, xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
ASSIGNMENT=json.loads((REPO/'inputs'/ROOT.name/'assignment.json').read_text())
AID=ASSIGNMENT['assignment_id']
CASE=AID+'__selected_near_side_crosswalk'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def put(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def channel(name,unit,method):
    return {'name':name,'unit':unit,'sampling_rate_hz':20,'method':method,'time_window':'entire original 25-second approach and turn','reference_frame':'original CARLA world XY and frame/time','uncertainty':'20 Hz sampling; native geometry and physical visibility require local review'}
def make_scene():
    source=REPO/'references/accepted-sources/C111325/scene-stop257-v1.xodr'
    tree=ET.parse(source);root=tree.getroot()
    root.find('header').set('name','C331230-near-side-crosswalk-v1')
    for road in root.findall('road'):
        road.find('objects').clear()
        signals=road.find('signals')
        for signal in list(signals):
            if signal.attrib['id']!='2001':signals.remove(signal)
    ET.indent(tree,space='  ');tree.write(ROOT/'scene.xodr',encoding='unicode',xml_declaration=True)
def main():
    make_scene()
    desc={'channels':[channel('kin.speed','m/s','native subject velocity'),channel('governing_sign','structured','native approach stop-sign inventory and original camera source'),channel('crosswalk_geometry','structured','physical near-side crosswalk tile vertices and original pixels'),channel('stopping_motion','structured','original full-body front, speed, brake and reference ordering')],'context_inputs':[],'limitations':['Original sign/crosswalk pixels and exact Native geometry require GPU review.','Minimum sampled speed is not a statutory full-stop verdict.']}
    case={'case_id':CASE,'target_law_id':ASSIGNMENT['law_id'],'target_type':'boundary_probe','rationale':'Exact near-side crosswalk branch; physical crosswalk tiles and governing West stop sign precede intersection entry.','variable_assignments':{'approach_speed_mps':{'value':5.0,'unit':'m/s','kind':'controller'}},'unresolved_judgment_calls':['Native sign governance and crosswalk pixels require original-frame review.','No invented stop epsilon or duration defines a legal full stop.'],'recording_description':desc}
    proposal={'cell_id':ASSIGNMENT['cell_id'],'actor':ASSIGNMENT['actor'],'status':'draft','sweep_specs':[],'cases':[case]}
    put(ROOT/'proposals/cases.json',proposal)
    config={'case':case,'case_id':CASE,'selected_case_id':CASE,'supported_case_ids':[CASE],'cell_id':ASSIGNMENT['cell_id'],'law_id':ASSIGNMENT['law_id'],'actor':ASSIGNMENT['actor'],'required_atoms':['kin.speed'],'source_packets':[],'duration_s':25,'camera':{'width':960,'height':540,'fov_deg':90},'recording_description':desc,'stop_control':{'stop_sign_id':'2001','governing_approach_road_id':1,'selected_branch':'near_side_crosswalk','crosswalk_upstream_x_m':-8.45,'crosswalk_downstream_x_m':-7.05,'marked_stopline_present':False,'near_side_of_intersection':True,'intersection_upstream_x_m':-7.0},'public_way_road_ids':[1,2,3,4,11,12],'authored_test_context':{'core_assumptions':[['asm.public_highway',True]]}}
    put(ROOT/'config.json',config)
    dispositions=[
      {'requirement':'Identified driver approaches an intersection indicated by a governing stop sign','source':'NRS 484A.450(2); activation','status':'selected_required','evidence_or_gap':'Exact West sign is authored in OpenDRIVE and Native landmark inventory is required; original-frame governance needs GPU review.'},
      {'requirement':'A near-side crosswalk exists and is the selected first stopping reference','source':'NRS 484A.450(2); selected branch','status':'selected_required','evidence_or_gap':'Physical crosswalk tile geometry is authored and Native body vertices/pixels are required; stop line is absent.'},
      {'requirement':'Stop before entering the near-side crosswalk and before entering the intersection','source':'NRS 484A.450(2); duty and ordering','status':'selected_required','evidence_or_gap':'Original speed, brake and full-body front distances from crosswalk/intersection are measured; legal full-stop judgment remains review.'},
      {'requirement':'If no crosswalk, use marked stop line or nearest view point','source':'NRS 484A.450(2); alternative reference branches','status':'alternative_pending','evidence_or_gap':'No-crosswalk alternatives are not selected; not used to replace the near-side crosswalk.'}
    ]
    term_channels={'dev.stop_sign':['governing_sign'],'dev.governs':['governing_sign'],'st.lane_enters':['crosswalk_geometry'],'drv.approaching':['stopping_motion'],'st.crosswalk':['crosswalk_geometry'],'st.stop_line':['crosswalk_geometry'],'st.intersection':['crosswalk_geometry'],'st.sight_distance':['governing_sign'],'rel.visible':['governing_sign'],'drv.stopped':['stopping_motion'],'drv.crossing_line':['stopping_motion'],'drv.entering_intersection':['stopping_motion']}
    mapping={t['term']:{'evidence':'Saved '+', '.join(term_channels[t['term']])+'; sight-distance/visibility terms are prompts for the unselected no-crosswalk alternative and remain unresolved','channels':term_channels[t['term']],'source_refs':['inputs/'+AID+'/assignment.json']} for t in ASSIGNMENT['source_observation_terms']}
    sources=[{'path':'inputs/'+AID+'/assignment.json','sha256':sha(REPO/'inputs'/AID/'assignment.json')},{'path':'references/accepted-sources/C111325/scene-stop257-v1.xodr','sha256':sha(REPO/'references/accepted-sources/C111325/scene-stop257-v1.xodr')},{'path':'examples/intersection/native/stop257_reference_markings_geometry_v2.py','sha256':sha(REPO/'examples/intersection/native/stop257_reference_markings_geometry_v2.py')}]
    plan={'assignment_id':AID,'actor':ASSIGNMENT['actor'],'cell_id':ASSIGNMENT['cell_id'],'law_id':ASSIGNMENT['law_id'],'selected_branch':ASSIGNMENT['branch'],'requirement_dispositions':dispositions,'cases':[{'case_id':CASE,'target_law_id':ASSIGNMENT['law_id']}],'comparisons':[],'observations':[{'name':c['name'],'mandatory':True} for c in desc['channels']],'sources':sources,'existing_evidence':ASSIGNMENT['existing_evidence'],'runtime_uncertainties':['No CARLA run performed; native route, full body motion, camera visibility and physical public-way context unverified.'],'source_observation_mapping':mapping}
    put(ROOT/'case-plan.json',plan)
    methods=['stop_sign_context','crosswalk_reference','stopping_sequence']
    outputs=['governing_stop_sign','near_side_crosswalk_reference','observed_stop_before_crosswalk']
    inputs=[['stop_control.json'],['stop_control.json'],['stop_control.json','stop_history.jsonl']]
    kinds=['sourced_context','sourced_context','measured']
    contract={'format':'worker-measurement-contract-v1','requirements':[{'disposition_index':i,'requirement':d['requirement'],'source':d['source'],'output_key':outputs[i],'method':methods[i],'kind':kinds[i],'value_type':'object','inputs':inputs[i]} for i,d in enumerate(dispositions) if d['status']=='selected_required'],'negative':{'remove':['stop_history.jsonl'],'error_contains':'Missing required source: stop_history.jsonl'}}
    put(ROOT/'measurement-contract.json',contract)
    put(ROOT/'stop_control.json',config['stop_control'])
    fixture=[
      {'frame':21714,'time_s':.05,'ego_body_xy_m':[[-15,.6],[-15,2.8],[-11,.6],[-11,2.8]],'ego_speed_mps':3.0,'applied_brake':.3,'native_crosswalk_tile_count':80},
      {'frame':21715,'time_s':.1,'ego_body_xy_m':[[-14,.6],[-14,2.8],[-10,.6],[-10,2.8]],'ego_speed_mps':0.0,'applied_brake':1.0,'native_crosswalk_tile_count':80},
      {'frame':21716,'time_s':.15,'ego_body_xy_m':[[-14,.6],[-14,2.8],[-10,.6],[-10,2.8]],'ego_speed_mps':0.0,'applied_brake':1.0,'native_crosswalk_tile_count':80},
    ]
    (ROOT/'stop_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in fixture))
    additions=[{'path':n,'source':'work/'+AID+'/'+n,'sha256':sha(ROOT/n)} for n in ('stop_control.json','stop_history.jsonl')]
    recipe={'format':'worker-fixture-recipe-v1','base':'runtime/main-pipeline-v1/fixtures/retained-speed','remove':['case.json','config.json','result.json'],'additions':additions}
    put(ROOT/'fixture-recipe.json',recipe)
    files=[]
    for name in ('config.json','runner.py','analyze.py','crosswalk_markings.py','scene.xodr','tests/test_case.py'):
        files.append({'path':name,'content':(ROOT/name).read_text()})
    construction={'case_id':CASE,'cell_id':ASSIGNMENT['cell_id'],'actor':ASSIGNMENT['actor'],'entrypoint':'runner.py','files':files,'measurement_plan':{'selected_requirement_contract':'measurement-contract.json','physical_acceptance':False},'recording_description':desc,'static_checks':['connected OpenDRIVE left-turn arc','opposing traffic lanes','camera resolution','complete planned channels'],'termination_rules':['25 seconds or explicit native failure; retain source and restore world'],'mechanisms':['native VehicleControl steering along curved junction','PipelineCapture original source channels','FrameMap and original RGB FFV1 video']}
    put(ROOT/'construction.json',construction)
    manifest={'format':'worker-execution-manifest-v1','assignment_id':AID,'runtime_manifest_sha256':sha(REPO/'runtime/main-pipeline-v1/SOURCE-MANIFEST.json'),'cases':[{'case_id':CASE,'kind':'capability','construction':'construction.json','construction_sha256':sha(ROOT/'construction.json'),'measurement_procedure':{'entrypoint':'analyze.py','output_schema':'analysis-report.json'},'measurement_contract':'measurement-contract.json','fixture_recipe':'work/'+AID+'/fixture-recipe.json','native_handoff':{'python_env_var':'CARLA_PYTHON','host_env_var':'CARLA_HOST','port_env_var':'CARLA_PORT'},'acquisition':{c['name']:{'entrypoint':'runner.py','method':c['method'],'evidence':'original frame capture and saved finalizer'} for c in desc['channels']}}]}
    put(ROOT/'execution-manifest.json',manifest)
if __name__=='__main__':main()
