"""Bind passing current-runtime proofs into exact delivery entries."""

import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
CHECKS = ['native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion']


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path):
    return path.relative_to(HERE).as_posix()


def build():
    draft = json.loads((HERE / 'selected-construction-manifest.json').read_text())
    offline = {(x['case_id'], x['candidate_id']): x for x in
               json.loads((HERE / 'selected-offline-proofs.json').read_text())['proofs']}
    compatibility = {(x['case_id'], x['candidate_id']): x for x in
                     json.loads((HERE / 'selected-compatibility-proofs.json').read_text())['proofs']}
    saved = {(x['case_id'], x['candidate_id']): x for x in
             json.loads((HERE / 'selected-saved-proofs.json').read_text())['proofs']}
    audits = {x['case_id']: x for x in
              json.loads((HERE / 'delivery-audit-proofs.json').read_text())['proofs']}

    def bind(candidate, case):
        off = offline[case, candidate]
        comp = compatibility[case, candidate]
        sav = saved[case, candidate]
        if off['construction_sha256'] != (entry['construction_sha256'] if candidate == 'primary'
                                           else entry['candidates'][0]['construction_sha256']):
            raise ValueError('Offline proof construction changed')
        comp_path = HERE / comp['receipt']
        comp_body = json.loads(comp_path.read_text())
        if not comp_body.get('passed') or comp_body['construction_sha256'] != off['construction_sha256']:
            raise ValueError('Public compatibility construction changed')
        saved_path = HERE / sav['receipt']
        saved_body = json.loads(saved_path.read_text())
        if not saved_body['source_hashes_preserved']:
            raise ValueError('Saved source preservation failed')
        return ({'command': off['command'], 'construction_sha256': off['construction_sha256'],
                 'exit_code': off['exit_code'], 'log': off['log'],
                 'log_sha256': off['log_sha256']},
                {'receipt': comp['receipt'], 'sha256': sha(comp_path),
                 'log': rel(HERE / f'selected-compatibility/{case.rsplit("__", 1)[1]}-{candidate}/analysis.log'),
                 'negative_log': rel(HERE / f'selected-compatibility/{case.rsplit("__", 1)[1]}-{candidate}/negative.log')},
                {'receipt': sav['receipt'], 'sha256': sha(saved_path),
                 'recorded_only': True, 'originals_preserved': True,
                 'log': rel(HERE / f'selected-saved/{case.rsplit("__", 1)[1]}-{candidate}/analysis.log'),
                 'log_sha256': sav['analysis_log_sha256']})

    entries = []
    for entry in draft['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[1]
        primary_off, primary_comp, primary_saved = bind('primary', case)
        entry['offline'] = primary_off
        entry['compatibility'] = primary_comp
        entry['negative'] = {'log': primary_comp['negative_log']}
        entry['saved_processing'] = primary_saved
        for candidate in entry['candidates']:
            candidate['offline'], candidate['compatibility'], candidate['saved_processing'] = bind(candidate['id'], case)
        construction = json.loads((HERE / entry['construction']).read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        evidence = ['native_samples.jsonl', 'road.xodr', 'sight_samples.jsonl',
                    'trace.jsonl', 'video_frames.jsonl', 'crosswalk_geometry.json',
                    'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                    'driver_reference.mkv']
        required = set(config.get('required_atoms', [])) | {
            channel['name'] for channel in construction['recording_description']['channels']}
        entry['acquisition'] = {
            name: {'entrypoint': 'finalize.py', 'evidence': evidence,
                   'method': 'source-joined original frame, body, road, sight and camera review'}
            for name in sorted(required)}
        physical = HERE / 'physical-preparation' / suffix / 'receipt.json'
        entry['physical_preparation'] = {'receipt': rel(physical), 'sha256': sha(physical)}
        command = (f'.venv-cpu/bin/python runtime.py process-saved --manifest '
                   f'work/{HERE.name}/execution-manifest.json --case {case} --attempt '
                   '$ATTEMPT --output $SAVED --library runtime/library '
                   '--validator $LEAN_VALIDATOR --owner-release-receipt '
                   '$ATTEMPT/owner-release.json')
        log = HERE / primary_saved['log']
        entry['post_capture'] = {'recorded_only': True, 'command': command,
                                 'feedback_command': command, 'test_exit_code': 0,
                                 'test_log': rel(log), 'test_log_sha256': sha(log)}
        audit = audits[case]
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['demo-train', 'full-train'], 'checks': CHECKS,
            'script': audit['script'], 'script_sha256': audit['script_sha256'],
            'command': audit['command'], 'test_exit_code': audit['test_exit_code'],
            'test_log': audit['test_log'], 'test_log_sha256': audit['test_log_sha256'],
            'negative_command': audit['negative_command'],
            'negative_exit_code': audit['negative_exit_code'],
            'negative_expected_error': audit['negative_expected_error'],
            'negative_log': audit['negative_log'],
            'negative_log_sha256': audit['negative_log_sha256']}
        entries.append(entry)
    manifest = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
                'runtime_manifest_sha256': draft['runtime_manifest_sha256'],
                'status': 'selected_cpu_prepared_pending_strict',
                'delivery_ready': False, 'original_native_observed': False,
                'cases': entries}
    target = HERE / 'execution-manifest.json'
    target.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'cases': len(entries), 'sha256': sha(target)}, sort_keys=True))


if __name__ == '__main__':
    build()
