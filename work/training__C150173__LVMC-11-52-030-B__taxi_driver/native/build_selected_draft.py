"""Promote taxi request bundles into exact selected CPU proof candidates."""
import copy
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
ROOT = BASE.parents[1]
NAMES = ('st.curb_zone', 'dev.regulatory_sign', 'drv.condition_in_effect',
         'env.civil_time', 'ru.taxicab', 'drv.standing_or_parked',
         'sig.door_open', 'ru.occupant_count', 'kin.time')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + '\n')


def description():
    return {'channels': [{'name': name, 'unit': 'source observation',
        'method': 'saved original taxi, frame and independent review join',
        'reference_frame': 'C150173 taxi and passenger source frames',
        'sampling_rate_hz': 20, 'time_window': '600 frames / 30 s',
        'uncertainty': 'Taxi, sign, passenger activity and physical pixels require original review'}
        for name in NAMES], 'context_inputs': [],
        'limitations': ['Source-shaped CPU fixtures establish software behavior only',
                        'Ordinary rules outside posted hours and sign authority require source review']}


def selected(source, desc):
    result = copy.deepcopy(source)
    result['recording_description'] = desc
    result['measurement_plan'] = {'method': 'source_join_measurement',
                                  'entrypoint': 'selected_finalize.py'}
    result['status'] = 'selected_cpu_proofs_pending'
    result['files'].append({'path': 'selected_finalize.py',
                            'content': (BASE / 'native/selected_finalize.py').read_text()})
    config_file = next(item for item in result['files'] if item['path'] == 'config.json')
    config = json.loads(config_file['content'])
    config['case']['recording_description'] = desc
    config_file['content'] = json.dumps(config, indent=2) + '\n'
    return result


def main():
    draft = json.loads((BASE / 'native-draft-manifest.json').read_text())
    desc = description()
    entries, proposals = [], []
    for item in draft['cases']:
        case = item['case_id']
        suffix = case.rsplit('__', 1)[1]
        primary = json.loads((BASE / item['construction']).read_text())
        fallback = json.loads((BASE / item['candidates'][0]['construction']).read_text())
        selected_primary = BASE / 'native-selected' / suffix / 'construction.json'
        selected_fallback = BASE / 'native-selected' / suffix / 'fallback1-construction.json'
        write(selected_primary, selected(primary, desc))
        write(selected_fallback, selected(fallback, desc))
        candidate = copy.deepcopy(item['candidates'][0])
        candidate['construction'] = str(selected_fallback.relative_to(BASE))
        candidate['construction_sha256'] = sha(selected_fallback)
        recipe = BASE / 'native/diagnostic' / suffix / 'fixture-recipe.json'
        contract = BASE / 'native-selected' / suffix / 'measurement-contract.json'
        entries.append({'case_id': case, 'kind': 'delivery',
            'construction': str(selected_primary.relative_to(BASE)),
            'construction_sha256': sha(selected_primary),
            'fixture_recipe': str(recipe.relative_to(ROOT)),
            'measurement_contract': str(contract.relative_to(BASE)),
            'measurement_procedure': {'entrypoint': 'selected_finalize.py'},
            'candidate_risk': item['candidate_risk'], 'candidates': [candidate]})
        proposals.append({'case_id': case, 'target_law_id': 'LVMC-11-52-030-B',
            'target_type': 'measurement_attempt',
            'rationale': 'Measure taxi yellow-zone passenger activity and posted hours',
            'variable_assignments': {}, 'unresolved_judgment_calls': [
                'source authority of posted sign', 'passenger purpose from original source',
                'ordinary rules outside posted hours'],
            'recording_description': desc})
    write(BASE / 'proposals/cases.json', {'cell_id': 'C150173',
        'actor': 'taxi_driver', 'status': 'draft', 'cases': proposals})
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': BASE.name,
        'runtime_manifest_sha256': sha(ROOT / 'runtime/SOURCE-MANIFEST.json'),
        'delivery_ready': False, 'status': 'selected_cpu_proofs_pending',
        'cases': entries}
    write(BASE / 'selected-draft-manifest.json', manifest)
    print(json.dumps({'cases': len(entries),
                      'manifest_sha256': sha(BASE / 'selected-draft-manifest.json')}))


if __name__ == '__main__':
    main()
