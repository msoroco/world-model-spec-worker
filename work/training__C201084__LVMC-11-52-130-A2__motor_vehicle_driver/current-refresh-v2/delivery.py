"""Reprove exact selected delivery audits against current diagnostic sources."""
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess

HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
REPO = PACKAGE.parents[1]
SCRATCH = REPO / '.runtime-work/c201084-refresh-v2'
MANIFEST = PACKAGE / 'execution-manifest.json'
SCRIPT = PACKAGE / 'delivery_audit.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, log):
    env = {**os.environ, 'PYTHONDONTWRITEBYTECODE': '1',
           'TMPDIR': str(SCRATCH / 'tmp'),
           'SCENARIO_PIPELINE_OUTPUT_ROOT': str(SCRATCH)}
    with log.open('w') as stream:
        return subprocess.run(command, cwd=REPO, env=env, stdout=stream,
                              stderr=subprocess.STDOUT, check=False).returncode


def main():
    manifest = json.loads(MANIFEST.read_text())
    for entry in manifest['cases']:
        group = entry['case_id'].rsplit('__', 1)[-1]
        attempt = SCRATCH / (group + '-primary-compat')
        processing = SCRATCH / (group + '-primary-saved/v0001/processing.json')
        positive = HERE / (group + '-delivery-positive.json')
        rejected = SCRATCH / (group + '-delivery-rejected.json')
        positive_log = HERE / (group + '-delivery-positive.log')
        negative_log = HERE / (group + '-delivery-negative.log')
        base = [str(REPO / '.venv-cpu/bin/python'), str(SCRIPT),
                '--case', entry['case_id'], '--candidate', 'primary',
                '--attempt', str(attempt), '--processing', str(processing)]
        command = base + ['--output', str(positive), '--diagnostic']
        negative_command = base + ['--output', str(rejected)]
        if not positive.exists():
            assert run(command, positive_log) == 0, group + ' positive failed'
        else:
            assert positive_log.is_file(), group + ' positive log missing'
        audit = json.loads(positive.read_text())
        assert audit['accepted'] is False and audit['diagnostic_only'] is True
        assert not rejected.exists()
        code = run(negative_command, negative_log)
        assert code != 0 and 'Original Native source required' in negative_log.read_text()
        receipt = entry['delivery_acceptance']
        receipt.update({'command': shlex.join(command),
                        'negative_command': shlex.join(negative_command),
                        'script': SCRIPT.relative_to(PACKAGE).as_posix(),
                        'script_sha256': sha(SCRIPT),
                        'test_exit_code': 0,
                        'test_log': positive_log.relative_to(PACKAGE).as_posix(),
                        'test_log_sha256': sha(positive_log),
                        'negative_exit_code': code,
                        'negative_expected_error': 'Original Native source required',
                        'negative_log': negative_log.relative_to(PACKAGE).as_posix(),
                        'negative_log_sha256': sha(negative_log),
                        'proof_scope': 'Current-runtime synthetic diagnostic positive and original Native rejection; no physical or legal acceptance'})
        print(group, sha(positive), flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n')
    print('manifest', sha(MANIFEST))


if __name__ == '__main__':
    main()
