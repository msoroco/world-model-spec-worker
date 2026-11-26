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


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def selected_construction(source, case_id, candidate_id):
    construction = copy.deepcopy(json.loads(source.read_text()))
    if construction['case_id'] != case_id:
        raise ValueError('Draft construction binds another exact case')
    for item in construction['files']:
        if item['path'] == 'config.json':
            config = json.loads(item['content'])
            config.update({'assignment_id': PREFIX, 'selected_case_id': case_id,
                           'candidate_id': candidate_id, 'required_atoms': [],
                           'source_packets': [], 'case': {'case_id': case_id},
                           'physical_acceptance_claimed': False})
            item['content'] = json.dumps(config, indent=2) + '\n'
    construction['status'] = 'selected_cpu_proofs_pending'
    construction['candidate_id'] = candidate_id
    return construction


def main():
    draft = json.loads((BASE / 'draft-native-manifest.json').read_text())
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
            'format': 'worker-source-measurement-contract', 'case_id': case,
            'procedure': 'finalize_original.py',
            'frame_count': 600, 'sampling_rate_hz': 20, 'duration_s': 30,
            'original_sources': ['native-rows.jsonl', 'video_frames.jsonl',
                                 'observed-activity.jsonl', 'four source videos',
                                 'taxi-license, stand-designation, participant-activity and other-regulations reviews'],
            'observations': ['taxi identity', 'outside-designated-stand location',
                             'stopped speed', 'door state', 'occupant transition',
                             'actual loading subject and timing'],
            'legal_verdict': None, 'physical_acceptance_claimed': False})
        entries.append({
            'case_id': case, 'kind': 'delivery',
            'construction': primary_path.name,
            'construction_sha256': sha(primary_path),
            'measurement_contract': contract_path.name,
            'measurement_procedure': {'entrypoint': 'finalize_original.py'},
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
            if log_path.is_file():
                receipt = json.loads(log_path.read_text())
                if (receipt.get('case_id') != case or
                        receipt.get('candidate_id') != candidate_id or
                        receipt.get('offline_passed') is not True or
                        receipt.get('simulation_started') is not False):
                    raise ValueError('Selected offline receipt does not match candidate')
                command = ('.venv-cpu/bin/python -B runtime.py offline --manifest work/' +
                           PREFIX + '/selected-draft-manifest.json --case ' + case +
                           ' --output .runtime-work/c394327-selected-offline-' + suffix +
                           '-' + candidate_id + ' --python ' +
                           str(Path.cwd() / '.venv-cpu/bin/python'))
                if candidate_id != 'primary':
                    command += ' --candidate ' + candidate_id
                item['offline'] = {'command': command, 'exit_code': 0,
                                   'construction_sha256': item['construction_sha256'],
                                   'log': str(log_path.relative_to(BASE)),
                                   'log_sha256': sha(log_path)}
    write(BASE / 'selected-draft-manifest.json', {
        'format': 'worker-execution-manifest', 'assignment_id': PREFIX,
        'status': 'selected_cpu_proofs_pending', 'delivery_ready': False,
        'original_native_observed': False, 'cases': entries})


if __name__ == '__main__':
    main()
