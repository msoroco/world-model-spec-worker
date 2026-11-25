"""Bind exact selected CPU proof receipts to the canonical delivery manifest."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'selected-probe-manifest.json'
SCRIPT = HERE / 'delivery_audit.py'
CHECKS = ['native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ref(path):
    return path.relative_to(HERE).as_posix()


def compatibility(case, ident):
    key = case + '-' + ident
    receipt = HERE / 'selected-public-final' / (key + '-compatibility.json')
    analysis = HERE / 'selected-public-final' / (key + '-analysis.log')
    negative = HERE / 'selected-public-final' / (key + '-negative.log')
    proof = json.loads(receipt.read_text())
    if not proof['passed'] or proof['candidate_id'] != ident or proof['log_sha256'] != sha(analysis) or proof['negative_log_sha256'] != sha(negative):
        raise ValueError('Selected public receipt/log mismatch: ' + key)
    return {'receipt': ref(receipt), 'sha256': sha(receipt),
            'log': ref(analysis), 'negative_log': ref(negative)}


def delivery(case_id, suffix):
    pos = HERE / 'delivery-proofs' / (suffix + '-positive.log')
    neg = HERE / 'delivery-proofs' / (suffix + '-negative.log')
    command = f'.venv-cpu/bin/python work/{HERE.name}/delivery_audit.py --case {case_id} --self-test'
    return {'case_id': case_id, 'sets': ['full-train'], 'checks': CHECKS,
            'script': ref(SCRIPT), 'script_sha256': sha(SCRIPT),
            'command': command, 'test_exit_code': 0, 'test_log': ref(pos),
            'test_log_sha256': sha(pos), 'negative_command': command + ' --negative',
            'negative_exit_code': 1,
            'negative_expected_error': 'Missing original source: exact original Native result',
            'negative_log': ref(neg), 'negative_log_sha256': sha(neg)}


def main():
    data = json.loads(MANIFEST.read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    for entry in data['cases']:
        case_id = entry['case_id']
        suffix = case_id.rsplit('__', 1)[-1]
        entry['compatibility'] = compatibility(suffix, 'primary')
        entry['negative'] = {'log': entry['compatibility']['negative_log']}
        for candidate in entry['candidates']:
            candidate['compatibility'] = compatibility(suffix, candidate['id'])
            candidate['fixture_recipe'] = entry['fixture_recipe']
        physical = HERE / 'physical-proof' / suffix / 'proof.json'
        entry['physical_preparation'] = {'receipt': ref(physical), 'sha256': sha(physical)}
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        construction = json.loads((HERE / entry['construction']).read_text())
        config = json.loads(next(f['content'] for f in construction['files'] if f['path'] == 'config.json'))
        atoms = set(config['required_atoms']) | {c['name'] for c in construction['recording_description']['channels']}
        entry['acquisition'] = {atom: {'entrypoint': 'runner.py',
            'method': 'sample original Native lane, body, route, frame and four camera streams at the shared 20 Hz tick',
            'evidence': 'native_samples.jsonl, video_frames.jsonl, road_geometry.json and source camera videos; finalizer joins channels'}
            for atom in sorted(atoms)}
        saved = HERE / 'selected-public-final' / (suffix + '-primary-processing.json')
        processing = json.loads(saved.read_text())
        if not (processing['passed'] and processing['recorded_only'] and
                processing['timestamp_joins']['frames'] == 480 and
                processing['physical_acceptance_claimed'] is False):
            raise ValueError('Saved proof differs: ' + suffix)
        entry['post_capture'] = {
            'command': f'.venv-cpu/bin/python runtime.py process-saved --manifest work/{HERE.name}/execution-manifest.json --case {case_id} --attempt $ATTEMPT --output $OUTPUT --library runtime/library --validator $DECODER --owner-release-receipt $OWNER_RELEASE_RECEIPT',
            'feedback_command': f'cat $OUTPUT/versions/*/feedback.json # {case_id}',
            'recorded_only': True, 'test_exit_code': 0,
            'test_log': ref(saved), 'test_log_sha256': sha(saved)}
        entry['delivery_acceptance'] = delivery(case_id, suffix)
    data['status'] = 'selected_delivery_prepared'
    (HERE / 'execution-manifest.json').write_text(json.dumps(data, indent=2) + '\n')
    print('manifest_cases', len(data['cases']))


if __name__ == '__main__':
    main()
