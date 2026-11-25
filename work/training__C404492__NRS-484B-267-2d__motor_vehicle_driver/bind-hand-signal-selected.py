"""Bind current-runtime driver hand-signal CPU proof matrix to exact selected delivery."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__preparing_hand_signal'
CANDIDATES = ('primary', 'fallback1', 'fallback2')


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path):
    return path.relative_to(HERE).as_posix()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    target = HERE / 'execution-manifest.json'
    manifest = read(target)
    probe = read(HERE / 'current-hand-signal-probe-manifest.json')
    if manifest['runtime_manifest_sha256'] != probe['runtime_manifest_sha256']:
        raise ValueError('Hand signal probe binds another runtime')
    if any(e['case_id'] == CASE for e in manifest['cases']):
        raise ValueError('Hand signal case already selected')
    entry = probe['cases'][0]
    if entry['case_id'] != CASE:
        raise ValueError('Wrong hand signal exact case')
    public = read(HERE / 'current-hand-signal-public-proof.json')['rows']
    saved = read(HERE / 'current-hand-signal-saved-proof.json')['rows']
    pubs = {r['candidate_id']: r for r in public}
    saves = {r['candidate_id']: r for r in saved}
    if set(pubs) != set(CANDIDATES) or set(saves) != set(CANDIDATES):
        raise ValueError('Hand signal candidate matrix incomplete')
    entry['acquisition'] = dict(manifest['cases'][0]['acquisition'])
    entry['acquisition']['dev.human_direction'] = {
        'entrypoint': 'runner.py',
        'method': 'Record source-driver hand signal actor identity, window geometry, original frame interval and independent pixel review',
        'evidence': 'vehicle_poses.jsonl, emergency_context.template.json and four original camera streams'}
    physical = HERE / 'physical-proof/preparing_hand_signal/canonical-proof.json'
    entry['physical_preparation'] = {'receipt': rel(physical), 'sha256': sha(physical)}
    entry['native_handoff'] = dict(manifest['cases'][0]['native_handoff'])
    for candidate in (entry, *entry['candidates']):
        name = candidate['id']
        pub = pubs[name]
        save = saves[name]
        construction = HERE / candidate['construction']
        if (sha(construction) != candidate['construction_sha256'] or
                pub['construction_sha256'] != candidate['construction_sha256'] or
                not save['recorded_only'] or not save['originals_preserved']):
            raise ValueError('Hand signal candidate proof changed: ' + name)
        folder = HERE / 'current-hand-signal-public' / name
        receipt = folder / 'receipt.json'
        analysis = folder / 'analysis.log'
        negative = folder / 'negative.log'
        saved_receipt = HERE / 'current-hand-signal-saved' / (name + '.json')
        if (sha(receipt) != pub['receipt_sha256'] or
                sha(analysis) != pub['analysis_log_sha256'] or
                sha(negative) != pub['negative_log_sha256'] or
                sha(saved_receipt) != save['receipt_sha256']):
            raise ValueError('Hand signal returned receipt changed: ' + name)
        offline_source = HERE / 'current-hand-signal-offline' / name / 'offline.log'
        if 'OK' not in offline_source.read_text():
            raise ValueError('Hand signal pinned offline proof failed: ' + name)
        offline = HERE / 'current-hand-signal-offline' / (name + '.log')
        offline.parent.mkdir(exist_ok=True)
        offline.write_text('\n'.join(line.rstrip() for line in offline_source.read_text().splitlines()).rstrip() + '\n')
        candidate['offline'] = {
            'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + HERE.name +
                '/execution-manifest.json --case ' + CASE + ' --candidate ' + name +
                ' --output "$OFFLINE_OUT" --python .venv-cpu/bin/python',
            'exit_code': 0, 'construction_sha256': candidate['construction_sha256'],
            'log': rel(offline), 'log_sha256': sha(offline)}
        candidate['compatibility'] = {'receipt': rel(receipt), 'sha256': sha(receipt),
                                      'log': rel(analysis), 'negative_log': rel(negative)}
        candidate['negative'] = {'log': rel(negative)}
        candidate['saved_processing'] = {'receipt': rel(saved_receipt),
                                         'sha256': sha(saved_receipt)}
    saved_primary = HERE / 'current-hand-signal-saved/primary.json'
    entry['post_capture'] = {
        'recorded_only': True,
        'command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' + HERE.name +
                   '/execution-manifest.json --case ' + CASE +
                   ' --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT"' +
                   ' --library runtime/library --validator "$DECODER"',
        'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
        'test_exit_code': 0, 'test_log': rel(saved_primary),
        'test_log_sha256': sha(saved_primary)}
    manifest['cases'].append(entry)
    manifest['status'] = 'partial_selected_cpu_proofs_bound'
    manifest['delivery_ready'] = False
    write(target, manifest)
    print(json.dumps({'case_id': CASE, 'selected_cases': len(manifest['cases']),
                      'manifest_sha256': sha(target), 'delivery_ready': False}))


if __name__ == '__main__':
    main()
