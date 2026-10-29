"""Deterministic local construction for one assigned exact case."""
import copy, hashlib, json, xml.etree.ElementTree as ET
from pathlib import Path
ROOT=Path(__file__).resolve().parent
REPO=ROOT.parents[1]
ASSIGNMENT=json.loads((REPO/'inputs'/ROOT.name/'assignment.json').read_text())
AID=ASSIGNMENT['assignment_id']
CASE=AID+'__selected_caravan_spacing'
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def put(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(obj,indent=2,ensure_ascii=False)+'\n')
def channel(name,unit,method):
    return {'name':name,'unit':unit,'sampling_rate_hz':20,'method':method,'time_window':'entire original 25-second approach and turn','reference_frame':'original CARLA world XY and frame/time','uncertainty':'20 Hz sampling; native geometry and physical visibility require local review'}
def make_scene():
    source=REPO/'references/accepted-sources/C228508/scene-caravan-v1.xodr'
    tree=ET.parse(source);tree.getroot().find('header').set('name','C160013-caravan-spacing-v1')
    ET.indent(tree,space='  ');tree.write(ROOT/'scene.xodr',encoding='unicode',xml_declaration=True)
def main():
    make_scene()
    desc={'channels':[channel('kin.speed','m/s','native following actor velocity'),channel('caravan_roles','structured','authored caravan purpose and outside-business-district context with actor roles'),channel('surface_gap','structured','original full-body lead/follow surface gaps'),channel('entrant_trajectory','structured','native entrant body trajectory and gap occupation')],'context_inputs':[],'limitations':['Caravan shared purpose and outside-business-district premise are authored context.','Gap occupation alone does not resolve the without-danger legal standard.']}
    case={'case_id':CASE,'target_law_id':ASSIGNMENT['law_id'],'target_type':'boundary_probe','rationale':'Exact selected caravan branch; follow and lead motor vehicles retain a full-body space while another vehicle enters it.','variable_assignments':{'approach_speed_mps':{'value':5.0,'unit':'m/s','kind':'controller'}},'unresolved_judgment_calls':['Sufficient space without danger is not reduced to a gap cutoff.','Actual caravan purpose, entrant movement and camera pixels require GPU review.'],'recording_description':desc}
    proposal={'cell_id':ASSIGNMENT['cell_id'],'actor':ASSIGNMENT['actor'],'status':'draft','sweep_specs':[],'cases':[case]}
    put(ROOT/'proposals/cases.json',proposal)
    config={'case':case,'case_id':CASE,'selected_case_id':CASE,'supported_case_ids':[CASE],'cell_id':ASSIGNMENT['cell_id'],'law_id':ASSIGNMENT['law_id'],'actor':ASSIGNMENT['actor'],'required_atoms':['kin.speed'],'source_packets':[],'duration_s':25,'camera':{'width':960,'height':540,'fov_deg':90},'recording_description':desc,'caravan_context':{'highway_id':1,'outside_business_district_basis':'synthetic authored Nevada non-business district premise','caravan_purpose':'synthetic shared route and purpose, subject to local review','vehicle_roles':['follow','lead','entrant']},'public_way_road_ids':[1],'authored_test_context':{'core_assumptions':[['asm.public_highway',True]]}}
    put(ROOT/'config.json',config)
    dispositions=[
      {'requirement':'Motor vehicles are driven in a caravan or motorcade on a highway outside a business district','source':'NRS 484B.127(3); selected branch and activation','status':'selected_required','evidence_or_gap':'Authored shared-purpose, public highway and non-business-district context plus native actor roles; legal class needs local confirmation.'},
      {'requirement':'Allow space between successive caravan vehicles throughout travel','source':'NRS 484B.127(3); spacing duty','status':'selected_required','evidence_or_gap':'Original full-body lead/follow signed surface gap is sampled throughout the run.'},
      {'requirement':'Space enables another vehicle to enter and occupy it without danger','source':'NRS 484B.127(3); statutory consequence','status':'selected_required','evidence_or_gap':'Original entrant body trajectory and rear/front clearance are measured; without-danger conclusion remains legal review.'}
    ]
    term_channels={'drv.following':['surface_gap'],'rel.surface_gap':['surface_gap'],'drv.queue_behind':['caravan_roles','surface_gap'],'rel.same_direction':['caravan_roles'],'ru.trailer_or_combination':['caravan_roles'],'drv.lane_change_feasible':['entrant_trajectory'],'kin.speed':['kin.speed']}
    mapping={t['term']:{'evidence':'Saved '+', '.join(term_channels[t['term']])+' from original actors or authored context; no legal danger threshold','channels':term_channels[t['term']],'source_refs':['inputs/'+AID+'/assignment.json']} for t in ASSIGNMENT['source_observation_terms']}
    sources=[{'path':'inputs/'+AID+'/assignment.json','sha256':sha(REPO/'inputs'/AID/'assignment.json')},{'path':'references/accepted-sources/C228508/scene-caravan-v1.xodr','sha256':sha(REPO/'references/accepted-sources/C228508/scene-caravan-v1.xodr')},{'path':'references/accepted-sources/C228508/caravan_controller_v3.py','sha256':sha(REPO/'references/accepted-sources/C228508/caravan_controller_v3.py')},{'path':'references/accepted-sources/C228508/caravan_entrant_controller_v1.py','sha256':sha(REPO/'references/accepted-sources/C228508/caravan_entrant_controller_v1.py')}]
    plan={'assignment_id':AID,'actor':ASSIGNMENT['actor'],'cell_id':ASSIGNMENT['cell_id'],'law_id':ASSIGNMENT['law_id'],'selected_branch':ASSIGNMENT['branch'],'requirement_dispositions':dispositions,'cases':[{'case_id':CASE,'target_law_id':ASSIGNMENT['law_id']}],'comparisons':[],'observations':[{'name':c['name'],'mandatory':True} for c in desc['channels']],'sources':sources,'existing_evidence':ASSIGNMENT['existing_evidence'],'runtime_uncertainties':['No CARLA run performed; native route, full body motion, camera visibility and physical public-way context unverified.'],'source_observation_mapping':mapping}
    put(ROOT/'case-plan.json',plan)
    methods=['caravan_context','intervehicle_gap','entrant_occupancy']
    outputs=['caravan_outside_district_context','caravan_full_body_spacing','entrant_gap_occupation']
    inputs=[['caravan_context.json'],['caravan_history.jsonl'],['caravan_history.jsonl']]
    kinds=['sourced_context','measured','measured']
    contract={'format':'worker-measurement-contract-v1','requirements':[{'disposition_index':i,'requirement':d['requirement'],'source':d['source'],'output_key':outputs[i],'method':methods[i],'kind':kinds[i],'value_type':'object','inputs':inputs[i]} for i,d in enumerate(dispositions)],'negative':{'remove':['caravan_history.jsonl'],'error_contains':'Missing required source: caravan_history.jsonl'}}
    put(ROOT/'measurement-contract.json',contract)
    put(ROOT/'caravan_context.json',config['caravan_context'])
    fixture=[
      {'frame':21714,'time_s':.05,'follow_body_xy_m':[[0,1],[0,3],[4,1],[4,3]],'lead_body_xy_m':[[30,1],[30,3],[34,1],[34,3]],'entrant_body_xy_m':[[13,5],[13,7],[17,5],[17,7]],'follow_speed_mps':5,'lead_speed_mps':5,'entrant_speed_mps':5},
      {'frame':21715,'time_s':.1,'follow_body_xy_m':[[1,1],[1,3],[5,1],[5,3]],'lead_body_xy_m':[[31,1],[31,3],[35,1],[35,3]],'entrant_body_xy_m':[[14,3],[14,5],[18,3],[18,5]],'follow_speed_mps':5,'lead_speed_mps':5,'entrant_speed_mps':5},
      {'frame':21716,'time_s':.15,'follow_body_xy_m':[[2,1],[2,3],[6,1],[6,3]],'lead_body_xy_m':[[32,1],[32,3],[36,1],[36,3]],'entrant_body_xy_m':[[15,1],[15,3],[19,1],[19,3]],'follow_speed_mps':5,'lead_speed_mps':5,'entrant_speed_mps':5},
    ]
    (ROOT/'caravan_history.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in fixture))
    additions=[{'path':n,'source':'work/'+AID+'/'+n,'sha256':sha(ROOT/n)} for n in ('caravan_context.json','caravan_history.jsonl')]
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
