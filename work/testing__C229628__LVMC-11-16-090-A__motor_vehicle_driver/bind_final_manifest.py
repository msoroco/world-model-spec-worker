"""Bind current selected, physical and independent delivery CPU proofs."""
import hashlib
import json
from pathlib import Path

from package_spec import AID, CHANNELS

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    manifest = json.loads((HERE / 'execution-manifest.selected-draft.json').read_text())
    if manifest['assignment_id'] != AID or len(manifest['cases']) != 4:
        raise ValueError('four exact selected aid cases required')
    sources = {
        'participants': ('native_source.py', 'source-sealed two-person and two-motor-vehicle identity'),
        'highway_jurisdiction': ('native_source.py', 'reviewed highway and municipal source status'),
        'lane_and_route': ('contest_carla_adapter.py', 'Native road and lane route readback'),
        'cue_and_episode': ('contest_carla_adapter.py', 'physical ego light state and other start readback'),
        'two_vehicle_motion': ('contest_capture.py', '900-frame original positions, speeds and acceleration'),
        'camera_frame_identity': ('contest_capture.py', 'four synchronized original cameras')}
    for entry in manifest['cases']:
        suffix = entry['case_id'].removeprefix(AID + '__')
        if sha(HERE / entry['construction']) != entry['construction_sha256']:
            raise ValueError('selected construction changed: ' + suffix)
        proof_path = HERE / ('proof-compat-receipt-' + suffix + '.json')
        proof = json.loads(proof_path.read_text())
        if not (proof.get('passed') is True and
                proof.get('construction_sha256') == entry['construction_sha256']):
            raise ValueError('selected compatibility proof stale: ' + suffix)
        physical = HERE / ('physical-' + suffix + '-receipt.json')
        saved = HERE / ('proof-selected-saved-' + suffix + '.log')
        delivery = HERE / ('delivery-acceptance-' + suffix + '.json')
        entry['compatibility'] = {'receipt': proof_path.name, 'sha256': sha(proof_path),
            'log': 'proof-compat-analysis-' + suffix + '.log',
            'negative_log': 'proof-compat-negative-' + suffix + '.log'}
        entry['negative'] = {'log': 'proof-compat-negative-' + suffix + '.log'}
        entry['physical_preparation'] = {'receipt': physical.name, 'sha256': sha(physical)}
        entry['saved_replay'] = {'log': saved.name, 'sha256': sha(saved)}
        entry['candidate_risk'] = {'status': 'none',
            'reason': 'A reviewed independent two-vehicle spawn and connected Native route are prerequisites; no site-specific alternate engineering trigger is evidenced before the original site packet. Physical failures must be recorded, not selected by legal outcome.'}
        entry['candidates'] = []
        entry['post_capture'] = {
            'command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' + AID +
                       '/execution-manifest.json --case ' + entry['case_id'] +
                       ' --attempt $ATTEMPT --output $PROCESSED --library runtime/library --validator $LEAN_VALIDATOR --owner-release-receipt $OWNER_RELEASE_RECEIPT',
            'feedback_command': '.venv-cpu/bin/python work/' + AID +
                                '/delivery_audit.py --case ' + entry['case_id'] +
                                ' --attempt $ATTEMPT --review $PIXEL_REVIEW --physical $PHYSICAL_RESULT',
            'recorded_only': True, 'test_exit_code': 0,
            'test_log': saved.name, 'test_log_sha256': sha(saved)}
        entry['delivery_acceptance'] = json.loads(delivery.read_text())
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT',
                                   'reviewed_packet_env_var': 'C229628_REVIEWED_SITE'}
        entry['acquisition'] = {name: {'entrypoint': sources[name][0],
                                       'method': sources[name][1],
                                       'evidence': 'original-source-receipt.json, contest-packet.json and synchronized four-view 900-frame capture'}
                                for name, _, _ in CHANNELS}
    manifest['status'] = 'selected_cpu_proofs_bound_native_review_pending'
    (HERE / 'execution-manifest.json').write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    return len(manifest['cases'])


if __name__ == '__main__':
    print('bound aid/contest cases:', build())
