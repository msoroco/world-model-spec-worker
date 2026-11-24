"""Bind current eight-chain receipts to exact selected CPU delivery intent."""

import copy
import hashlib
import json
from pathlib import Path
import shutil


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SCRATCH = ROOT / '.runtime-work/c10316-head-refresh-v5'
RETURN = HERE / 'head-refresh'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def copy_and_hash(source, name):
    target = RETURN / name
    shutil.copyfile(source, target)
    return target.relative_to(HERE).as_posix(), sha(target)


def main():
    draft = json.loads((HERE / 'draft-execution-manifest.json').read_text())
    proof = json.loads((RETURN / 'proof.json').read_text())
    if proof['manifest_sha256'] != sha(HERE / 'draft-execution-manifest.json'):
        raise ValueError('Eight-chain proof does not bind current draft')
    rows = {(r['case_id'], r['candidate']): r for r in proof['records']}
    if len(rows) != 8:
        raise ValueError('Eight current candidate chains required')
    plan = json.loads((HERE / 'case-plan.json').read_text())
    ids = [case['case_id'] for case in plan['cases']]
    selected = {'format': 'worker-execution-manifest', 'assignment_id': HERE.name,
                'runtime_manifest_sha256': draft['runtime_manifest_sha256'],
                'status': 'delivery_prepared', 'delivery_ready': False,
                'original_native_observed': False, 'source_draft_sha256': sha(HERE / 'draft-execution-manifest.json'),
                'cases': []}
    for draft_entry in draft['cases']:
        entry = copy.deepcopy(draft_entry)
        entry['kind'] = 'delivery'
        entry['native_handoff'] = {'python_env_var': 'CARLA_PYTHON',
                                   'host_env_var': 'CARLA_HOST', 'port_env_var': 'CARLA_PORT'}
        suffix = entry['case_id'].rsplit('__', 1)[-1]
        physical = HERE / 'physical-proof' / suffix / 'proof.json'
        entry['physical_preparation'] = {'case_id': entry['case_id'],
                                         'receipt': physical.relative_to(HERE).as_posix(),
                                         'sha256': sha(physical)}
        construction = json.loads((HERE / entry['construction']).read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        required = set(config['required_atoms']) | {channel['name'] for channel in
                                                   construction['recording_description']['channels']}
        entry['acquisition'] = {name: {'entrypoint': 'finalize.py',
                                       'evidence': 'no-countdown-samples.jsonl, no-countdown-context.json, video_frames.jsonl, capture/evidence.jsonl',
                                       'method': 'derive from original joined Native pose, head readback and camera frames'}
                                for name in sorted(required)}
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            selected_candidate = entry if candidate == 'primary' else next(
                item for item in entry['candidates'] if item['id'] == candidate)
            record = rows[(entry['case_id'], candidate)]
            source = HERE / 'draft-bundles' / suffix / candidate / 'draft-receipt.json'
            offline = json.loads(source.read_text())
            if offline['construction_sha256'] != selected_candidate['construction_sha256']:
                raise ValueError('Offline proof construction differs')
            selected_candidate['offline'] = {
                'command': offline['command'], 'exit_code': 0,
                'construction_sha256': offline['construction_sha256'],
                'log': offline['command_log'], 'log_sha256': offline['command_log_sha256']}
            key = suffix + '-' + candidate
            attempt = SCRATCH / key / 'compat'
            saved = SCRATCH / key / 'saved/v0001/processing.json'
            c_path, c_hash = copy_and_hash(attempt / 'compatibility.json', key + '-compatibility.json')
            a_path, a_hash = copy_and_hash(attempt / 'compatibility-analysis.log', key + '-analysis.log')
            n_path, n_hash = copy_and_hash(attempt / 'negative-analysis.log', key + '-negative.log')
            s_path, s_hash = copy_and_hash(saved, key + '-processing.json')
            if any((c_hash != record['compatibility_receipt_sha256'],
                    n_hash != record['negative_log_sha256'],
                    s_hash != record['saved_receipt_sha256'])):
                raise ValueError('Current public receipt copy changed')
            selected_candidate['compatibility'] = {'receipt': c_path, 'sha256': c_hash,
                                                    'log': a_path, 'negative_log': n_path}
            selected_candidate['negative'] = {'log': n_path}
            selected_candidate['saved_processing'] = {'receipt': s_path, 'sha256': s_hash}
            if candidate == 'primary':
                entry['post_capture'] = {
                    'recorded_only': True,
                    'command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' + HERE.name +
                               '/execution-manifest.json --case ' + entry['case_id'] +
                               ' --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT" --library runtime/library --validator "$DECODER"',
                    'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
                    'test_exit_code': 0, 'test_log': s_path, 'test_log_sha256': s_hash}
        selected['cases'].append(entry)
    write(HERE / 'execution-manifest.json', selected)
    root = json.loads((HERE / selected['cases'][0]['construction']).read_text())
    config = json.loads(next(item['content'] for item in root['files'] if item['path'] == 'config.json'))
    config['supported_case_ids'] = ids
    for camera in config['cameras']:
        camera['pose_strategy'] = 'authored crossing overview' if camera['name'] == 'overview' else \
                                  'source-joined original pedestrian-head and crossing coverage'
        camera['fov_deg'] = 90
    for item in root['files']:
        if item['path'] == 'config.json':
            item['content'] = json.dumps(config, indent=2) + '\n'
        destination = HERE / item['path']
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(item['content'])
    root['files'].append({'path': 'tests/test_signal_head.py',
                          'content': (HERE / 'native/test_signal_head.py').read_text()})
    (HERE / 'tests').mkdir(exist_ok=True)
    (HERE / 'tests/test_signal_head.py').write_text((HERE / 'native/test_signal_head.py').read_text())
    write(HERE / 'construction.json', root)
    print(json.dumps({'selected_cases': len(selected['cases']),
                      'receipt_chains': len(rows),
                      'selected_manifest_sha256': sha(HERE / 'execution-manifest.json')}))


if __name__ == '__main__':
    main()
