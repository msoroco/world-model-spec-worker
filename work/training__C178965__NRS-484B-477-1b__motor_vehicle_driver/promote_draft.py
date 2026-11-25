"""Bind current Native drafts to exact-case measurement and semantic plans."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n')


def main():
    plan_path = HERE / 'case-plan.json'
    plan = json.loads(plan_path.read_text())
    aid = plan['assignment_id']
    ids = [case['case_id'] for case in plan['cases']]
    if len(ids) != 3 or len(set(ids)) != 3:
        raise ValueError('The below, exact and above boundary case plan differs')
    manifest = json.loads((HERE / 'draft-alley-manifest.json').read_text())
    if {entry['case_id'] for entry in manifest['cases']} != set(ids):
        raise ValueError('Current Native draft manifest and case plan differ')
    descriptions = {}
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(aid + '__')
        proposal = json.loads((HERE / entry['construction']).read_text())
        config = json.loads(next(item['content'] for item in proposal['files']
                                 if item['path'] == 'config.json'))
        descriptions[entry['case_id']] = config['recording_description']
        contract = {'format': 'worker-measurement-contract', 'case_id': entry['case_id'],
                    'requirements': [{'disposition_index': 0,
                                      'requirement': 'NRS-484B-477-1b',
                                      'source': 'NRS 484B.477(1)(b)',
                                      'output_key': 'source_bound_alley_width',
                                      'method': 'alley_width_measurement',
                                      'value_type': 'object', 'kind': 'measured',
                                      'inputs': ['vehicle-poses.jsonl', 'video_frames.jsonl',
                                                 'alley-inventory.json', 'trace.jsonl']}],
                    'negative': {'remove': ['alley-inventory.json'],
                                 'error_contains': 'Missing required source: alley-inventory.json'}}
        path = HERE / 'draft-alley' / suffix / 'measurement-contract.json'
        write(path, contract)
        entry['measurement_contract'] = str(path.relative_to(HERE))
        entry['measurement_procedure'] = {'entrypoint': 'finalize_alley.py'}
        entry['fixture_recipe'] = str((HERE / f'diagnostic-{suffix}-recipe.json').relative_to(ROOT))
    write(HERE / 'draft-alley-manifest.json', manifest)
    first = json.loads((HERE / manifest['cases'][0]['construction']).read_text())
    for item in first['files']:
        target = HERE / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(item['content'])
    write(HERE / 'construction.json', first)
    proposals = {'cell_id': 'C178965', 'actor': 'motor_vehicle_driver',
                 'status': 'draft', 'sweep_specs': [
                     {'sweep_id': 'ten-foot-exact-boundary',
                      'target_law_id': 'NRS-484B-477-1b',
                      'judgment_refs': [{'phrase': 'less than 10 feet',
                                         'note': 'The exact equality boundary is not less than ten feet.'}],
                      'status': 'expanded', 'rationale': 'Below, equal and above saved width probes.',
                      'missing_inputs': []},
                     {'sweep_id': 'alley-and-ordinance-review',
                      'target_law_id': 'NRS-484B-477-1b',
                      'judgment_refs': [{'phrase': 'any other alley',
                                         'note': 'Alley identity and antecedent need independent review.'},
                                        {'phrase': 'Unless otherwise provided by ordinance',
                                         'note': 'Local authority and ordinance effect are not inferred from a scene.'}],
                      'status': 'incomplete',
                      'rationale': 'Original geometry is separate from legal site and ordinance status.',
                      'missing_inputs': ['Independent site/ordinance source packet for the Native attempt.']}],
                 'sweeps_expanded': True, 'cases': []}
    for case in plan['cases']:
        suffix = case['case_id'].removeprefix(aid + '__')
        proposals['cases'].append({'case_id': case['case_id'],
                                   'target_law_id': 'NRS-484B-477-1b',
                                   'target_type': 'boundary_probe',
                                   'rationale': case['physical_target'],
                                   'deliberate_differences': ['unobstructed alley width'],
                                   'variable_assignments': {
                                       'alley_width_m': {'kind': 'world_setup',
                                                         'value': {'controlled_1': 7.5,
                                                                   'controlled_at_10': 6.648,
                                                                   'controlled_2': 6.0}[suffix]},
                                       'parking_request': {'kind': 'subject_behavior',
                                                           'value': 'park beside a distinct other vehicle'}},
                                   'unresolved_judgment_calls': ['qualifying alley and any other alley antecedent',
                                                                 'local ordinance effect',
                                                                 'actual parking purpose and free movement'],
                                   'recording_description': descriptions[case['case_id']]})
    write(HERE / 'proposals' / 'cases.json', proposals)
    mapping = plan.get('source_observation_mapping')
    if isinstance(mapping, list):
        plan['source_observation_mapping'] = {item['term']: {key: value for key, value in item.items()
                                                            if key != 'term'} for item in mapping}
    plan['camera_plan'] = {'profile': 'overview1080-capability', 'duration_s': 30,
                           'composition': 'synchronized_four_view_primary',
                           'coverage': [{'view': name, 'subject': 'subject, other vehicle and paved alley edges',
                                         'interval': 'all 600 original frames'}
                                        for name in ('overview', 'approach', 'reference_corner', 'driver_reference')]}
    write(plan_path, plan)
    print(json.dumps({'cases': ids, 'measurement_contracts': 3,
                      'proposal_sha256': hashlib.sha256((HERE / 'proposals/cases.json').read_bytes()).hexdigest(),
                      'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
