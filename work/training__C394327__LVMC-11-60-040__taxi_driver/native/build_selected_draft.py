"""Promote taxi request constructions to selected CPU work in progress.

This writes a selected draft only. It makes no claim about compatibility,
recorded-only processing, original activity or delivery acceptance.
"""
import copy
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
PREFIX = BASE.name
CHANNELS = ('ru.taxicab', 'st.curb_zone', 'dev.regulatory_sign',
            'drv.standing_or_parked', 'rel.occupies', 'drv.stopped',
            'sig.door_open', 'ru.occupant_count', 'kin.time')


def recording_description():
    return {
        'channels': [{
            'name': name, 'unit': 'source observation',
            'method': 'joined original Native taxi, camera and reviewed activity sources',
            'reference_frame': 'original C394327 taxi and participant frames',
            'sampling_rate_hz': 20, 'time_window': '600 frames / 30 s',
            'uncertainty': 'Original identity, stand authority, activity and pixels require local review'
        } for name in CHANNELS],
        'context_inputs': [
            {'name': 'taxi_license_review', 'unit': 'source review',
             'method': 'licensed-taxicab authority document review'},
            {'name': 'stand_designation_review', 'unit': 'source review',
             'method': 'designated stand authority document review'},
            {'name': 'other_regulations_review', 'unit': 'source review',
             'method': 'other stopping and parking rules review'}],
        'limitations': ['No legal verdict or original Native acceptance from CPU diagnostic']}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def selected_construction(source, case_id, candidate_id):
    construction = copy.deepcopy(json.loads(source.read_text()))
    if construction['case_id'] != case_id:
        raise ValueError('Draft construction binds another exact case')
    finalizer = (BASE / 'native' / 'selected_finalize.py').read_text()
    construction['files'].append({'path': 'selected_finalize.py',
                                  'content': finalizer})
    for item in construction['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config.update({'assignment_id': PREFIX, 'selected_case_id': case_id,
                           'candidate_id': candidate_id, 'required_atoms': [],
                           'source_packets': [], 'case': {'case_id': case_id},
                           'physical_acceptance_claimed': False})
            config['case']['recording_description'] = recording_description()
            item['content'] = json.dumps(config, indent=2) + '\n'
    construction['recording_description'] = recording_description()
    construction['status'] = 'selected_cpu_proofs_pending'
    construction['candidate_id'] = candidate_id
    return construction


def main():
    draft = json.loads((BASE / 'draft-native-manifest.json').read_text())
    bindings_path = BASE / 'native' / 'selected-offline-bindings.json'
    bindings = json.loads(bindings_path.read_text()) if bindings_path.is_file() else {}
    if draft['assignment_id'] != PREFIX or len(draft['cases']) != 2:
        raise ValueError('Expected two exact taxi cases')
    entries = []
    for original in draft['cases']:
        case = original['case_id']
        suffix = case.removeprefix(PREFIX + '__')
        if suffix not in ('probe_a', 'probe_b'):
            raise ValueError('Unexpected taxi case')
        primary_path = BASE / ('selected-' + suffix + '-construction.json')
        primary = selected_construction(BASE / original['construction'], case, 'primary')
        write(primary_path, primary)
        candidate = original['candidates'][0]
        if candidate['id'] != 'fallback1':
            raise ValueError('Selected candidate must use supported fallback1 ID')
        fallback_path = BASE / ('selected-' + suffix + '-fallback1-construction.json')
        fallback = selected_construction(BASE / candidate['construction'], case, 'fallback1')
        write(fallback_path, fallback)
        primary_config = json.loads(next(x['content'] for x in primary['files']
                                         if x['path'] == 'config.json'))
        fallback_config = json.loads(next(x['content'] for x in fallback['files']
                                          if x['path'] == 'config.json'))
        fixed = ('cell_id', 'law_id', 'actor', 'selected_case_id', 'required_atoms',
                 'source_packets', 'rate_hz', 'duration_s', 'cameras', 'case')
        if any(primary_config.get(key) != fallback_config.get(key) for key in fixed):
            raise ValueError('Fallback changed selected capture contract')
        if primary['recording_description'] != fallback['recording_description']:
            raise ValueError('Fallback changed recording observations')
        contract_path = BASE / ('selected-' + suffix + '-measurement-contract.json')
        write(contract_path, {
            'format': 'worker-measurement-contract', 'case_id': case,
            'requirements': [{
                'disposition_index': 0, 'requirement': 'LVMC-11-60-040',
                'source': 'LVMC 11.60.040',
                'output_key': 'taxi_loading_measurement',
                'method': 'taxi_loading_measurement', 'kind': 'measured',
                'value_type': 'object',
                'inputs': ['observed-activity.jsonl',
                           'participant-activity-review.json',
                           'stand-designation-review.json',
                           'other-regulations-review.json']}],
            'negative': {
                'remove': ['observed-activity.jsonl'],
                'error_contains': 'Missing required source: observed-activity.jsonl'},
            'frame_count': 600, 'sampling_rate_hz': 20, 'duration_s': 30,
            'legal_verdict': None, 'physical_acceptance_claimed': False})
        entries.append({
            'case_id': case, 'kind': 'delivery',
            'construction': primary_path.name,
            'construction_sha256': sha(primary_path),
            'fixture_recipe': str((BASE / 'native' / 'diagnostic' / suffix /
                                   'fixture-recipe.json').relative_to(Path.cwd())),
            'measurement_contract': contract_path.name,
            'measurement_procedure': {'entrypoint': 'selected_finalize.py'},
            'candidate_risk': original['candidate_risk'],
            'candidates': [{
                'id': 'fallback1', 'construction': fallback_path.name,
                'construction_sha256': sha(fallback_path),
                'trigger': candidate['trigger'],
                'changed_knobs': candidate['changed_knobs']}]})
        for candidate_id, item in [('primary', entries[-1]),
                                   ('fallback1', entries[-1]['candidates'][0])]:
            log_path = BASE / 'native' / (
                'selected-' + suffix.replace('_', '-') + '-' + candidate_id + '-offline.log')
            if log_path.is_file() and bindings.get(suffix + ':' + candidate_id) == item['construction_sha256']:
                receipt = json.loads(log_path.read_text())
                if (receipt.get('case_id') != case or
                        receipt.get('candidate_id') != candidate_id or
                        receipt.get('offline_passed') is not True or
                        receipt.get('simulation_started') is not False):
                    raise ValueError('Selected offline receipt does not match candidate')
                command = ('.venv-cpu/bin/python -B runtime.py offline --manifest work/' +
                           PREFIX + '/selected-draft-manifest.json --case ' + case +
                           ' --output .runtime-work/c394327-selected-' + suffix +
                           '-' + candidate_id + '-camera-v2 --python ' +
                           str(Path.cwd() / '.venv-cpu/bin/python'))
                if candidate_id != 'primary':
                    command += ' --candidate ' + candidate_id
                item['offline'] = {'command': command, 'exit_code': 0,
                                   'construction_sha256': item['construction_sha256'],
                                   'log': str(log_path.relative_to(BASE)),
                                   'log_sha256': sha(log_path)}
    runtime_hash = sha(Path.cwd() / 'runtime' / 'SOURCE-MANIFEST.json')
    write(BASE / 'selected-draft-manifest.json', {
        'format': 'worker-execution-manifest', 'assignment_id': PREFIX,
        'runtime_manifest_sha256': runtime_hash,
        'status': 'selected_cpu_proofs_pending', 'delivery_ready': False,
        'original_native_observed': False, 'cases': entries})


if __name__ == '__main__':
    main()
