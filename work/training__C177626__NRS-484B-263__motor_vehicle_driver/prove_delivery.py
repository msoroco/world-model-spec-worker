"""Run exact-case positive and stale-original-source delivery audit probes."""
from hashlib import sha256
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
AUDIT = ROOT / 'delivery_audit.py'
CHECKS = ['native_source', 'all_participants', 'time_join',
          'full_video_decode', 'actual_pixels', 'physical_completion']


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def run(suffix):
    case = ROOT.name + '__selected_ed45c8e4__condition_' + suffix
    source = REPO / '.runtime-work/c177626'
    attempt = source / ('saved-attempt-' + suffix)
    processing = source / ('saved-processed-' + suffix) / 'v0001/processing.json'
    negative = source / ('saved-processed-' + suffix) / 'v0001/processing-negative.json'
    changed = json.loads(processing.read_text())
    changed['original_source_hashes']['native_samples.jsonl'] = '0' * 64
    negative.write_text(json.dumps(changed, indent=2) + '\n')
    out = ROOT / 'delivery-proof' / ('condition_' + suffix)
    out.mkdir(parents=True, exist_ok=True)
    base = [sys.executable, '-B', str(AUDIT), '--case', case,
            '--attempt', str(attempt), '--diagnostic']
    positive = base + ['--processing', str(processing), '--output',
                       str(source / ('audit-' + suffix + '.json'))]
    negative_command = base + ['--processing', str(negative), '--output',
                               str(source / ('audit-' + suffix + '-negative.json'))]
    good = subprocess.run(positive, cwd=REPO, capture_output=True, text=True)
    bad = subprocess.run(negative_command, cwd=REPO, capture_output=True, text=True)
    expected = 'Original source missing or stale: native_samples.jsonl'
    assert good.returncode == 0, good.stdout + good.stderr
    assert bad.returncode != 0 and expected in bad.stdout + bad.stderr
    goodlog = out / 'positive.log'
    badlog = out / 'negative.log'
    goodlog.write_text((good.stdout + good.stderr).rstrip() + '\n')
    badlog.write_text((bad.stdout + bad.stderr).rstrip() + '\n')
    def relative(path):
        return path.relative_to(ROOT).as_posix()
    def command(args):
        return ' '.join(str(arg) for arg in args).replace(str(REPO) + '/', '')
    return {'case_id': case, 'sets': ['full-train'], 'checks': CHECKS,
            'script': relative(AUDIT), 'script_sha256': digest(AUDIT),
            'command': command(positive), 'test_exit_code': good.returncode,
            'test_log': relative(goodlog), 'test_log_sha256': digest(goodlog),
            'negative_command': command(negative_command),
            'negative_exit_code': bad.returncode,
            'negative_expected_error': expected,
            'negative_log': relative(badlog), 'negative_log_sha256': digest(badlog)}


if __name__ == '__main__':
    manifest_path = ROOT / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        entry['delivery_acceptance'] = run(entry['case_id'][-1])
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print('PASS: A/B exact-case diagnostic delivery audits and stale-source negatives')
