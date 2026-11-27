"""Bind exact measurement contracts and diagnostic recipes to selected primaries."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
AID = ROOT.name
SOURCES = ['road.xodr', 'bus-context.json', 'bus-history.jsonl',
           'video_frames.jsonl', 'trace.jsonl', 'capture/manifest.json',
           'overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv']


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    proposals = {'cell_id': 'C386410', 'actor': 'bus_driver', 'status': 'draft',
                 'sweep_specs': [], 'sweeps_expanded': True, 'cases': []}
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        construction = json.loads((ROOT / entry['construction']).read_text())
        proposals['cases'].append({'case_id': case, 'target_law_id': plan['law_id'],
            'target_type': 'attempt', 'recording_description': construction['recording_description'],
            'variable_assignments': {'bus_standing_location': {'kind': 'world_setup',
              'value': suffix, 'unit': 'category'}},
            'unresolved_judgment_calls': ['official designation', 'standing or parking legal characterization'],
            'rationale': 'Exact source-joined bus standing location comparison.'})
        rows = []
        for index, (method, key) in enumerate((('measure_bus_event', 'bus_event'),
                                                ('source_place', 'bus_place'),
                                                ('source_scope', 'bus_scope'))):
            disposition = plan['requirement_dispositions'][index]
            rows.append({'disposition_index': index,
                'requirement': disposition['requirement'], 'source': disposition['source'],
                'kind': 'measured' if index == 0 else 'sourced_context',
                'method': method, 'output_key': key, 'value_type': 'object',
                'inputs': SOURCES})
        contract = {'format': 'worker-measurement-contract', 'case_id': case,
            'requirements': rows, 'negative': {'remove': ['bus-context.json'],
            'error_contains': 'Missing required source: bus-context.json'}}
        path = ROOT / 'cases' / suffix / 'measurement-contract.json'
        write(path, contract)
        entry['measurement_contract'] = str(path.relative_to(ROOT))
        entry['fixture_recipe'] = 'work/' + AID + '/cases/' + suffix + '/recipe.json'
    write(ROOT / 'proposals/cases.json', proposals)
    write(manifest_path, manifest)


if __name__ == '__main__':
    main()
