"""Bind tested exact selected packages; leave physical/delivery acceptance pending."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
NAMES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def bind():
    path = HERE/'execution-manifest.json'
    manifest = read(path)
    summary = read(HERE/'update020-selected-proof-summary.json')
    if (manifest['status'] != 'partial_selected_cpu_proofs_pending_physical_unverified' or
            summary['staged_execution_manifest_sha256'] != sha(path)):
        raise ValueError('Selected proof run did not use current staged manifest')
    proofs = {(row['case_id'], row['candidate_id']): row for row in summary['proofs']}
    if len(proofs) != 8:
        raise ValueError('Eight exact selected proofs required')
    for entry in manifest['cases']:
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        for candidate in NAMES:
            selected = entry if candidate == 'primary' else next(
                row for row in entry['candidates'] if row['id'] == candidate)
            proof = proofs[(entry['case_id'], candidate)]
            if (sha(HERE/selected['construction']) != selected['construction_sha256'] or
                    proof['construction_sha256'] != selected['construction_sha256']):
                raise ValueError('Selected construction/proof binding differs')
            base = HERE/'selected-proof-bindings-020'/suffix/candidate
            receipt = read(base/'compatibility.json')
            saved = read(base/'saved-processing.json')
            if (receipt['passed'] is not True or receipt['case_id'] != entry['case_id'] or
                    receipt['candidate_id'] != candidate or
                    receipt['construction_sha256'] != selected['construction_sha256'] or
                    receipt['log_sha256'] != sha(base/'analysis.log') or
                    receipt['negative_log_sha256'] != sha(base/'negative-analysis.log') or
                    saved['passed'] is not True or saved['recorded_only'] is not True or
                    saved['originals_preserved'] is not True or
                    saved['missing_evidence'] is not False or
                    saved['native_revision']['construction_sha256'] != selected['construction_sha256']):
                raise ValueError('Selected compatibility/saved proof incomplete')
            relative = f'selected-proof-bindings-020/{suffix}/{candidate}'
            selected['offline'] = {'exit_code': 0,
                'construction_sha256': selected['construction_sha256'],
                'command': proof['offline_command'],
                'log': relative+'/offline.log',
                'log_sha256': sha(base/'offline.log')}
            selected['compatibility'] = {'receipt': relative+'/compatibility.json',
                'sha256': sha(base/'compatibility.json'),
                'log': relative+'/analysis.log',
                'negative_log': relative+'/negative-analysis.log'}
        entry['negative'] = {'log': f'selected-proof-bindings-020/{suffix}/primary/negative-analysis.log'}
        entry['preparation_status'] = 'selected_cpu_offline_compat_saved_proven_physical_unverified'
        entry['acquisition'] = {
            'st.alley': {'entrypoint': 'runner.py',
                'method': 'original Native road and lane waypoint readback',
                'evidence': 'road_geometry.json, native_samples.jsonl'},
            'st.driveway_or_alley_entrance': {'entrypoint': 'runner.py',
                'method': 'surveyed Native driveway lane and authored entrance bounds',
                'evidence': 'road_geometry.json, native_samples.jsonl; property designation pending review'},
            'rel.occupies': {'entrypoint': 'runner.py',
                'method': 'ordered original Native body footprint per frame',
                'evidence': 'native_samples.jsonl, body_history.jsonl'},
            'kin.extent': {'entrypoint': 'runner.py',
                'method': 'original actor bounding box vertices per frame',
                'evidence': 'body_history.jsonl, native_samples.jsonl'},
            'kin.position': {'entrypoint': 'runner.py',
                'method': 'original actor pose and center per frame',
                'evidence': 'native_samples.jsonl, trace.jsonl'},
            'ego_speed': {'entrypoint': 'runner.py',
                'method': 'measured original actor velocity norm',
                'evidence': 'native_samples.jsonl'},
            'native_body_pose_control': {'entrypoint': 'runner.py',
                'method': 'joined original pose, body, lane and controller request',
                'evidence': 'native_samples.jsonl'},
            'camera_frame_join': {'entrypoint': 'runner.py',
                'method': 'four source-camera frames joined to original Native frame',
                'evidence': 'video_frames.jsonl, four source .mkv files'}}
        primary = next(row for row in summary['proofs'] if row['case_id'] == entry['case_id']
                       and row['candidate_id'] == 'primary')
        entry['post_capture'] = {'recorded_only': True,
            'command': primary['saved_command'],
            'feedback_command': primary['saved_command'],
            'test_log': f'update020-{suffix}-primary-saved.log',
            'test_log_sha256': sha(HERE/f'update020-{suffix}-primary-saved.log'),
            'test_exit_code': 0,
            'scope': 'synthetic saved-processing proof; actual Native feedback unverified'}
    manifest['status'] = 'partial_selected_cpu_proofs_bound_physical_unverified'
    path.write_text(json.dumps(manifest, indent=2)+'\n')
    return {'cases': len(manifest['cases']), 'candidate_proofs': len(proofs),
            'status': manifest['status'], 'manifest_sha256': sha(path)}


if __name__ == '__main__':
    print(json.dumps(bind(), indent=2))
