"""Bind four independent diagnostic and original-negative speed delivery audits."""
import argparse
import hashlib
import json
import shlex
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CHECKS = ('native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(tag):
    path = HERE / 'execution-manifest.json'
    manifest = json.loads(path.read_text())
    if len(manifest['cases']) != 2:
        raise ValueError('Two exact selected signal cases required')
    script = HERE / 'delivery_audit.py'
    for case in manifest['cases']:
        case_id = case['case_id']
        suffix = case_id.removeprefix(HERE.name + '__')
        base = ROOT / '.runtime-work/c111331-update400-selected-matrix/44142a632d03' / suffix / 'primary'
        common = [sys.executable, str(script), '--case', case_id,
                  '--candidate', 'primary', '--attempt', str(base / 'compatibility'),
                  '--processing', str(base / 'saved/v0001/processing.json')]
        diagnostic = HERE / f'{tag}-{suffix}-delivery-diagnostic.json'
        negative = HERE / f'{tag}-{suffix}-delivery-negative.json'
        positive = common + ['--output', str(diagnostic), '--diagnostic']
        original = common + ['--output', str(negative)]
        logs = []
        for kind, command in (('positive', positive), ('negative', original)):
            log = HERE / f'{tag}-{suffix}-delivery-{kind}.log'
            run = subprocess.run(command, cwd=ROOT, text=True,
                                 stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                 timeout=180)
            log.write_text(run.stdout)
            logs.append((run.returncode, log))
        (positive_rc, positive_log), (negative_rc, negative_log) = logs
        if (positive_rc or not diagnostic.is_file() or
                json.loads(diagnostic.read_text()).get('passed') is not True or
                negative_rc == 0 or
                'Original Native signal/body and pixel evidence required' not in negative_log.read_text()):
            raise ValueError('Delivery source separation failed: ' + suffix)
        case['delivery_acceptance'] = {
            'case_id': case_id, 'sets': ['demo-train', 'full-train'],
            'checks': list(CHECKS), 'script': script.name,
            'script_sha256': sha(script), 'command': shlex.join(positive),
            'test_exit_code': 0, 'test_log': positive_log.name,
            'test_log_sha256': sha(positive_log),
            'negative_command': shlex.join(original),
            'negative_exit_code': negative_rc,
            'negative_expected_error': 'Original Native signal/body and pixel evidence required',
            'negative_log': negative_log.name,
            'negative_log_sha256': sha(negative_log)}
        print(suffix, 'delivery diagnostic and original rejection passed', flush=True)
    manifest['status'] = 'selected_cpu_delivery_bound_current_runtime'
    path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'selected_cases': 2, 'manifest_sha256': sha(path),
                      'original_recordings_accepted': 0}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', required=True)
    args = parser.parse_args()
    main(args.tag)
