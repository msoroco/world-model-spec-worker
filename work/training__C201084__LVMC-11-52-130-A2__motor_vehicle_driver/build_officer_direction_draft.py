"""Bind retained pedestrian actor samples to an exact diagnostic CPU bundle."""
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CASE=HERE.name+'__officer_direction'
CAMERAS=('overview','approach','reference_corner','driver_reference')
MODULES=('officer_direction_entrypoint.py','officer_direction_runner.py',
         'officer_direction_capture.py','officer_direction_probe.py',
         'officer_direction_finalize.py','native_runner.py','native_capture.py',
         'native_controller.py','native_survey.py','fire_lane_survey.py',
         'source_measurement.py','native_finalize.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def build():
    base=HERE/'fixtures/reference-sources'
    officer=HERE/'fixtures/officer-direction-sources'
    frames=[json.loads(line) for line in (base/'video_frames.jsonl').read_text().splitlines()]
    if len(frames)!=600:
        raise ValueError('Expected 600 diagnostic source frames')
    readback={'actor_id':501,'type_id':'walker.pedestrian.001',
              'position_xy_m':[11,1],
              'source_kind':'synthetic_native_sample',
              'police_authority_verified':False,
              'direction_applicability_verified':False,
              'statutory_necessity_verified':False}
    write(officer/'officer-survey-readback.json',readback)
    rows=[]
    for i,frame in enumerate(frames):
        rows.append({'frame':frame['carla_frame'],'video_frame':i,
            'officer_actor_id':501,'officer_type_id':'walker.pedestrian.001',
            'pose_xyz_yaw_deg':[11,1,0,90],
            'velocity_xyz_mps':[0,0,0],
            'police_authority_verified':False,
            'direction_applicability_verified':False,
            'statutory_necessity_verified':False,
            'source_kind':'synthetic_native_sample'})
    (officer/'police-officer-actor.jsonl').write_text(
        ''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))
    capture_manifest=json.loads((base/'capture/manifest.json').read_text())
    capture_manifest['case_id']=CASE
    capture_manifest['sources'].update({name:sha(officer/name) for name in
        ('officer-survey-readback.json','police-officer-actor.jsonl')})
    write(officer/'capture/manifest.json',capture_manifest)

    recipe=copy.deepcopy(json.loads((HERE/'draft-reference-diagnostic-recipe.json').read_text()))
    for source in recipe['sources']:
        if source['path']=='capture/manifest.json':
            source['source']=str((officer/'capture/manifest.json').relative_to(ROOT))
            source['sha256']=sha(officer/'capture/manifest.json')
    for name in ('officer-survey-readback.json','police-officer-actor.jsonl'):
        recipe['sources'].append({'path':name,
            'source':str((officer/name).relative_to(ROOT)),
            'sha256':sha(officer/name)})
    write(HERE/'draft-officer-direction-diagnostic-recipe.json',recipe)

    construction=copy.deepcopy(json.loads((HERE/'draft-reference-construction.json').read_text()))
    config_file=next(row for row in construction['files'] if row['path']=='config.json')
    config=json.loads(config_file['content'])
    config.update(case_id=CASE,selected_case_id=CASE,
                  case_suffix='officer_direction',candidate_id='primary',
                  police_authority_verified=False,
                  direction_applicability_verified=False,
                  statutory_necessity_verified=False)
    config['recording_description']['context_inputs'].append({
        'name':'officer_direction_context','unit':'structured',
        'method':'saved original pedestrian pose and frame-map join',
        'reference_frame':'original CARLA actor and world frame',
        'uncertainty':'Police authority, direction applicability and legal necessity require original review'})
    config['recording_description']['limitations'].append(
        'Pedestrian pose alone does not establish police authority or a direction to stop in the fire lane')
    config_file['content']=json.dumps(config,indent=2,sort_keys=True)+'\n'
    construction['case_id']=CASE
    construction['entrypoint']='officer_direction_entrypoint.py'
    construction['status']='selected_cpu_preparation_incomplete'
    construction['files']=[{'path':name,'content':(HERE/name).read_text()}
                           for name in MODULES]+[config_file,{
        'path':'tests/test_bundle.py','content':
        'import unittest\nimport officer_direction_entrypoint as entry\n'
        'class BundleTest(unittest.TestCase):\n'
        ' def test_exact(self):\n'
        '  result=entry.check()\n'
        '  self.assertEqual(result["frames"],600)\n'
        '  self.assertEqual(len(result["source_cameras"]),4)\n'
        '  self.assertFalse(result["physical_acceptance_claimed"])\n'}]
    construction['mechanisms']+=['surveyed live pedestrian actor identity',
        'frame-synchronized original pedestrian pose and velocity source',
        'saved-only actor identity, pose, and frame join']
    construction['raw_sources']+=['officer-survey-readback.json',
                                  'police-officer-actor.jsonl']
    construction['recording_description']=config['recording_description']
    for disposition in construction['measurement_plan']['requirements']:
        if (CASE.replace('__officer_direction','__reference') in disposition.get('case_ids',[]) and
                CASE not in disposition['case_ids']):
            disposition['case_ids'].append(CASE)
    for entry in construction['measurement_plan']['per_case_contracts']:
        entry['case_id']=CASE
        entry['observations'] += [{'name':'officer_direction_context',
            'unit':'structured','mandatory':True,
            'purpose':'Retain source-bound actor pose without a police-authority or legal verdict'}]
    write(HERE/'draft-officer-direction-construction.json',construction)

    contract=copy.deepcopy(json.loads((HERE/'draft-reference-measurement-contract.json').read_text()))
    contract['case_id']=CASE
    contract['requirements'][0].update(
        method='measure_officer_direction_context',output_key='officer_direction_context',
        inputs=['officer-survey-readback.json','police-officer-actor.jsonl',
                'video_frames.jsonl'])
    contract['negative']={'remove':['police-officer-actor.jsonl'],
                          'error_contains':'Missing required source: police-officer-actor.jsonl'}
    write(HERE/'draft-officer-direction-measurement-contract.json',contract)
    manifest={'format':'worker-execution-manifest',
        'assignment_id':HERE.name,
        'runtime_manifest_sha256':sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json'),
        'status':'draft_primary_diagnostic',
        'cases':[{'case_id':CASE,
            'construction':'draft-officer-direction-construction.json',
            'construction_sha256':sha(HERE/'draft-officer-direction-construction.json'),
            'measurement_contract':'draft-officer-direction-measurement-contract.json',
            'fixture_recipe':str((HERE/'draft-officer-direction-diagnostic-recipe.json').relative_to(ROOT)),
            'measurement_procedure':{'entrypoint':'officer_direction_finalize.py',
                                     'source_only':True}}]}
    write(HERE/'draft-officer-direction-manifest.json',manifest)
    proposal_path=HERE/'proposals/cases.json'
    proposals=json.loads(proposal_path.read_text())
    proposal=next(row for row in json.loads((HERE/'case-plan.json').read_text())['cases']
                  if row['case_id']==CASE)
    proposal=copy.deepcopy(proposal)
    proposal['recording_description']=config['recording_description']
    proposal['variable_assignments']={}
    proposals['cases']=[row for row in proposals['cases'] if row['case_id']!=CASE]
    proposals['cases'].append(proposal)
    write(proposal_path,proposals)
    return {'case_id':CASE,
            'construction_sha256':sha(HERE/'draft-officer-direction-construction.json'),
            'manifest_sha256':sha(HERE/'draft-officer-direction-manifest.json'),
            'fixture_recipe_sha256':sha(HERE/'draft-officer-direction-diagnostic-recipe.json')}


if __name__=='__main__':
    print(json.dumps(build(),sort_keys=True))
