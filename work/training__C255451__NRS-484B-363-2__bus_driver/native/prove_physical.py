"""Run three measured saved-source outcomes for each selected bus case."""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = ROOT.parents[1]
MANIFEST = ROOT / 'execution-manifest.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run():
    manifest = json.loads(MANIFEST.read_text())
    scratch = REPO / '.runtime-work/c255451-physical-v1'
    scratch.mkdir(parents=True, exist_ok=True)
    for entry in manifest['cases']:
        condition = entry['case_id'].rsplit('__', 1)[-1]
        original = REPO / '.runtime-work' / ('c255451-recorded-v3-' + condition + '-fixture')
        if not original.is_dir():
            raise ValueError('Source-hashed recorded fixture missing: ' + condition)
        destination = HERE / 'selected' / condition / 'physical'
        destination.mkdir(parents=True, exist_ok=True)
        fixtures = []
        for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
            source = scratch / (condition + '-' + kind)
            if source.exists():
                raise ValueError('Choose fresh physical source output: ' + str(source))
            source.mkdir()
            for filename in ('school_zone_context.json', 'video_frames.jsonl'):
                shutil.copy2(original / filename, source / filename)
            motion = original / 'native_motion.jsonl'
            if kind == 'complete_motion':
                shutil.copy2(motion, source / motion.name)
            elif kind == 'incomplete_motion':
                (source / motion.name).write_text(''.join(motion.read_text().splitlines(keepends=True)[:250]))
            result = destination / (kind + '.json')
            log = destination / (kind + '.log')
            command = [sys.executable, '-B', str(HERE / 'physical_probe.py'),
                       '--fixture', str(source), '--kind', kind, '--output', str(result)]
            outcome = subprocess.run(command, cwd=REPO, text=True, capture_output=True,
                                     env={**os.environ, 'TMPDIR': str(REPO / '.runtime-work')})
            log.write_text((outcome.stdout + outcome.stderr).rstrip() + '\n')
            if outcome.returncode:
                raise ValueError('Physical source test failed: ' + condition + ' ' + kind)
            fixtures.append({'kind': kind, 'command': ' '.join(command), 'exit_code': outcome.returncode,
                             'log': str(log.relative_to(ROOT)), 'log_sha256': sha(log),
                             'result': str(result.relative_to(ROOT)), 'result_sha256': sha(result),
                             'source_sha256': {p.name: sha(p) for p in source.iterdir()}})
        runner = REPO / '.runtime-work' / ('c255451-recorded-v3-' + condition + '-attempt/runner.py')
        processing = REPO / '.runtime-work' / ('c255451-recorded-v3-' + condition + '-processed/v0001/processing.json')
        lifecycle_result = destination / 'lifecycle.json'
        lifecycle_log = destination / 'lifecycle.log'
        lifecycle_command = [sys.executable, '-B', str(HERE / 'lifecycle_probe.py'),
                             '--runner', str(runner), '--processing', str(processing),
                             '--output', str(lifecycle_result)]
        lifecycle_run = subprocess.run(lifecycle_command, cwd=REPO, text=True, capture_output=True,
                                       env={**os.environ, 'TMPDIR': str(REPO / '.runtime-work')})
        lifecycle_log.write_text((lifecycle_run.stdout + lifecycle_run.stderr).rstrip() + '\n')
        if lifecycle_run.returncode:
            raise ValueError('Lifecycle source test failed: ' + condition + ' ' + lifecycle_log.read_text())
        lifecycle = json.loads(lifecycle_result.read_text())
        lifecycle.update({'log': str(lifecycle_log.relative_to(ROOT)),
                          'log_sha256': sha(lifecycle_log),
                          'command': ' '.join(lifecycle_command),
                          'processing_sha256': sha(processing),
                          'runner_sha256': sha(runner)})
        proof = {'case_id': entry['case_id'], 'construction_sha256': entry['construction_sha256'],
                 'fixtures': fixtures, 'lifecycle': lifecycle, 'physical_acceptance_claimed': False}
        proof_path = destination / 'proof.json'
        proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True) + '\n')
        entry['physical_preparation'] = {'receipt': str(proof_path.relative_to(ROOT)),
                                         'sha256': sha(proof_path)}
        temporary = REPO / '.runtime-work/c255451-physical-manifest-next.json'
        temporary.write_text(json.dumps(manifest, indent=2) + '\n')
        temporary.replace(MANIFEST)
        print('physical source outcomes ' + condition, flush=True)


if __name__ == '__main__':
    run()
