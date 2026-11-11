"""Build current unselected C111662 packages from retained source-pinned constructions."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[1]
AID = ROOT.name
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
CASES = ('reference', 'contrast', 'divided_reference', 'divided_opening')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False)+'\n')


def source(case, candidate):
    if case.startswith('divided_'):
        return HERE/'divided-opening'/'runtime-drafts'/case/candidate/'construction.json'
    return HERE/'runtime-drafts'/case/candidate/'construction.json'


def build():
    batch = json.loads((REPO/'batch.json').read_text())
    plan = json.loads((ROOT/'case-plan.json').read_text())
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': AID, 'status': 'draft_not_selected',
                'runtime_manifest_sha256': batch['runtime']['source_manifest_sha256'],
                'source_branch': 'business_district_u_turn', 'cases': []}
    proposals = {'cell_id': 'C111662', 'actor': 'motor_vehicle_driver',
                 'status': 'unselected_cpu_draft', 'cases': []}
    channels = [{'name': name, 'unit': unit, 'sampling_rate_hz': 20,
                 'method': 'saved Native body/frame join', 'time_window': '800 frames',
                 'reference_frame': 'authored OpenDRIVE coordinates',
                 'uncertainty': '50 ms frame bracket; district/exception applicability unverified'}
                for name, unit in (('ego_pose','structured'), ('ego_speed','m/s'),
                                   ('u_turn_at_intersection_or_opening','bool'))]
    recording = {'channels': channels, 'context_inputs': [
        {'name': 'authored_road', 'unit': 'structured', 'method': 'source-hashed OpenDRIVE'},
        {'name': 'authored_request', 'unit': 'structured', 'method': 'source-hashed requested-tracks.jsonl'},
        {'name': 'authored_frontage', 'unit': 'structured', 'method': 'source-hashed frontage plan and Native geometry readback pending'}],
        'limitations': ['Original district designation, physical U-turn, and exception status unverified']}
    code = (HERE/'finalize_current.py').read_text()
    for case in CASES:
        case_id = AID+'__'+case
        disposition_ids = [i for i, row in enumerate(plan['requirement_dispositions'])
                           if case_id in row.get('case_ids', [])]
        keys = (('turn_crossing_x_m','measure_turn_crossing','number'),
                ('authored_exception_location','measure_exception_location','boolean'))
        if case.startswith('divided_'):
            keys = (('authored_divided_opening','measure_divided_opening','boolean'),)
        assert len(disposition_ids) == len(keys)
        requirements = []
        for index, (key, method, value_type) in zip(disposition_ids, keys):
            row = plan['requirement_dispositions'][index]
            requirements.append({'disposition_index': index, 'requirement': row['requirement'],
                                 'source': row['source'], 'output_key': key, 'method': method,
                                 'value_type': value_type, 'kind': 'measured', 'inputs': ['raw.json']})
        contract_rel = f'native/measurement-contracts-current/{case}.json'
        write(ROOT/contract_rel, {'format': 'worker-measurement-contract', 'case_id': case_id,
                                 'requirements': requirements,
                                 'negative': {'remove': ['raw.json'],
                                              'error_contains': 'Missing required source: raw.json'},
                                 'uncertainty': {'frame_bracket_s': .05,
                                                 'physical_and_legal_status': 'unverified'}})
        entry = {'case_id': case_id, 'kind': 'draft_not_selected', 'candidates': [],
                 'measurement_contract': contract_rel,
                 'measurement_procedure': {'entrypoint': 'finalize_current.py',
                                           'output_schema': 'c111662-current-saved-diagnostic-v1'},
                 'candidate_risk': {'status': 'physical', 'reason':
                                    'Requested U-turn may miss crossing, median opening, or four-camera visibility in Native capture'}}
        recipe = ROOT/f'update015-current-{case}-recipe.json'
        if recipe.is_file():
            entry['fixture_recipe'] = recipe.relative_to(REPO).as_posix()
        original = None
        for candidate in CANDIDATES:
            construction = json.loads(source(case,candidate).read_text())
            files = construction['files']
            capture_paths = {f'work/{AID}/native/capture.py', f'work/{AID}/native/capture_divided.py'}
            for item in files:
                if item['path'] in capture_paths:
                    item['content'] = (HERE/Path(item['path']).name).read_text()
            frontage_code = (HERE/'frontage.py').read_text()
            files.extend([
                {'path':'frontage.py','content':frontage_code},
                {'path':f'work/{AID}/native/frontage.py','content':frontage_code},
                {'path':'frontage-plan.json','content':(HERE/'frontage-plan.json').read_text()},
                {'path':'tests/test_frontage.py','content':(HERE/'tests/test_frontage.py').read_text()},
            ])
            road_name = 'divided-highway.xodr' if case.startswith('divided_') else 'district-crossroads.xodr'
            files.append({'path':'road.xodr', 'content':next(item['content'] for item in files if item['path']==road_name)})
            cfg_entry = next(item for item in files if item['path']=='config.json')
            config = json.loads(cfg_entry['content'])
            if original is None: original = config
            config.update({'selected_case_id':case_id,'cell_id':'C111662',
                           'law_id':'NRS-484B-403-3','actor':'motor_vehicle_driver',
                           'case_suffix':case,'duration_s':40,'required_atoms':[],
                           'source_packets':[], 'cameras':['overview','approach','reference_corner','driver_reference'],
                           'case': {'case_id':case_id},'physical_success_claimed':False})
            cfg_entry['content'] = json.dumps(config,indent=2)+'\n'
            files.append({'path':'finalize_current.py','content':code})
            if case.startswith('divided_'):
                files.append({'path':f'work/{AID}/native/saved.py', 'content':(HERE/'saved.py').read_text()})
                files.append({'path':f'work/{AID}/native/saved_divided.py', 'content':(HERE/'saved_divided.py').read_text()})
            construction['files'] = files
            construction['recording_description'] = recording
            construction['static_checks'] = ['800-frame source-bound request identity',
                                             'synthetic body/trace/video frame join']
            construction['termination_rules'] = ['retain original acquisition', 'require 800 synchronized frames']
            construction['mechanisms'] = ['source-pinned six-lane U-turn request',
                                          'four synchronized original camera streams']
            target_rel = f'native/package-current/{case}/{candidate}/construction.json'
            target = ROOT/target_rel
            write(target,construction)
            ref = {'id':candidate,'construction':target_rel,'construction_sha256':sha(target)}
            if candidate=='primary':
                entry.update({key:ref[key] for key in ('construction','construction_sha256')})
            else:
                changed = [key for key in ('requested_approach_speed_mps','pre_turn_dwell_s',
                                            'camera_policy','requested_turn_center_x_m')
                           if config.get(key)!=original.get(key)]
                ref['changed_knobs'] = changed or ['requested-tracks.jsonl']
                ref['trigger'] = {'source': 'saved Native body and four-camera frame join',
                                  'metric': {'fallback1':'measured turn speed',
                                             'fallback2':'stationary pre-turn frames',
                                             'fallback3':'camera capture coverage'}[candidate],
                                  'failure_condition': 'physical target or visibility below reviewed threshold'}
                entry['candidates'].append(ref)
        manifest['cases'].append(entry)
        proposals['cases'].append({'case_id':case_id,'target_law_id':'NRS-484B-403-3',
                                   'target_type':'attempt','recording_description':recording})
    write(ROOT/'draft-execution-manifest.json',manifest)
    write(ROOT/'proposals/cases.json',proposals)
    return {'cases': len(CASES), 'constructions': 16,
            'manifest_sha256': sha(ROOT/'draft-execution-manifest.json')}


if __name__=='__main__':
    print(json.dumps(build(),sort_keys=True))
