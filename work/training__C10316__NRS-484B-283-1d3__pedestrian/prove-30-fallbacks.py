"""Run public 600-frame CPU compatibility and saved processing for draft fallbacks."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'draft-execution-manifest.json'
VALIDATOR = ROOT / '.runtime-work/c10316-current-decoder/.lake/build/bin/adapterCheck'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, log, env):
    with log.open('w') as stream:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream,
                                stderr=subprocess.STDOUT, timeout=600, check=False)
    if result.returncode:
        raise RuntimeError(f'{command[2]} failed with {result.returncode}: {log}')
    return sha(log)


def main():
    env = os.environ.copy()
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c10316-fallback-pipeline')
    env['TMPDIR'] = str(ROOT / '.runtime-work/c10316-fallback-tmp')
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    Path(env['TMPDIR']).mkdir(parents=True, exist_ok=True)
    records = []
    for suffix in ('controlled_1', 'controlled_2'):
        case_id = HERE.name + '__' + suffix
        for candidate in ('fallback1', 'fallback2', 'fallback3'):
            name = f'{suffix}-{candidate}'
            output = ROOT / '.runtime-work/c10316-30-fallbacks' / name / 'compat'
            saved = ROOT / '.runtime-work/c10316-30-fallbacks' / name / 'saved'
            compatibility_log = HERE / f'compat-30-{name}.log'
            saved_log = HERE / f'saved-30-{name}.log'
            common = ['--manifest', str(MANIFEST), '--case', case_id]
            common_tools = ['--library', str(ROOT / 'runtime/pipeline/library'),
                            '--validator', str(VALIDATOR)]
            compatibility_cmd = [sys.executable, str(ROOT / 'runtime.py'), 'compatibility',
                                 *common, '--candidate', candidate, '--output', str(output),
                                 *common_tools]
            compatibility_log_sha = run(compatibility_cmd, compatibility_log, env)
            receipt = json.loads((output / 'compatibility.json').read_text())
            assert receipt['passed'] is True and receipt['candidate_id'] == candidate
            assert receipt['negative_removed'] == 'no-countdown-samples.jsonl'
            assert receipt['negative_log_sha256'] == sha(output / 'negative-analysis.log')
            saved_cmd = [sys.executable, str(ROOT / 'runtime.py'), 'process-saved',
                         *common, '--attempt', str(output), '--output', str(saved),
                         *common_tools]
            saved_log_sha = run(saved_cmd, saved_log, env)
            processing = json.loads((saved / 'v0001/processing.json').read_text())
            assert processing['passed'] is True and processing['recorded_only'] is True
            assert processing['candidate_id'] == candidate
            assert processing['timestamp_joins']['frames'] == 600
            assert processing['final_video_checks']['frames'] == 600
            assert processing['physical_acceptance_claimed'] is False
            assert processing['legal_acceptance_claimed'] is False
            records.append({
                'case_id': case_id, 'candidate': candidate, 'source_kind': 'synthetic_scene_request',
                'compatibility_command': compatibility_cmd, 'compatibility_log': compatibility_log.name,
                'compatibility_log_sha256': compatibility_log_sha,
                'compatibility_receipt': str((output / 'compatibility.json').relative_to(ROOT)),
                'compatibility_receipt_sha256': sha(output / 'compatibility.json'),
                'saved_command': saved_cmd, 'saved_log': saved_log.name,
                'saved_log_sha256': saved_log_sha,
                'saved_receipt': str((saved / 'v0001/processing.json').relative_to(ROOT)),
                'saved_receipt_sha256': sha(saved / 'v0001/processing.json'),
                'construction_sha256': receipt['construction_sha256'],
                'negative_log_sha256': receipt['negative_log_sha256'],
            })
            print(name, 'compatibility and saved processing pass', flush=True)
    summary = {'format': 'c10316-current-30-second-fallback-cpu-proof',
               'manifest_sha256': sha(MANIFEST), 'selected': False,
               'physical_signal_observed': False, 'records': records}
    (HERE / 'fallback-30-proof.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(sha(HERE / 'fallback-30-proof.json'))


if __name__ == '__main__':
    main()
