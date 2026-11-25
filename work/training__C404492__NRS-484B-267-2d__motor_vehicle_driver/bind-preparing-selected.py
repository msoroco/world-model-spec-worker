"""Bind the proved visible-movement case into the selected CPU manifest."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read(path):
    return json.loads(path.read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path):
    return path.relative_to(HERE).as_posix()


def main():
    target = HERE / 'execution-manifest.json'
    manifest = read(target)
    probe = read(HERE / 'current-preparing-probe-manifest.json')
    entry = probe['cases'][0]
    case = entry['case_id']
    if manifest['runtime_manifest_sha256'] != probe['runtime_manifest_sha256']:
        raise ValueError('Probe binds another runtime')
    if any(item['case_id'] == case for item in manifest['cases']):
        raise ValueError('Preparation case is already selected')
    public = read(HERE / 'current-preparing-public-matrix-proof.json')
    saved = read(HERE / 'current-preparing-saved-matrix-proof.json')
    pubs = {item['candidate_id']: item for item in public['candidates']}
    saves = {item['candidate_id']: item for item in saved['candidates']}
    if set(pubs) != {'primary', 'fallback1', 'fallback2'} or set(saves) != set(pubs):
        raise ValueError('Preparation proof matrix incomplete')
    if public['case_id'] != case or saved['case_id'] != case:
        raise ValueError('Preparation proof case changed')
    entry['acquisition'] = dict(manifest['cases'][0]['acquisition'])
    entry['acquisition']['drv.responding_emergency'] = {
        'entrypoint': 'runner.py',
        'method': 'Record original vehicle identity, stopped phase, visibly moving phase and later travel on every Native frame',
        'evidence': 'vehicle_poses.jsonl and emergency_context.template.json; preparation, authorization, lamps and pixels require independent original review'}
    physical = HERE / 'physical-proof/preparing_movement/canonical-proof.json'
    entry['physical_preparation'] = {'receipt': rel(physical), 'sha256': sha(physical)}
    entry['native_handoff'] = dict(manifest['cases'][0]['native_handoff'])
    for candidate in (entry, *entry['candidates']):
        name = candidate['id']
        source = HERE / candidate['construction']
        if sha(source) != candidate['construction_sha256']:
            raise ValueError('Preparation construction changed: ' + name)
        pub_folder = HERE / 'current-preparing-public' / name
        receipt = pub_folder / 'receipt.json'
        analysis = pub_folder / 'analysis.log'
        negative = pub_folder / 'negative.log'
        saved_receipt = HERE / 'current-preparing-saved' / name / 'receipt.json'
        if (sha(receipt) != pubs[name]['receipt_sha256'] or
                sha(saved_receipt) != saves[name]['receipt_sha256'] or
                not pubs[name]['missing_source_negative'] or
                not saves[name]['recorded_only'] or
                not saves[name]['originals_preserved']):
            raise ValueError('Preparation proof changed: ' + name)
        output = ROOT / '.runtime-work/c404492-preparing-bind' / name
        output.parent.mkdir(parents=True, exist_ok=True)
        command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
                   'offline', '--manifest', str(HERE / 'current-preparing-probe-manifest.json'),
                   '--case', case, '--candidate', name, '--output', str(output),
                   '--python', str(ROOT / '.venv-cpu/bin/python')]
        environment = dict(os.environ)
        environment['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c404492-preparing-bind')
        environment['TMPDIR'] = str(ROOT / '.runtime-work/c404492-preparing-bind')
        completed = subprocess.run(command, cwd=ROOT, env=environment,
                                   capture_output=True, text=True)
        if completed.returncode:
            raise ValueError('Preparation offline failed: ' + name + '\n' + completed.stdout + completed.stderr)
        log = HERE / 'current-preparing-offline' / (name + '.log')
        log.parent.mkdir(exist_ok=True)
        log.write_text('\n'.join(line.rstrip() for line in
                                 (completed.stdout + completed.stderr).splitlines()).rstrip() + '\n')
        candidate['offline'] = {
            'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + HERE.name +
                       '/execution-manifest.json --case ' + case + ' --candidate ' + name +
                       ' --output "$OFFLINE_OUT" --python .venv-cpu/bin/python',
            'exit_code': 0, 'construction_sha256': candidate['construction_sha256'],
            'log': rel(log), 'log_sha256': sha(log)}
        candidate['compatibility'] = {'receipt': rel(receipt), 'sha256': sha(receipt),
                                      'log': rel(analysis), 'negative_log': rel(negative)}
        candidate['negative'] = {'log': rel(negative)}
        candidate['saved_processing'] = {'receipt': rel(saved_receipt), 'sha256': sha(saved_receipt)}
    primary = HERE / 'current-preparing-saved/primary/receipt.json'
    entry['post_capture'] = {
        'recorded_only': True,
        'command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' + HERE.name +
                   '/execution-manifest.json --case ' + case +
                   ' --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT"' +
                   ' --library runtime/library --validator "$DECODER"',
        'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
        'test_exit_code': 0, 'test_log': rel(primary), 'test_log_sha256': sha(primary)}
    manifest['cases'].append(entry)
    manifest['status'] = 'partial_selected_cpu_proofs_bound'
    manifest['delivery_ready'] = False
    target.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'selected_cases': len(manifest['cases']),
                      'manifest_sha256': sha(target), 'delivery_ready': False}))


if __name__ == '__main__':
    main()
