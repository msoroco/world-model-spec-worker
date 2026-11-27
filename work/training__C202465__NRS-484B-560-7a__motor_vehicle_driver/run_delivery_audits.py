"""Run selected diagnostic delivery audits and source-removal negatives."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
AUDIT = HERE / 'delivery_audit.py'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    for entry in manifest['cases']:
        case = entry['case_id']
        suffix = case.rsplit('__', 1)[1]
        proofdir = HERE / 'proofs' / suffix
        saved = proofdir / 'saved-processing.json'
        receipt = json.loads(saved.read_text())
        stage = Path(receipt['version'])
        attempt = stage.parent.parent / (suffix + '-attempt')
        processing = stage / 'processing.json'
        out = proofdir / 'delivery-diagnostic.json'
        command = [sys.executable, '-B', str(AUDIT), '--case', case,
                   '--attempt', str(attempt), '--processing', str(processing),
                   '--output', str(out), '--diagnostic']
        positive = subprocess.run(command, cwd=REPO, text=True, capture_output=True,
                                  env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        poslog = proofdir / 'delivery-positive.log'
        poslog.write_text((positive.stdout + positive.stderr).rstrip() + '\n')
        if positive.returncode:
            raise RuntimeError(f'{suffix} positive: {positive.stderr[-1000:]}')
        negative = REPO / '.runtime-work' / 'c202465-delivery-negative' / suffix
        if negative.exists():
            shutil.rmtree(negative)
        shutil.copytree(attempt, negative, copy_function=os.link)
        removed = negative / 'rail-review/rail-geometry.json'
        removed.unlink()
        negative_output = REPO / '.runtime-work' / 'c202465-delivery-negative' / (suffix + '.json')
        bad_command = [sys.executable, '-B', str(AUDIT), '--case', case,
                       '--attempt', str(negative), '--processing', str(processing),
                       '--output', str(negative_output), '--diagnostic']
        failed = subprocess.run(bad_command, cwd=REPO, text=True, capture_output=True,
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1'})
        neglog = proofdir / 'delivery-negative.log'
        neglog.write_text((failed.stdout + failed.stderr).rstrip() + '\n')
        expected = 'Original source missing or stale: rail-review/rail-geometry.json'
        if failed.returncode == 0 or expected not in neglog.read_text():
            raise RuntimeError(f'{suffix} negative not rejected as expected')
        entry['delivery_acceptance'] = {
            'case_id': case, 'sets': ['full-train'],
            'checks': ['native_source', 'all_participants', 'time_join',
                       'full_video_decode', 'actual_pixels', 'physical_completion'],
            'script': AUDIT.name, 'script_sha256': sha(AUDIT),
            'command': ' '.join(command), 'test_exit_code': 0,
            'test_log': str(poslog.relative_to(HERE)), 'test_log_sha256': sha(poslog),
            'negative_command': ' '.join(bad_command), 'negative_exit_code': failed.returncode,
            'negative_expected_error': expected,
            'negative_log': str(neglog.relative_to(HERE)),
            'negative_log_sha256': sha(neglog)}
        print(suffix, sha(out))
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print('manifest', sha(manifest_path))


if __name__ == '__main__':
    main()
