"""Bind current runtime contract and exact probe 2 diagnostic sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__probe_2'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def main():
    original = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    description = json.loads((HERE / 'draft-exact/probe_2/primary/construction.json').read_text())['recording_description']
    proposal = {'cell_id': 'C188094', 'actor': 'pedestrian', 'status': 'draft',
                'cases': [{'case_id': case['case_id'], 'target_law_id': 'LVMC-11-30-070-B',
                           'target_type': case['target_type'], 'recording_description': description,
                           'variable_assignments': {}, 'sweep_measurements': []}
                          for case in plan['cases']]}
    (HERE / 'proposals').mkdir(exist_ok=True)
    write(HERE / 'proposals/cases.json', proposal)
    selected = plan['requirement_dispositions'][0]
    contract = {'format': 'worker-measurement-contract', 'case_id': CASE,
                'requirements': [{'disposition_index': 0, 'requirement': selected['requirement'],
                                  'source': selected['source'], 'output_key': 'business_district_crossing_path',
                                  'method': 'measure_selected_crossing', 'value_type': 'object',
                                  'kind': 'measured',
                                  'inputs': ['actor-poses.jsonl', 'crossing-context.json', 'road.xodr']}],
                'negative': {'remove': ['crossing-context.json'],
                             'error_contains': 'Missing required source: crossing-context.json'}}
    write(HERE / 'v2-probe2-measurement-contract.json', contract)
    single = dict(original)
    single['cases'] = [dict(original['cases'][1])]
    single['cases'][0]['measurement_contract'] = 'v2-probe2-measurement-contract.json'
    single['cases'][0]['fixture_recipe'] = 'work/' + HERE.name + '/v2-probe2-fixture-recipe.json'
    write(HERE / 'v2-probe2-manifest.json', single)
    print(json.dumps({'construction_sha256': single['cases'][0]['construction_sha256'],
                      'measurement_contract_sha256': sha(HERE / 'v2-probe2-measurement-contract.json')}))


if __name__ == '__main__':
    main()
