"""Bind current C135709 selected CPU receipts into the canonical case manifest."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(path):
    return json.loads(Path(path).read_text())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    manifest = read(ROOT/'execution-manifest-draft.json')
    offline = read(ROOT/'selected-all/draft-proof.json')['results']
    compatible = read(ROOT/'update051-proof-matrix.json')['results']
    saved = read(ROOT/'update051-saved-matrix.json')['results']
    delivery = read(ROOT/'update053-delivery-contract.json')['contracts']
    lookup = lambda rows, case, candidate: next(
        row for row in rows if row['case_id'] == case and row['candidate_id'] == candidate)
    for entry in manifest['cases']:
        case = entry['case_id']
        witness = case.rsplit('__', 1)[-1]
        primary = lookup(offline, case, 'primary')
        entry['offline'] = {key: primary[key] for key in
                            ('command', 'exit_code', 'construction_sha256',
                             'log', 'log_sha256')}
        physical = ROOT/'update052-physical'/witness/'proof.json'
        entry['physical_preparation'] = {
            'receipt': physical.relative_to(ROOT).as_posix(), 'sha256': sha(physical)}
        entry['delivery_acceptance'] = delivery[witness]
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST',
                                   'port_env_var': 'CARLA_PORT'}
        entry['acquisition'] = {
            name: {'entrypoint': 'finalize_selected.py',
                   'method': 'derive from retained Native actor, frame, map and review rows',
                   'evidence': 'native-raw-actors.jsonl, video_frames.jsonl, stand-review.jsonl and native-map-readback.json'}
            for name in ('ego_pose', 'ego_speed',
                         'taxicab_stand_occupancy_by_nontaxicab',
                         'four_source_views')}
        entry['compatibility'] = compatibility_ref(witness, 'primary')
        entry['negative'] = {'log': f'update051-proof/{witness}/primary/negative.log'}
        processed = lookup(saved, case, 'primary')
        entry['post_capture'] = {'recorded_only': True,
            'command': processed['command'],
            'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
            'test_exit_code': processed['exit_code'],
            'test_log': processed['log'],
            'test_log_sha256': processed['log_sha256']}
        for candidate in entry['candidates']:
            ident = candidate['id']
            proof = lookup(offline, case, ident)
            candidate['offline'] = {key: proof[key] for key in
                                    ('command', 'exit_code', 'construction_sha256',
                                     'log', 'log_sha256')}
            candidate['compatibility'] = compatibility_ref(witness, ident)
    manifest['status'] = 'selected_cpu_proven_pending_delivery_review'
    manifest['delivery_ready'] = False
    manifest['original_native_observed'] = False
    output = ROOT/'execution-manifest.json'
    output.write_text(json.dumps(manifest, indent=2)+'\n')
    return manifest


def compatibility_ref(witness, candidate):
    base = Path('update051-proof')/witness/candidate
    receipt = ROOT/base/'receipt.json'
    return {'receipt': (base/'receipt.json').as_posix(), 'sha256': sha(receipt),
            'log': (base/'analysis.log').as_posix(),
            'negative_log': (base/'negative.log').as_posix()}


if __name__ == '__main__':
    print(json.dumps({'cases': len(bind()['cases']), 'delivery_ready': False}))
