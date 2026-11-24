"""Construct the selected moving-then-stopped referral without 484B.607 duties."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
SUFFIX = 'stopped_referral'
CASE = AID + '__' + SUFFIX


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    manifest_path = HERE / 'current-execution-manifest.json'
    manifest = read(manifest_path)
    baseline = next(x for x in manifest['cases'] if x['case_id'].endswith('__controlled_1'))
    entry = copy.deepcopy(baseline)
    entry['case_id'] = CASE
    entry['candidate_risk']['reason'] = 'Moving vehicle must be observed stopping within 600 frames; driver and vehicle must remain separated under Native readback'
    entry['measurement_contract'] = 'current-contracts/' + SUFFIX + '.json'
    entry['fixture_recipe'] = 'work/' + AID + '/current-' + SUFFIX + '-recipe.json'
    for key in ('physical_preparation', 'offline', 'compatibility', 'negative',
                'saved_processing', 'post_capture', 'delivery_acceptance', 'acquisition'):
        entry.pop(key, None)
    for candidate in ['primary', *entry['candidates']]:
        cid = candidate if candidate == 'primary' else candidate['id']
        dest = entry if cid == 'primary' else candidate
        for key in ('offline', 'compatibility', 'negative', 'saved_processing'):
            dest.pop(key, None)
        original = read(HERE / 'current-bundles/controlled_1' / cid / 'construction.json')
        original['case_id'] = CASE
        original['recording_description']['limitations'].append('NRS 484B.607 exact duties are not supplied; measure stop and preserve referral without a verdict')
        original['measurement_plan']['stopped_referral_source'] = 'NRS 484B.267(2)(f)(2)'
        for file in original['files']:
            if file['path'] == 'config.json':
                config = json.loads(file['content'])
                config['case_id'] = CASE
                config['selected_case_id'] = CASE
                config['case_suffix'] = SUFFIX
                config['supported_case_ids'] = [CASE]
                config['requested_emergency_stop_frame'] = 200
                config['recording_description'] = 'Moving authorized emergency vehicle approaches the driver and then stops; preserve NRS 484B.607 referral without inferring its unsupplied duties. Four original camera and 600-frame pose sources are required.'
                file['content'] = json.dumps(config, indent=2) + '\n'
            elif file['path'] == 'runner.py':
                file['content'] = (HERE / 'native/stopped_runner.py').read_text()
            elif file['path'] == 'measure_approach.py':
                file['content'] = (HERE / 'native/measure_stopped.py').read_text()
            elif file['path'] == 'finalize.py':
                file['content'] = (HERE / 'native/finalize_stopped.py').read_text()
            elif file['path'] == 'tests/test_native.py':
                file['content'] = (HERE / 'native/tests/test_stopped.py').read_text()
        path = HERE / 'current-bundles' / SUFFIX / cid / 'construction.json'
        write(path, original)
        dest['construction'] = path.relative_to(HERE).as_posix()
        dest['construction_sha256'] = sha(path)
    manifest['cases'] = [x for x in manifest['cases'] if x['case_id'] != CASE] + [entry]
    manifest['delivery_ready'] = False
    write(manifest_path, manifest)
    plan_path = HERE / 'case-plan.json'
    plan = read(plan_path)
    stopped = {'requirement': 'NRS-484B-267-2f',
               'source': 'NRS 484B.267(2)(f); with 484B.267(4)',
               'branch': 'Moving emergency vehicle stops; referral to NRS 484B.607',
               'status': 'selected_required', 'case_ids': [CASE],
               'evidence_or_gap': 'Selected CPU construction measures a moving vehicle stopping and preserves the unsupplied 484B.607 referral; original motion and legal source remain for review.'}
    plan['requirement_dispositions'] = [x for x in plan['requirement_dispositions']
                                        if x.get('branch') != stopped['branch']]
    plan['requirement_dispositions'].insert(2, stopped)
    case = {'case_id': CASE, 'target_law_id': plan['law_id'], 'kind': 'delivery',
            'source_branch': stopped['branch'],
            'physical_target': 'request a moving source vehicle to stop and measure its original stopped state without a 484B.607 duty verdict',
            'comparison_variable': 'emergency vehicle stops versus continues approach',
            'requested_not_measured': True, 'selection_targets': ['full-train'],
            'gap_ids': ['approaching_referral']}
    plan['cases'] = [x for x in plan['cases'] if x['case_id'] != CASE] + [case]
    comparison_id = AID + '__stopped_referral_comparison'
    plan['comparisons'] = [x for x in plan['comparisons'] if x['comparison_id'] != comparison_id]
    plan['comparisons'].append({'comparison_id': comparison_id,
        'case_ids': [AID + '__controlled_1', CASE],
        'deliberate_differences': ['emergency vehicle stops instead of continuing approach and passing'],
        'fixed_conditions': ['same road, actor kind, initial vehicle and driver trajectories, lights, right-edge request and four camera timing']})
    write(plan_path, plan)
    contract = {'format': 'worker-measurement-contract', 'requirements': [
        {'disposition_index': 2, 'requirement': 'NRS-484B-267-2f',
         'source': stopped['source'], 'output_key': 'approach_response',
         'method': 'measure_stopped_referral', 'value_type': 'object',
         'kind': 'measured', 'inputs': ['video_frames.jsonl', 'vehicle_poses.jsonl', 'emergency_context.json']}],
        'negative': {'remove': ['emergency_context.json'],
                     'error_contains': 'Missing required source: emergency_context.json'}}
    write(HERE / entry['measurement_contract'], contract)
    print(json.dumps({'case': CASE, 'construction_sha256': entry['construction_sha256'],
                      'fixture_recipe_sha256': sha(HERE / ('current-' + SUFFIX + '-recipe.json'))}))


if __name__ == '__main__':
    main()
