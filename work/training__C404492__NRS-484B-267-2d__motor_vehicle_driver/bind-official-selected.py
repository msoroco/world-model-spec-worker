"""Bind the proved official alternatives into the selected partial manifest."""
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


def clean_log(value):
    return '\n'.join(line.rstrip() for line in value.splitlines()).rstrip() + '\n'


def main():
    target = HERE / 'execution-manifest.json'
    manifest = read(target)
    probe = read(HERE / 'current-official-probe-manifest.json')
    public = read(HERE / 'current-official-public-proof.json')
    saved = read(HERE / 'current-official-saved-proof.json')
    pubs = {(r['case_id'], r['candidate_id']): r for r in public['results']}
    saves = {(r['case_id'], r['candidate_id']): r for r in saved['results']}
    if len(pubs) != 6 or len(saves) != 6 or not all(
            r['passed'] for r in (*pubs.values(), *saves.values())):
        raise ValueError('Official candidate proof matrix incomplete')
    if manifest['runtime_manifest_sha256'] != probe['runtime_manifest_sha256']:
        raise ValueError('Official probe binds another runtime')
    originals = [entry for entry in manifest['cases']
                 if entry['case_id'].endswith(('__controlled_1', '__controlled_2'))]
    if len(originals) != 2:
        raise ValueError('Expected two previously selected controlled cases')
    for entry in probe['cases']:
        case_id = entry['case_id']
        suffix = case_id.rsplit('__', 1)[-1]
        entry['acquisition'] = {
            'drv.responding_emergency': {
                'entrypoint': 'runner.py',
                'method': 'Record regulatory vehicle identity, original poses, travel and flashing phase per Native frame',
                'evidence': 'vehicle_poses.jsonl and regulatory_vehicle_context.template.json; authority and equipment need independent original review'},
            'rel.same_direction': {
                'entrypoint': 'runner.py',
                'method': 'Read observed lane waypoints and actor headings with original frame times',
                'evidence': 'vehicle_poses.jsonl joined to video_frames.jsonl and reviewed lane context'},
            'rel.longitudinal_overlap': {
                'entrypoint': 'finalize.py',
                'method': 'Project original body extents onto the observed travel axis and retain overlapping frames',
                'evidence': 'vehicle_poses.jsonl, trace.jsonl and channels/rel.longitudinal_overlap.jsonl'},
            'drv.overtaking': {
                'entrypoint': 'finalize.py',
                'method': 'Track signed relative order separately from body overlap',
                'evidence': 'vehicle_poses.jsonl and channels/drv.overtaking.jsonl'},
            'rel.ahead_behind_in_lane': {
                'entrypoint': 'finalize.py',
                'method': 'Report signed relative order and distinct lane identities',
                'evidence': 'vehicle_poses.jsonl and channels/rel.ahead_behind_in_lane.jsonl'},
            'kin.velocity': {
                'entrypoint': 'runner.py',
                'method': 'Retain observed actor velocities and ego trace at original Native frame and time',
                'evidence': 'vehicle_poses.jsonl and trace.jsonl joined to video_frames.jsonl'},
            'dev.human_direction': {
                'entrypoint': 'finalize.py',
                'method': 'Carry source-reviewed officer direction with unknown preserved',
                'evidence': 'officer_direction_context review and channels/context-review.json'}}
        physical = HERE / 'physical-proof' / suffix / 'proof.json'
        entry['physical_preparation'] = {'receipt': rel(physical), 'sha256': sha(physical)}
        entry['native_handoff'] = {
            'python_env_var': 'CARLA_PYTHON', 'host_env_var': 'CARLA_HOST',
            'port_env_var': 'CARLA_PORT', 'survey_env_var': 'SCENARIO_NATIVE_SURVEY'}
        for candidate in (entry, *entry['candidates']):
            cid = candidate['id']
            key = (case_id, cid)
            pub, save = pubs[key], saves[key]
            if pub['construction_sha256'] != candidate['construction_sha256']:
                raise ValueError('Public construction hash differs: ' + str(key))
            receipt_dir = HERE / 'current-official-public' / (suffix + '-' + cid + ('-v2' if cid == 'primary' else ''))
            receipt = receipt_dir / 'receipt.json'
            analysis = receipt_dir / 'analysis.log'
            negative = receipt_dir / 'negative.log'
            saved_receipt = HERE / save['receipt']
            if (sha(receipt) != pub['full_receipt_sha256'] or
                    sha(analysis) != save['analysis_log_sha256'] or
                    sha(negative) != pub['negative_log_sha256'] or
                    sha(saved_receipt) != save['full_receipt_sha256']):
                raise ValueError('Returned proof changed: ' + str(key))
            output = ROOT / '.runtime-work' / 'c404492-official-bind' / (suffix + '-' + cid)
            output.parent.mkdir(parents=True, exist_ok=True)
            command = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
                       'offline', '--manifest', str(HERE / 'current-official-probe-manifest.json'),
                       '--case', case_id, '--candidate', cid, '--output', str(output),
                       '--python', str(ROOT / '.venv-cpu/bin/python')]
            environment = dict(os.environ)
            environment['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work' / 'c404492-official-bind')
            completed = subprocess.run(command, cwd=ROOT, env=environment,
                                       capture_output=True, text=True)
            if completed.returncode:
                raise ValueError('Official offline failed: ' + str(key) + '\n' + completed.stdout + completed.stderr)
            log = HERE / 'current-official-offline' / (suffix + '-' + cid + '.log')
            log.parent.mkdir(exist_ok=True)
            log.write_text(clean_log(completed.stdout + completed.stderr))
            candidate['offline'] = {
                'command': '.venv-cpu/bin/python runtime.py offline --manifest work/' + HERE.name +
                    '/execution-manifest.json --case ' + case_id + ' --candidate ' + cid +
                    ' --output "$OFFLINE_OUT" --python .venv-cpu/bin/python',
                'exit_code': 0, 'construction_sha256': candidate['construction_sha256'],
                'log': rel(log), 'log_sha256': sha(log)}
            candidate['compatibility'] = {
                'receipt': rel(receipt), 'sha256': sha(receipt),
                'log': rel(analysis), 'negative_log': rel(negative)}
            candidate['negative'] = {'log': rel(negative)}
            candidate['saved_processing'] = {
                'receipt': rel(saved_receipt), 'sha256': sha(saved_receipt)}
        primary = HERE / 'current-official-saved' / (suffix + '-primary.json')
        entry['post_capture'] = {
            'recorded_only': True,
            'command': '.venv-cpu/bin/python runtime.py process-saved --manifest work/' +
                HERE.name + '/execution-manifest.json --case ' + case_id +
                ' --attempt "$SAVED_ATTEMPT" --output "$PROCESSED_OUT"' +
                ' --library runtime/library --validator "$DECODER"',
            'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
            'test_exit_code': 0, 'test_log': rel(primary), 'test_log_sha256': sha(primary)}
    manifest['cases'] = originals + probe['cases']
    manifest['status'] = 'partial_selected_cpu_proofs_bound'
    manifest['delivery_ready'] = False
    target.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'selected_cases': len(manifest['cases']),
                      'proved_official_candidates': len(pubs),
                      'manifest_sha256': sha(target), 'delivery_ready': False}))


if __name__ == '__main__':
    main()
