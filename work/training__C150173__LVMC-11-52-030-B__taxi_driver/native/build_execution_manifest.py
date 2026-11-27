"""Bind current exact selected taxi proofs into the canonical execution manifest."""
import copy
import hashlib
import json
from pathlib import Path


PACKAGE = Path(__file__).resolve().parent.parent
SOURCE = PACKAGE / 'selected-draft-manifest.json'
CPU = PACKAGE / 'native-selected-cpu.json'
COMPATIBILITY = PACKAGE / 'native-selected/public-compatibility-summary.json'
SAVED = PACKAGE / 'native-selected/saved-processing-summary.json'
ACQUISITION = {
    'st.curb_zone': ('Original yellow curb geometry and independent color review',
                     ['yellow-road.xodr', 'road.xodr', 'sign-review.json']),
    'dev.regulatory_sign': ('Original posted sign pixels and independent wording/authority review',
                            ['reference_corner.mkv', 'sign-review.json']),
    'drv.condition_in_effect': ('Original civil time joined to reviewed posted conditions',
                                ['yellow-zone-native.jsonl', 'sign-review.json']),
    'env.civil_time': ('Original per-frame civil time and Native frame map',
                       ['yellow-zone-native.jsonl', 'video_frames.jsonl']),
    'ru.taxicab': ('Original actor identity joined to independent taxicab classification',
                   ['yellow-zone-native.jsonl', 'taxicab-review.json']),
    'ru.commercial_motor_vehicle': ('Original actor identity joined to independent commercial-use review',
                                     ['yellow-zone-native.jsonl', 'commercial-status-review.json', 'overview.mkv']),
    'drv.standing_or_parked': ('Original taxi body and velocity samples over full interval',
                               ['yellow-zone-native.jsonl', 'trace.jsonl']),
    'sig.door_open': ('Independently reviewed original passenger activity joined to Native frames',
                      ['observed-passenger-activity.jsonl', 'passenger-purpose-review.json']),
    'ru.occupant_count': ('Independently reviewed original occupancy joined to Native frames',
                          ['observed-passenger-activity.jsonl', 'passenger-purpose-review.json']),
    'kin.time': ('Original Native trace/frame elapsed time',
                 ['trace.jsonl', 'video_frames.jsonl'])}
FREIGHT_ACQUISITION = {
    'st.curb_zone': ('Original yellow curb geometry and color review',
                     ['yellow-freight-road.xodr', 'road.xodr', 'sign-review.json']),
    'dev.regulatory_sign': ('Original freight sign pixels and wording review',
                            ['reference_corner.mkv', 'sign-review.json']),
    'drv.condition_in_effect': ('Original civil time joined to reviewed freight sign',
                                ['freight-native.jsonl', 'sign-review.json']),
    'env.civil_time': ('Original per-frame civil time and Native frame map',
                       ['freight-native.jsonl', 'video_frames.jsonl']),
    'ru.commercial_motor_vehicle': ('Original taxi actor and independent commercial-use review',
                                     ['freight-native.jsonl', 'commercial-status-review.json', 'overview.mkv']),
    'ru.taxicab': ('Original taxi actor identity and commercial-use review',
                   ['freight-native.jsonl', 'commercial-status-review.json']),
    'drv.standing_or_parked': ('Original taxi body and velocity samples over full interval',
                               ['freight-native.jsonl', 'trace.jsonl']),
    'sig.door_open': ('Independently reviewed cargo transfer motion joined to Native frames',
                      ['freight-native.jsonl', 'freight-purpose-review.json']),
    'ru.occupant_count': ('Original actor and cargo occupancy observation',
                          ['freight-native.jsonl', 'overview.mkv']),
    'kin.time': ('Original Native trace/frame elapsed time',
                 ['trace.jsonl', 'video_frames.jsonl'])}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def receipt(index, case_id, candidate):
    item = next((row for row in index['cases']
                 if row['case_id'] == case_id and row['candidate_id'] == candidate), None)
    if item is None:
        raise ValueError('Exact taxi compatibility receipt missing')
    files = item['files']
    source = files['compatibility.json']
    log = files['compatibility-analysis.log']
    negative = files['negative-analysis.log']
    if any(sha(PACKAGE / part['path']) != part['sha256']
           for part in (source, log, negative)):
        raise ValueError('Selected taxi compatibility source changed')
    return {'receipt': source['path'], 'sha256': source['sha256'],
            'log': log['path'], 'negative_log': negative['path']}


def main():
    manifest = copy.deepcopy(json.loads(SOURCE.read_text()))
    cpu = json.loads(CPU.read_text())
    by_case = {entry['case_id']: entry for entry in cpu['cases']}
    compatibility = json.loads(COMPATIBILITY.read_text())
    saved = {item['case_id']: item for item in json.loads(SAVED.read_text())['cases']}
    delivery_path = PACKAGE / 'native-selected/delivery-proof-index.json'
    delivery = (json.loads(delivery_path.read_text()) if delivery_path.is_file()
                else {'cases': []})
    delivery_by_case = {item['case_id']: item for item in delivery['cases']}
    for entry in manifest['cases']:
        case = entry['case_id']
        proof = by_case[case]
        if proof['construction_sha256'] != entry['construction_sha256']:
            raise ValueError('Exact taxi selected construction changed')
        offline = copy.deepcopy(proof['offline_cpu']['primary'])
        offline['command'] = ('.venv-cpu/bin/python -B runtime.py offline '
                              '--manifest work/' + PACKAGE.name + '/execution-manifest.json '
                              '--case ' + case + ' --candidate primary')
        entry['offline'] = offline
        entry['compatibility'] = receipt(compatibility, case, 'primary')
        entry['negative'] = {'log': entry['compatibility']['negative_log'],
                             'log_sha256': sha(PACKAGE / entry['compatibility']['negative_log'])}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT'}
        freight = case.rsplit('__', 1)[1].startswith('freight_')
        acquisition = FREIGHT_ACQUISITION if freight else ACQUISITION
        entry['acquisition'] = {name: {'entrypoint': 'freight_finalize.py' if freight else 'selected_finalize.py',
            'method': method, 'evidence': evidence}
            for name, (method, evidence) in acquisition.items()}
        prior_saved = saved[case]
        positive = prior_saved['files']['positive_analysis']
        saved_receipt = prior_saved['files']['positive_receipt']
        if (not prior_saved['recorded_only'] or
                not prior_saved['originals_preserved'] or
                sha(PACKAGE / positive['path']) != positive['sha256'] or
                sha(PACKAGE / saved_receipt['path']) != saved_receipt['sha256']):
            raise ValueError('Selected taxi saved-only proof changed')
        entry['post_capture'] = {
            'recorded_only': True,
            'command': ('.venv-cpu/bin/python -B runtime.py process-saved '
                        '--manifest work/' + PACKAGE.name + '/execution-manifest.json '
                        '--case ' + case + ' --attempt $ATTEMPT '
                        '--output $SAVED_OUTPUT --library runtime/library '
                        '--validator $DECODER --owner-release-receipt $OWNER_RELEASE_RECEIPT'),
            'feedback_command': 'cat $SAVED_OUTPUT/v0001/feedback.json',
            'test_exit_code': 0,
            'test_log': positive['path'], 'test_log_sha256': positive['sha256'],
            'test_receipt': saved_receipt['path'],
            'test_receipt_sha256': saved_receipt['sha256']}
        if case in delivery_by_case:
            entry['delivery_acceptance'] = copy.deepcopy(delivery_by_case[case])
        for candidate in entry['candidates']:
            ident = candidate['id']
            candidate['offline'] = copy.deepcopy(proof['offline_cpu'][ident])
            candidate['offline']['command'] = (
                '.venv-cpu/bin/python -B runtime.py offline --manifest work/' +
                PACKAGE.name + '/execution-manifest.json --case ' + case +
                ' --candidate ' + ident)
            candidate['compatibility'] = receipt(compatibility, case, ident)
    output = PACKAGE / 'execution-manifest.json'
    output.write_text(json.dumps(manifest, indent=2) + '\n')
    return {'cases': len(manifest['cases']), 'sha256': sha(output)}


if __name__ == '__main__':
    print(json.dumps(main(), sort_keys=True))
