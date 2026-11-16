"""Bind current selected software proofs to exact C111331 delivery cases."""
import hashlib
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def main():
    matrix = read(HERE / 'update043-selected-proof-matrix.json')
    if len(matrix['rows']) != 8 or not all(row['passed'] for row in matrix['rows']):
        raise ValueError('Eight selected CPU chains required before binding')
    plan = read(HERE / 'case-plan.json')
    plan['evidence_review']['reviewer'] = 'portable CPU preparation worker'
    plan['evidence_review']['facts'] = []
    plan['evidence_review']['gaps'] = [
        {'id': suffix + '-original-entry', 'requirement': 'Original Native signal phase at full-body intersection entry',
         'source': 'inputs/' + HERE.name + '/assignment.json',
         'why_existing_insufficient': 'No source-hashed accepted evidence inventory or equivalence receipt supplied.'}
        for suffix in ('reference', 'contrast')]
    for case in plan['cases']:
        case['gap_ids'] = [case['case_id'].removeprefix(HERE.name + '__') + '-original-entry']
    write(HERE / 'case-plan.json', plan)
    manifest_path = HERE / 'execution-manifest.json'
    manifest = read(manifest_path)
    manifest['selection_review']['case_plan_sha256'] = sha(HERE / 'case-plan.json')
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.removeprefix(HERE.name + '__')
        row = next(r for r in matrix['rows'] if r['case_id'] == case and r['candidate_id'] == 'primary')
        entry['negative'] = {'log': row['negative']['path']}
        entry['acquisition'] = {
            'native_body_pose': {'entrypoint': 'runner.py', 'method': 'saved_capture_rows and observed vehicle bounding-box/velocity each Native tick',
                                 'evidence': 'native_samples.jsonl, trace.jsonl and video_frames.jsonl joined by original Native frame'},
            'observed_signal_state': {'entrypoint': 'runner.py', 'method': 'observed governing signal actor state each Native tick',
                                      'evidence': 'native_samples.jsonl signal_actor_id and observed_signal_state'},
            'signal_camera_frame_join': {'entrypoint': 'runner.py', 'method': 'four source-camera frames joined to Native tick',
                                         'evidence': 'video_frames.jsonl and reference_corner.mkv original pixel source'}}
        command = (f'{sys.executable} {ROOT / "runtime.py"} process-saved '
                   f'--manifest {manifest_path} --case {case} --attempt "$SAVED_ATTEMPT" '
                   f'--output "$PROCESSED_OUT" --library {ROOT / "runtime/pipeline/library"} '
                   f'--validator {ROOT / ".runtime-work/decoder-update015-c10316/.lake/build/bin/adapterCheck"}')
        entry['post_capture'] = {'recorded_only': True, 'command': command,
            'feedback_command': 'cat "$PROCESSED_OUT/v0001/feedback.json"',
            'test_exit_code': 0, 'test_log': row['saved_process']['log'],
            'test_log_sha256': row['saved_process']['log_sha256']}
        attempt = ROOT / '.runtime-work' / f'c111331-update043b-{suffix}-primary-compat'
        processed = ROOT / '.runtime-work' / f'c111331-update043b-{suffix}-primary-processed/v0001/processing.json'
        script = HERE / 'delivery_audit.py'
        base = [sys.executable, str(script), '--case', case, '--candidate', 'primary',
                '--attempt', str(attempt), '--processing', str(processed)]
        positive = base + ['--output', str(HERE / f'update043b-{suffix}-delivery-diagnostic.json'), '--diagnostic']
        negative = base + ['--output', str(HERE / f'update043b-{suffix}-delivery-negative.json')]
        positive_log = HERE / f'update043b-{suffix}-delivery-positive.log'
        negative_log = HERE / f'update043b-{suffix}-delivery-negative.log'
        for args, log, expected in ((positive, positive_log, 0), (negative, negative_log, 1)):
            with log.open('w') as stream:
                run = subprocess.run(args, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, timeout=30)
            if run.returncode != expected:
                raise RuntimeError('Delivery audit unexpected exit: ' + log.read_text()[-1000:])
        required_error = 'Original Native signal/body and pixel evidence required'
        if required_error not in negative_log.read_text():
            raise ValueError('Physical negative did not show expected rejection')
        entry['delivery_acceptance'].update({
            'script': 'delivery_audit.py', 'script_sha256': sha(script),
            'command': ' '.join(positive), 'test_exit_code': 0,
            'test_log': positive_log.name, 'test_log_sha256': sha(positive_log),
            'negative_command': ' '.join(negative), 'negative_exit_code': 1,
            'negative_expected_error': required_error,
            'negative_log': negative_log.name, 'negative_log_sha256': sha(negative_log)})
        entry['preparation_status'] = 'selected; all exact CPU construction, compatibility and saved paths passed; physical original pending'
    manifest['comparison_audit'] = {
        'script': 'comparison_audit.py', 'script_sha256': sha(HERE / 'comparison_audit.py'),
        'positive_log': 'update043b-comparison-positive.log',
        'positive_log_sha256': sha(HERE / 'update043b-comparison-positive.log'),
        'fixed_condition_negative_log': 'update043b-comparison-fixed-negative.log',
        'fixed_condition_negative_log_sha256': sha(HERE / 'update043b-comparison-fixed-negative.log'),
        'physical_negative_log': 'update043b-comparison-negative.log',
        'physical_negative_log_sha256': sha(HERE / 'update043b-comparison-negative.log')}
    manifest['status'] = 'selected_cpu_proofs_passed_physical_unverified'
    write(manifest_path, manifest)
    print(json.dumps({'cases_bound': len(manifest['cases']), 'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
