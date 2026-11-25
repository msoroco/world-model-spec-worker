"""Bind current-runtime officer CPU proof matrix to exact selected delivery."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__officer_directed'
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
    probe = read(HERE / 'current-officer-probe-manifest.json')
    if manifest['runtime_manifest_sha256'] != probe['runtime_manifest_sha256']:
        raise ValueError('Officer probe binds another runtime')
    if any(e['case_id'] == CASE for e in manifest['cases']):
        raise ValueError('Officer case already selected')
    entry = probe['cases'][0]
    if entry['case_id'] != CASE:
        raise ValueError('Wrong officer exact case')
    public = read(HERE / 'current-officer-public-proof.json')['results']
    saved = read(HERE / 'current-officer-saved-proof.json')['results']
    pubs = {r['candidate_id']: r for r in public}
    saves = {r['candidate_id']: r for r in saved}
    if set(pubs) != set(CANDIDATES) or set(saves) != set(CANDIDATES):
        raise ValueError('Officer candidate matrix incomplete')
    entry['acquisition'] = dict(manifest['cases'][0]['acquisition'])
    entry['acquisition']['dev.human_direction'] = {
        'entrypoint': 'runner.py',
        'method': 'Record original officer identity, instruction, recipient, timing and reviewer sources with exact Native frame joins',
        'evidence': 'emergency_context.template.json and four original camera streams; instruction content and authority require independent original review'}
    physical = HERE / 'physical-proof/officer_directed/proof.json'
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
            raise ValueError('Officer candidate proof changed: ' + name)
        folder = HERE / 'current-officer-public' / name
        receipt = folder / 'receipt.json'
        analysis = folder / 'analysis.log'
        negative = folder / 'negative.log'
        saved_receipt = HERE / 'current-officer-saved' / (name + '.json')
        if (sha(receipt) != pub['full_receipt_sha256'] or
                sha(analysis) != pub['analysis_log_sha256'] or
                sha(negative) != pub['negative_log_sha256'] or
                sha(saved_receipt) != save['full_receipt_sha256']):
            raise ValueError('Officer returned receipt changed: ' + name)
        offline_source = ROOT / '.runtime-work' / ('c404492-officer-offline-' + name + '-v5') / 'offline.log'
        if 'OK' not in offline_source.read_text():
            raise ValueError('Officer pinned offline proof failed: ' + name)
        offline = HERE / 'current-officer-offline' / (name + '.log')
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
    saved_primary = HERE / 'current-officer-saved/primary.json'
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
