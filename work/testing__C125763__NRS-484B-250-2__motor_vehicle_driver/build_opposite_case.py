"""Build an isolated synthetic opposite-direction left-turn CPU case."""
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[1]
SUFFIX='yield_opposite_left_turn'
CASE=HERE.name+'__'+SUFFIX
PRIMARY=HERE.name+'__yield_ego_left_near_time'
OUT=HERE/'cases'/SUFFIX


def serialized(value):
    return json.dumps(value,indent=2,allow_nan=False)+'\n'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def embedded(files,path):
    return next(row for row in files if row['path']==path)


def build():
    OUT.mkdir(parents=True,exist_ok=True)
    construction=copy.deepcopy(json.loads(
        (HERE/'cases/yield_ego_left_near_time/construction.json').read_text()))
    construction['case_id']=CASE
    files=construction['files']
    site=json.loads(embedded(files,'site.json')['content'])
    site['approach_relation']='opposite_directions'
    site['other_left_turn_intended']=True
    site['approaches']['other'].update(
        highway_id='EW',lane_id=2,road_id=1,forward_xy=[-1,0],
        route_xy_m=[[30,0],[15,0],[15,-15]],spawn_pose=[30,0,0,180])
    source=embedded(files,'review/crossing_geometry_source.json')
    document=json.loads(source['content'])
    document['reviewed_site_fields']['approaches']=site['approaches']
    source['content']=serialized(document)
    site['source_documents']['crossing_geometry_source']['sha256']=hashlib.sha256(
        source['content'].encode()).hexdigest()
    embedded(files,'site.json')['content']=serialized(site)
    config=json.loads(embedded(files,'config.json')['content'])
    config['selected_case_id']=CASE
    config['site_packet']['sha256']=hashlib.sha256(
        embedded(files,'site.json')['content'].encode()).hexdigest()
    embedded(files,'config.json')['content']=serialized(config)
    test=embedded(files,'tests/test_bundle.py')
    test['content']=test['content'].replace('yield_ego_left_near_time',SUFFIX)
    (OUT/'construction.json').write_text(serialized(construction))

    diagnostic=copy.deepcopy(json.loads((HERE/'diagnostic.json').read_text()))
    context=json.loads(diagnostic['files']['junction_context.json'])
    context.update(other_highway_id='EW',other_road_id=1,
                   other_approach_forward_xy=[-1,0],
                   approach_relation='opposite_directions',
                   turn_intent_source='controller_history.jsonl')
    diagnostic['files']['junction_context.json']=serialized(context)
    history=[json.loads(line) for line in diagnostic['files']['crossing_history.jsonl'].splitlines()]
    for row in history:
        row['other_left_turn_intended']=True
        row['other']['road_id']=1
    for row in history[:30]:
        row['other']['body_vertices_xy_m']=[[x+30,y] for x,y in
                                             row['other']['body_vertices_xy_m']]
    diagnostic['files']['crossing_history.jsonl']=''.join(
        json.dumps(row,allow_nan=False)+'\n' for row in history)
    controls=[json.loads(line) for line in diagnostic['files']['controller_history.jsonl'].splitlines()]
    for row in controls:row['other_left_turn_intended']=True
    diagnostic['files']['controller_history.jsonl']=''.join(
        json.dumps(row,allow_nan=False)+'\n' for row in controls)
    capture=json.loads(diagnostic['files']['capture/manifest.json'])
    capture['case_id']=CASE
    diagnostic['files']['capture/manifest.json']=serialized(capture)
    source_path=OUT/'diagnostic.json';source_path.write_text(serialized(diagnostic))
    relative=str(source_path.relative_to(REPO));checksum=digest(source_path)
    recipe={'format':'worker-fixture-recipe',
            'sources':[{'path':'diagnostic-input.json','source':relative,'sha256':checksum}],
            'generator':{'source':relative,'sha256':checksum}}
    (OUT/'diagnostic-recipe.json').write_text(serialized(recipe))
    manifest={'format':'worker-execution-manifest','assignment_id':HERE.name,
              'runtime_manifest_sha256':digest(REPO/'runtime/SOURCE-MANIFEST.json'),
              'status':'isolated_partial_opposite_diagnostic',
              'cases':[{'case_id':CASE,'kind':'delivery',
                        'construction':str((OUT/'construction.json').relative_to(HERE)),
                        'construction_sha256':digest(OUT/'construction.json'),
                        'measurement_procedure':{'entrypoint':'finalizer.py'},
                        'measurement_contract':'measurement-contract.json',
                        'fixture_recipe':str((OUT/'diagnostic-recipe.json').relative_to(REPO)),
                        'native_handoff':{'python_env_var':'CARLA_PYTHON',
                                          'host_env_var':'CARLA_HOST',
                                          'port_env_var':'CARLA_PORT'}}]}
    (HERE/'opposite-candidate-manifest.json').write_text(serialized(manifest))
    plan_path=HERE/'case-plan.json';plan=json.loads(plan_path.read_text())
    for row in plan['requirement_dispositions']:
        if row['status']=='selected_required' and PRIMARY in row.get('case_ids',[]):
            row['case_ids']=list(dict.fromkeys(row['case_ids']+[CASE]))
    plan_path.write_text(serialized(plan))
    proposals_path=HERE/'proposals/cases.json'
    proposals=json.loads(proposals_path.read_text())
    proposal=copy.deepcopy(next(c for c in proposals['cases'] if c['case_id']==PRIMARY))
    proposal['case_id']=CASE
    proposal['rationale']='Synthetic same-highway opposite approach with original controller left-turn intent; physical site unverified'
    proposal['probe']['target_value_or_branch']=SUFFIX
    proposal['deliberate_differences']=['Other approach reverses ego direction, shares highway and intends left turn']
    proposals['cases']=[c for c in proposals['cases'] if c['case_id']!=CASE]+[proposal]
    proposals_path.write_text(serialized(proposals))
    return manifest


if __name__=='__main__':
    print(serialized(build()),end='')
