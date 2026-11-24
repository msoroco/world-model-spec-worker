"""Construct the selected regulatory-agency official approach alternative."""
import copy
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
AID = HERE.name
SUFFIX = 'official_approach'
CASE = AID + '__' + SUFFIX


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def build_fixture():
    source = HERE / 'current-fixture/controlled_1'
    target = HERE / 'current-fixture' / SUFFIX
    target.mkdir(parents=True, exist_ok=True)
    for path in source.rglob('*'):
        if path.is_file():
            dest = target / path.relative_to(source)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, dest)
    context = read(target / 'emergency_context.json')
    context['case_id'] = CASE
    context['responding_vehicle_kind'] = 'regulatory_agency_official'
    context['official_vehicle_reviewed'] = True
    context['official_regulatory_agency_source'] = 'synthetic-fixture:official_regulatory_agency_source'
    context.pop('emergency_vehicle_authorized', None)
    context.pop('emergency_authorization_source', None)
    write(target / 'emergency_context.json', context)
    spec = read(HERE / 'current-controlled_1-diagnostic.json')
    spec_path = HERE / ('current-' + SUFFIX + '-diagnostic.json')
    write(spec_path, spec)
    files = [{'path': path.relative_to(target).as_posix(),
              'source': path.relative_to(ROOT).as_posix(), 'sha256': sha(path)}
             for path in sorted(target.rglob('*')) if path.is_file()]
    recipe = {'format': 'worker-fixture-recipe', 'sources': files,
              'generator': {'source': spec_path.relative_to(ROOT).as_posix(),
                            'sha256': sha(spec_path)}}
    write(HERE / ('current-' + SUFFIX + '-recipe.json'), recipe)


def build_bundle():
    manifest_path = HERE / 'current-execution-manifest.json'
    manifest = read(manifest_path)
    baseline = next(x for x in manifest['cases'] if x['case_id'].endswith('__controlled_1'))
    entry = copy.deepcopy(baseline)
    entry['case_id'] = CASE
    entry['candidate_risk']['reason'] = 'Official-vehicle identity and qualifying equipment require original agency and pixel review; approach and right-edge realization require Native readback'
    entry['measurement_contract'] = 'current-contracts/' + SUFFIX + '.json'
    entry['fixture_recipe'] = 'work/' + AID + '/current-' + SUFFIX + '-recipe.json'
    entry.pop('physical_preparation', None)
    entry.pop('offline', None)
    entry.pop('compatibility', None)
    entry.pop('negative', None)
    entry.pop('saved_processing', None)
    entry.pop('post_capture', None)
    entry.pop('delivery_acceptance', None)
    entry.pop('acquisition', None)
    for candidate in ['primary', *entry['candidates']]:
        cid = candidate if candidate == 'primary' else candidate['id']
        dest = entry if cid == 'primary' else candidate
        for key in ('offline', 'compatibility', 'negative', 'saved_processing'):
            dest.pop(key, None)
        original = read(HERE / 'current-bundles/controlled_1' / cid / 'construction.json')
        original['case_id'] = CASE
        original['recording_description']['limitations'].append('Regulatory-agency official identity requires independent original source review')
        original['measurement_plan']['official_vehicle_kind'] = 'regulatory_agency_official'
        original['recording_description']['context_inputs'] = []
        for file in original['files']:
            if file['path'] == 'config.json':
                config = json.loads(file['content'])
                config['case_id'] = CASE
                config['selected_case_id'] = CASE
                config['case_suffix'] = SUFFIX
                config['responding_vehicle_kind'] = 'regulatory_agency_official'
                config['supported_case_ids'] = [CASE]
                config['recording_description'] = config['recording_description'].replace('emergency vehicle', 'regulatory-agency official vehicle')
                file['content'] = json.dumps(config, indent=2) + '\n'
            elif file['path'] == 'runner.py':
                file['content'] = (HERE / 'native/official_runner.py').read_text()
            elif file['path'] == 'measure_approach.py':
                file['content'] = (HERE / 'native/measure_official.py').read_text()
            elif file['path'] == 'finalize.py':
                file['content'] = (HERE / 'native/finalize_official.py').read_text()
            elif file['path'] == 'tests/test_native.py':
                file['content'] = (HERE / 'native/tests/test_official.py').read_text()
        path = HERE / 'current-bundles' / SUFFIX / cid / 'construction.json'
        write(path, original)
        dest['construction'] = path.relative_to(HERE).as_posix()
        dest['construction_sha256'] = sha(path)
    manifest['cases'] = [x for x in manifest['cases'] if x['case_id'] != CASE] + [entry]
    manifest['delivery_ready'] = False
    write(manifest_path, manifest)
    plan_path = HERE / 'case-plan.json'
    plan = read(plan_path)
    official = {'requirement': 'NRS-484B-267-2f',
                'source': 'NRS 484B.267(2)(f); with 484B.267(4)',
                'branch': 'Regulatory-agency official vehicle approaches the driver',
                'status': 'selected_required', 'case_ids': [CASE],
                'evidence_or_gap': 'Selected CPU construction requests an official vehicle with original agency/equipment review; identity, pixels and physical outcome remain unverified.'}
    plan['requirement_dispositions'] = [x for x in plan['requirement_dispositions']
                                        if x.get('branch') != official['branch']]
    plan['requirement_dispositions'].insert(1, official)
    case = {'case_id': CASE, 'target_law_id': plan['law_id'], 'kind': 'delivery',
            'source_branch': official['branch'],
            'physical_target': 'request right-edge position and stop until regulatory official vehicle passes',
            'comparison_variable': 'source vehicle kind: authorized emergency versus regulatory-agency official',
            'requested_not_measured': True, 'selection_targets': ['full-train'],
            'gap_ids': ['approaching_referral']}
    plan['cases'] = [x for x in plan['cases'] if x['case_id'] != CASE] + [case]
    plan['comparisons'] = [x for x in plan['comparisons']
                           if x['comparison_id'] != AID + '__official_kind_comparison']
    plan['comparisons'].append({'comparison_id': AID + '__official_kind_comparison',
        'case_ids': [AID + '__controlled_1', CASE],
        'deliberate_differences': ['source vehicle kind and identity review'],
        'fixed_conditions': ['same road, driver path, source vehicle path, lights, response controller and four camera timing']})
    write(plan_path, plan)
    contract = {'format': 'worker-measurement-contract', 'requirements': [
        {'disposition_index': 1, 'requirement': 'NRS-484B-267-2f',
         'source': official['source'], 'output_key': 'approach_response',
         'method': 'measure_approach_response', 'value_type': 'object',
         'kind': 'measured', 'inputs': ['video_frames.jsonl', 'vehicle_poses.jsonl', 'emergency_context.json']}],
        'negative': {'remove': ['emergency_context.json'],
                     'error_contains': 'Missing required source: emergency_context.json'}}
    write(HERE / entry['measurement_contract'], contract)
    return entry


def main():
    build_fixture()
    entry = build_bundle()
    print(json.dumps({'case': CASE, 'construction_sha256': entry['construction_sha256'],
                      'fixture_recipe_sha256': sha(HERE / ('current-' + SUFFIX + '-recipe.json'))}))


if __name__ == '__main__':
    main()
