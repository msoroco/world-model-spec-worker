"""Bind the retained traffic-light source to an exact diagnostic CPU bundle."""
import copy
import hashlib
import json
from pathlib import Path

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
CASE=HERE.name+'__device_direction'
CAMERAS=('overview','approach','reference_corner','driver_reference')
MODULES=('device_direction_entrypoint.py','device_direction_runner.py',
         'device_direction_capture.py','device_direction_probe.py',
         'device_direction_finalize.py','native_runner.py','native_capture.py',
         'native_controller.py','native_survey.py','fire_lane_survey.py',
         'source_measurement.py','native_finalize.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def build():
    base=HERE/'fixtures/reference-sources'
    device=HERE/'fixtures/device-direction-sources'
    frames=[json.loads(line) for line in (base/'video_frames.jsonl').read_text().splitlines()]
    if len(frames)!=600:
        raise ValueError('Expected 600 diagnostic source frames')
    readback={'actor_id':203,'type_id':'traffic.traffic_light',
              'position_xy_m':[22,1],'road_id':17,'lane_id':-1,
              'source_kind':'synthetic_native_sample',
              'direction_applicability_verified':False,
              'statutory_necessity_verified':False}
    write(device/'device-survey-readback.json',readback)
    rows=[]
    for i,frame in enumerate(frames):
        rows.append({'frame':frame['carla_frame'],'video_frame':i,
            'device_actor_id':203,'device_type_id':'traffic.traffic_light',
            'device_state':'Red' if 200<=i<260 else 'Green',
            'device_pose_xyz_m':[22,1,0],
            'direction_applicability_verified':False,
            'statutory_necessity_verified':False,
            'source_kind':'synthetic_native_sample'})
    (device/'traffic-control-device.jsonl').write_text(
        ''.join(json.dumps(row,sort_keys=True)+'\n' for row in rows))
    capture_manifest=json.loads((base/'capture/manifest.json').read_text())
    capture_manifest['case_id']=CASE
    capture_manifest['sources'].update({name:sha(device/name) for name in
        ('device-survey-readback.json','traffic-control-device.jsonl')})
    write(device/'capture/manifest.json',capture_manifest)

    recipe=copy.deepcopy(json.loads((HERE/'draft-reference-diagnostic-recipe.json').read_text()))
    for source in recipe['sources']:
        if source['path']=='capture/manifest.json':
            source['source']=str((device/'capture/manifest.json').relative_to(ROOT))
            source['sha256']=sha(device/'capture/manifest.json')
    for name in ('device-survey-readback.json','traffic-control-device.jsonl'):
        recipe['sources'].append({'path':name,
            'source':str((device/name).relative_to(ROOT)),
            'sha256':sha(device/name)})
    write(HERE/'draft-device-direction-diagnostic-recipe.json',recipe)

    construction=copy.deepcopy(json.loads((HERE/'draft-reference-construction.json').read_text()))
    config_file=next(row for row in construction['files'] if row['path']=='config.json')
    config=json.loads(config_file['content'])
    config.update(case_id=CASE,selected_case_id=CASE,
                  case_suffix='device_direction',candidate_id='primary',
                  direction_applicability_verified=False,
                  statutory_necessity_verified=False)
    config['recording_description']['context_inputs'].append({
        'name':'device_direction_context','unit':'structured',
        'method':'saved traffic-control actor state and frame-map join',
        'reference_frame':'original CARLA actor and world frame',
        'uncertainty':'Device applicability and legal necessity require original review'})
    config['recording_description']['limitations'].append(
        'Traffic-light state alone does not establish a direction to stop in the fire lane')
    config_file['content']=json.dumps(config,indent=2,sort_keys=True)+'\n'
    construction['case_id']=CASE
    construction['entrypoint']='device_direction_entrypoint.py'
    construction['status']='selected_cpu_preparation_incomplete'
    construction['files']=[{'path':name,'content':(HERE/name).read_text()}
                           for name in MODULES]+[config_file,{
        'path':'tests/test_bundle.py','content':
        'import unittest\nimport device_direction_entrypoint as entry\n'
        'class BundleTest(unittest.TestCase):\n'
        ' def test_exact(self):\n'
        '  result=entry.check()\n'
        '  self.assertEqual(result["frames"],600)\n'
        '  self.assertEqual(len(result["source_cameras"]),4)\n'
        '  self.assertFalse(result["physical_acceptance_claimed"])\n'}]
    construction['mechanisms']+=['live traffic-light actor and same-road survey',
        'frame-synchronized original light-state source',
        'saved-only device identity, state, and frame join']
    construction['raw_sources']+=['device-survey-readback.json',
                                  'traffic-control-device.jsonl']
    construction['recording_description']=config['recording_description']
    for disposition in construction['measurement_plan']['requirements']:
        if (CASE.replace('__device_direction','__reference') in disposition.get('case_ids',[]) and
                CASE not in disposition['case_ids']):
            disposition['case_ids'].append(CASE)
    for entry in construction['measurement_plan']['per_case_contracts']:
        entry['case_id']=CASE
        entry['observations'] += [{'name':'device_direction_context',
            'unit':'structured','mandatory':True,
            'purpose':'Retain source-bound device state without a legal verdict'}]
    write(HERE/'draft-device-direction-construction.json',construction)

    contract=copy.deepcopy(json.loads((HERE/'draft-reference-measurement-contract.json').read_text()))
    contract['case_id']=CASE
    contract['requirements'][0].update(
        method='measure_device_direction_context',output_key='device_direction_context',
        inputs=['device-survey-readback.json','traffic-control-device.jsonl',
                'video_frames.jsonl'])
    contract['negative']={'remove':['traffic-control-device.jsonl'],
                          'error_contains':'Missing required source: traffic-control-device.jsonl'}
    write(HERE/'draft-device-direction-measurement-contract.json',contract)
    manifest={'format':'worker-execution-manifest',
        'assignment_id':HERE.name,
        'runtime_manifest_sha256':sha(ROOT/'runtime/pipeline/SOURCE-MANIFEST.json'),
        'status':'draft_primary_diagnostic',
        'cases':[{'case_id':CASE,
            'construction':'draft-device-direction-construction.json',
            'construction_sha256':sha(HERE/'draft-device-direction-construction.json'),
            'measurement_contract':'draft-device-direction-measurement-contract.json',
            'fixture_recipe':str((HERE/'draft-device-direction-diagnostic-recipe.json').relative_to(ROOT)),
            'measurement_procedure':{'entrypoint':'device_direction_finalize.py',
                                     'source_only':True}}]}
    write(HERE/'draft-device-direction-manifest.json',manifest)
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
            'construction_sha256':sha(HERE/'draft-device-direction-construction.json'),
            'manifest_sha256':sha(HERE/'draft-device-direction-manifest.json'),
            'fixture_recipe_sha256':sha(HERE/'draft-device-direction-diagnostic-recipe.json')}


if __name__=='__main__':
    print(json.dumps(build(),sort_keys=True))
