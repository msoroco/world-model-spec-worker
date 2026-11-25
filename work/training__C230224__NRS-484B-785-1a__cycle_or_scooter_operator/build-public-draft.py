"""Bind current-runtime public diagnostic contracts without asserting readiness."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name
SUFFIXES = ('controlled_1', 'controlled_at_cap', 'controlled_2')
RUNTIME_SHA = '5e2dd81ac49dd2d9814a10b71ee30cf85323868a8369116020b06a69cbfcc5e3'


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    base = json.loads((HERE/'selected-offline-manifest.json').read_text())
    by_case = {item['case_id']: item for item in base['cases']}
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': AID,
                'runtime_manifest_sha256': RUNTIME_SHA,
                'status': 'selected_cpu_draft', 'delivery_ready': False, 'cases': []}
    proposal = {'cell_id': 'C230224', 'actor': 'cycle_or_scooter_operator',
                'status': 'draft', 'sweep_specs': [], 'cases': []}
    for suffix in SUFFIXES:
        case = AID + '__' + suffix
        entry = dict(by_case[case])
        contract_path = HERE/f'cases/{suffix}/measurement-contract.json'
        contract = {'format': 'worker-measurement-contract', 'case_id': case,
                    'requirements': [{'disposition_index': 0,
                        'requirement': 'NRS-484B-785-1a', 'source': 'NRS 484B.785(1)(a)',
                        'output_key': 'measure', 'method': 'measure', 'value_type': 'object',
                        'kind': 'measured',
                        'inputs': ['video_frames.jsonl', 'native_rider_trace.jsonl', 'scooter_context.json']}],
                    'negative': {'remove': ['scooter_context.json'],
                                 'error_contains': 'Missing required source: scooter_context.json'}}
        write(contract_path, contract)
        entry.update(kind='delivery',
                     measurement_contract=str(contract_path.relative_to(HERE)),
                     measurement_procedure={'entrypoint': 'measure_scooter.py',
                                            'output_schema': 'worker-analysis-report-v1'},
                     fixture_recipe=f'work/{AID}/cases/{suffix}/recipe.json')
        manifest['cases'].append(entry)
        proposal['cases'].append({'case_id': case, 'target_law_id': 'NRS-484B-785-1a',
            'target_type': 'delivery', 'rationale': 'Exact measured path-speed boundary source review',
            'variable_assignments': {'requested_speed_mph': {'kind': 'world_setup',
                'value': {'controlled_1': 12, 'controlled_at_cap': 15, 'controlled_2': 17}[suffix]}},
            'unresolved_judgment_calls': ['applicable ordinance exception and physical occupancy'],
            'recording_description': json.loads((HERE/('native/config.json' if suffix == 'controlled_1' else f'cases/{suffix}/native/config.json')).read_text())['recording_description']})
    write(HERE/'public-draft-manifest.json', manifest)
    write(HERE/'proposals/cases.json', proposal)
    print(json.dumps({'case_count': len(manifest['cases']),
                      'manifest_sha256': hashlib.sha256((HERE/'public-draft-manifest.json').read_bytes()).hexdigest()},
                     sort_keys=True))


if __name__ == '__main__':
    main()
