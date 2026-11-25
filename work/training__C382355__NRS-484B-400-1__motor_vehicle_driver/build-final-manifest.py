"""Bind selected CPU receipts to the canonical exact-case execution manifest."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRIPT = HERE / 'delivery_audit.py'
CHECKS = ['native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref(path):
    return path.relative_to(HERE).as_posix()


def compat(suffix, candidate):
    key = suffix + '-' + candidate
    receipt = HERE / 'selected-public' / (key + '-compatibility.json')
    analysis = HERE / 'selected-public' / (key + '-analysis.log')
    negative = HERE / 'selected-public' / (key + '-negative.log')
    proof = json.loads(receipt.read_text())
    if (not proof['passed'] or proof['candidate_id'] != candidate or
            proof['log_sha256'] != sha(analysis) or
            proof['negative_log_sha256'] != sha(negative)):
        raise ValueError('Selected compatibility source differs: ' + key)
    return {'receipt': ref(receipt), 'sha256': sha(receipt),
            'log': ref(analysis), 'negative_log': ref(negative)}


def main():
    data = json.loads((HERE / 'selected-probe-manifest.json').read_text())
    delivery = json.loads((HERE / 'delivery-proofs/proof.json').read_text())['records']
    delivery_by_case = {row['case_id']: row for row in delivery}
    if len(data['cases']) != 4 or len(delivery_by_case) != 4:
        raise ValueError('Selected CPU receipt coverage differs')
    for entry in data['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[-1]
        if entry['offline']['construction_sha256'] != entry['construction_sha256']:
            raise ValueError('Selected primary offline proof differs')
        entry['compatibility'] = compat(suffix, 'primary')
        entry['negative'] = {'log': entry['compatibility']['negative_log']}
        for candidate in entry['candidates']:
            ident = candidate['id']
            if candidate['offline']['construction_sha256'] != candidate['construction_sha256']:
                raise ValueError('Selected fallback offline proof differs')
            candidate['compatibility'] = compat(suffix, ident)
            candidate['fixture_recipe'] = entry['fixture_recipe']
        physical = HERE / 'physical-proof' / suffix / 'proof.json'
        entry['physical_preparation'] = {'receipt': ref(physical), 'sha256': sha(physical)}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT'}
        construction = json.loads((HERE / entry['construction']).read_text())
        config = json.loads(next(f['content'] for f in construction['files']
                                 if f['path'] == 'config.json'))
        atoms = set(config['required_atoms']) | {
            channel['name'] for channel in construction['recording_description']['channels']}
        entry['acquisition'] = {atom: {
            'entrypoint': 'runner.py',
            'method': 'sample original Native qualifying right-only or extreme-right lane design, body, right-turn route and four cameras at one 20 Hz tick; derive source-joined delivery channels',
            'evidence': 'native_samples.jsonl, body_history.jsonl, video_frames.jsonl, road_geometry.json and original source videos'}
            for atom in sorted(atoms)}
        saved = HERE / 'selected-public' / (suffix + '-primary-processing.json')
        log = HERE / 'selected-public' / (suffix + '-primary-saved.log')
        processing = json.loads(saved.read_text())
        if not (processing['passed'] and processing['recorded_only'] and
                processing['timestamp_joins']['frames'] == 480 and
                processing['physical_acceptance_claimed'] is False):
            raise ValueError('Saved-only proof differs: ' + suffix)
        entry['post_capture'] = {
            'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json --case {case} --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $DECODER --owner-release-receipt $OWNER_RELEASE_RECEIPT',
            'feedback_command': f'cat $OUTPUT/versions/*/feedback.json # {case}',
            'recorded_only': True, 'test_exit_code': 0,
            'test_log': ref(log), 'test_log_sha256': sha(log),
            'processing_receipt': ref(saved), 'processing_sha256': sha(saved)}
        proof = delivery_by_case[case]
        pos, neg = proof['positive'], proof['negative']
        if pos['exit_code'] != 0 or neg['exit_code'] == 0:
            raise ValueError('Delivery self-test differs: ' + suffix)
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'], 'checks': CHECKS,
            'script': ref(SCRIPT), 'script_sha256': sha(SCRIPT),
            'command': pos['command'], 'test_exit_code': 0,
            'test_log': pos['log'], 'test_log_sha256': pos['log_sha256'],
            'negative_command': neg['command'],
            'negative_exit_code': neg['exit_code'],
            'negative_expected_error': 'Missing original source: exact original Native result',
            'negative_log': neg['log'], 'negative_log_sha256': neg['log_sha256']}
    data['status'] = 'selected_delivery_prepared'
    path = HERE / 'execution-manifest.json'
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'manifest_cases': len(data['cases']), 'sha256': sha(path)}))


if __name__ == '__main__':
    main()
