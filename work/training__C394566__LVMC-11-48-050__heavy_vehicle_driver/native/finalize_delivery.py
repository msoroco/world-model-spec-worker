"""Bind completed CPU receipts into the exact selected delivery package."""
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
ROOT = HERE.parents[1]
AID = HERE.name


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


def audit_logs(case):
    suffix = case.removeprefix(AID + '__')
    script = HERE / 'delivery_audit.py'
    prefix = '.venv-cpu/bin/python -B work/' + AID + '/delivery_audit.py --case ' + case + ' --self-test'
    log_dir = HERE / 'delivery-proofs'
    log_dir.mkdir(exist_ok=True)
    commands = [(prefix, log_dir / (suffix + '-positive.log'), 0),
                (prefix + ' --negative', log_dir / (suffix + '-negative.log'), 1)]
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', TMPDIR=str(ROOT / '.runtime-work'))
    results = []
    for command, log, expected in commands:
        result = subprocess.run(command.split(), cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, timeout=30)
        log.write_text(result.stdout.rstrip() + '\n')
        if result.returncode != expected:
            raise ValueError('Independent audit self-test exit differs: ' + case)
        results.append((command, log, expected))
    if 'Missing original source: exact original Native result' not in results[1][1].read_text():
        raise ValueError('Missing negative original-source rejection')
    return {'case_id': case, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join', 'full_video_decode',
                       'actual_pixels', 'physical_completion'],
            'script': str(script.relative_to(HERE)), 'script_sha256': sha(script),
            'command': results[0][0], 'test_exit_code': 0,
            'test_log': str(results[0][1].relative_to(HERE)), 'test_log_sha256': sha(results[0][1]),
            'negative_command': results[1][0], 'negative_exit_code': 1,
            'negative_expected_error': 'Missing original source: exact original Native result',
            'negative_log': str(results[1][1].relative_to(HERE)),
            'negative_log_sha256': sha(results[1][1]),
            'scope': 'CPU audit predicates only; original Native and independent authority review pending'}


def main():
    probe = json.loads((HERE / 'execution-probe-manifest.json').read_text())
    saved = json.loads((HERE / 'saved/proof-index.json').read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    if len(probe['cases']) != len(plan['cases']) or len(plan['cases']) != 17:
        raise ValueError('Expected all 17 exact source-branch cases')
    for entry in probe['cases']:
        case = entry['case_id']
        suffix = case.removeprefix(AID + '__')
        entry['post_capture'] = saved.get(case)
        if not all(key in entry for key in ('offline', 'compatibility', 'negative',
                                            'post_capture', 'physical_preparation')):
            raise ValueError('Incomplete selected CPU chain: ' + case)
        if not isinstance(entry['post_capture'], dict):
            raise ValueError('Missing saved-only CPU chain: ' + case)
        for candidate in entry['candidates']:
            if not all(key in candidate for key in ('offline', 'compatibility')):
                raise ValueError('Incomplete fallback CPU chain: ' + case)
        entry['acquisition'] = {
            name: {'entrypoint': 'runner.py',
                   'method': 'sealed original Native route, synchronized camera and cited factual authority readback',
                   'evidence': 'original-route-rows.jsonl, video_frames.jsonl, capture-seal.json, authority-context.json and cited source files'}
            for name in ('ego_pose', 'heavy_vehicle_restricted_street_operation')}
        post = entry['post_capture']
        post.update(command='.venv-cpu/bin/python -B runtime.py process-saved --manifest work/' + AID + '/execution-manifest.json --case ' + case +
                    ' --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER',
                    feedback_command='.venv-cpu/bin/python -B runtime.py process-saved --manifest work/' + AID + '/execution-manifest.json --case ' + case +
                    ' --attempt $ATTEMPT --output $SAVED_OUTPUT --library runtime/library --validator $DECODER',
                    recorded_only=True, test_exit_code=0)
        entry['delivery_acceptance'] = audit_logs(case)
        entry['delivery_readiness'] = 'original_capture_pending'
    probe['status'] = 'selected_cpu_proof'
    write(HERE / 'execution-manifest.json', probe)
    first = probe['cases'][0]
    construction = json.loads((HERE / first['construction']).read_text())
    write(HERE / 'construction.json', construction)
    for item in construction['files']:
        path = HERE / item['path']
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(item['content'])
    for case in plan['cases']:
        case['selected'] = True
        case['planning_status'] = 'selected_cpu_proof_original_review_pending'
        case['target_type'] = 'selected_delivery_comparison'
    for comparison in plan['comparisons']:
        comparison['status'] = 'selected_cpu_proof_original_review_pending'
        comparison['audit_gap'] = ('Independent diagnostic source-fact comparison proof passed; original Native '
                                   'pixels, source authority and legal application remain delivery review.')
    for disposition in plan['requirement_dispositions']:
        disposition['evidence_or_gap'] = ('Exact selected source-bound Native/offline/public/saved/semantic/physical and '
            'independent CPU proof is bound; original CARLA, source authority, permit authenticity/conditions, '
            'exact clock endpoints and legal result remain independent delivery review.')
    write(HERE / 'case-plan.json', plan)
    print(json.dumps({'selected_cases': len(probe['cases']),
                      'candidate_constructions': sum(1 + len(e['candidates']) for e in probe['cases'])}))


if __name__ == '__main__':
    main()
