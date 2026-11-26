"""Bind current-hash selected CPU evidence to exact source-gated handoff."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
AID = HERE.name


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    if manifest['assignment_id'] != AID or len(manifest['cases']) != 9:
        raise ValueError('nine current selected cases required')
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.removeprefix(AID + '__')
        if sha(HERE / entry['construction']) != entry['construction_sha256']:
            raise ValueError('selected construction changed')
        physical = HERE / ('physical-' + suffix + '-receipt.json')
        delivery = HERE / ('delivery-acceptance-' + suffix + '.json')
        saved = HERE / ('proof-saved-primary-' + suffix + '.log')
        entry['physical_preparation'] = {'receipt': physical.name, 'sha256': sha(physical)}
        entry['saved_replay'] = {'log': saved.name, 'sha256': sha(saved)}
        entry['delivery_acceptance'] = json.loads(delivery.read_text())
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT',
                                   'reviewed_packet_env_var': 'C376609_REVIEWED_SITE'}
        entry['post_capture'] = {
            'command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' + AID +
                       '/execution-manifest.json --case ' + case +
                       ' --attempt $ATTEMPT --output $PROCESSED --library runtime/library'
                       ' --validator $LEAN_VALIDATOR --owner-release-receipt $OWNER_RELEASE_RECEIPT',
            'feedback_command': '.venv-cpu/bin/python work/' + AID +
                                '/delivery_audit.py --case ' + case +
                                ' --attempt $ATTEMPT --review $PIXEL_REVIEW --physical $PHYSICAL_RESULT',
            'recorded_only': True, 'test_exit_code': 0,
            'test_log': saved.name, 'test_log_sha256': sha(saved)}
        entry['missing_proofs'] = ['reviewed original highway and exclusive lane site',
                                   '900-frame four-view Native capture',
                                   'independent original physical and pixel review']
        for candidate in entry['candidates']:
            spec = candidate['compatibility']
            spec['negative_log'] = 'proof-compat-negative-' + candidate['id'] + '-' + suffix + '.log'
    manifest['status'] = 'selected_cpu_proofs_bound_original_source_pending'
    path.write_text(json.dumps(manifest, indent=2) + '\n')
    return len(manifest['cases'])


if __name__ == '__main__':
    print('bound selected CPU case proofs:', run())
