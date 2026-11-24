"""Pinned offline proof after packaging source-bound fallback2 path evaluation."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
OWNER = HERE.parent
ROOT = HERE.parents[2]
MANIFEST = OWNER / 'draft-primary-manifest.json'
PROOF = OWNER / 'integrated-fallback-offline-proof.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_bundle(construction, case_id, candidate_id):
    if construction.get('case_id') != case_id:
        raise ValueError('Exact case identity differs')
    files = {item['path']: item['content'] for item in construction['files']}
    if 'fallback_trigger.py' not in files or 'evaluate_path_trigger' not in files.get('runner.py', ''):
        raise ValueError('Source-bound path trigger not packaged')
    if files['fallback_trigger.py'] != (HERE / 'fallback_trigger.py').read_text():
        raise ValueError('Packaged path evaluator differs from proved source')
    config = json.loads(files['config.json'])
    if config['case_id'] != case_id or config['candidate_id'] != candidate_id:
        raise ValueError('Candidate config identity differs')
    if config['duration_s'] != 30 or config['rate_hz'] != 20:
        raise ValueError('Full source window differs')
    return files


def main():
    manifest = json.loads(MANIFEST.read_text())
    scratch = ROOT / '.runtime-work'
    scratch.mkdir(exist_ok=True)
    run_root = Path(tempfile.mkdtemp(prefix='c228133-integrated-offline-', dir=scratch))
    env = os.environ.copy()
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(run_root / 'pipeline-output')
    env['TMPDIR'] = str(run_root)
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    rows = []
    negative_rejections = []
    for case in manifest['cases']:
        suffix = case['case_id'].rsplit('__', 1)[-1]
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            entry = case if candidate == 'primary' else next(
                item for item in case['candidates'] if item['id'] == candidate)
            construction = OWNER / entry['construction']
            if sha(construction) != entry['construction_sha256']:
                raise ValueError('Manifest construction changed')
            bundle = json.loads(construction.read_text())
            validate_bundle(bundle, case['case_id'], candidate)
            if candidate == 'primary' and suffix == 'reference':
                for label, mutate in (
                    ('missing_trigger_source', lambda c: c['files'].__setitem__(
                        slice(None), [f for f in c['files'] if f['path'] != 'fallback_trigger.py'])),
                    ('changed_trigger_source', lambda c: next(f for f in c['files'] if f['path'] == 'fallback_trigger.py').update(content='pass\n')),
                    ('swapped_case', lambda c: c.update(case_id='other')),
                ):
                    copy = json.loads(json.dumps(bundle))
                    mutate(copy)
                    try:
                        validate_bundle(copy, case['case_id'], candidate)
                    except ValueError:
                        negative_rejections.append(label)
                    else:
                        raise ValueError('Negative bundle accepted: ' + label)
            destination = run_root / (suffix + '-' + candidate)
            cmd = [str(ROOT / '.venv-cpu/bin/python'), str(ROOT / 'runtime.py'),
                   'offline', '--manifest', str(MANIFEST), '--case', case['case_id'],
                   '--output', str(destination), '--python', str(ROOT / '.venv-cpu/bin/python')]
            if candidate != 'primary':
                cmd += ['--candidate', candidate]
            done = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True,
                                  text=True, timeout=300)
            log = OWNER / f'integrated-offline-{suffix}-{candidate}.log'
            log.write_text(done.stdout + done.stderr)
            if done.returncode:
                raise RuntimeError('Pinned offline failed: ' + str(log))
            unit = destination / 'offline.log'
            if not unit.is_file() or 'OK' not in unit.read_text():
                raise ValueError('Materialized CPU unit proof absent')
            rows.append({'case_id': case['case_id'], 'candidate_id': candidate,
                         'construction_sha256': entry['construction_sha256'],
                         'command_log': log.name, 'command_log_sha256': sha(log),
                         'unit_log_sha256': sha(unit), 'exit_code': done.returncode})
    report = {'format': 'c228133-integrated-fallback-offline-v1',
              'manifest_sha256': sha(MANIFEST),
              'fallback_trigger_source_sha256': sha(HERE / 'fallback_trigger.py'),
              'fallback_trigger_negative_proof_sha256': sha(OWNER / 'fallback-trigger-proof.json'),
              'results': rows, 'packaging_negative_rejections': negative_rejections,
              'selected_for_delivery': False,
              'original_native_observed': False}
    PROOF.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'proof_sha256': sha(PROOF), 'offline_checks': len(rows),
                      'packaging_negatives': negative_rejections,
                      'manifest_sha256': report['manifest_sha256']}))


if __name__ == '__main__':
    main()
