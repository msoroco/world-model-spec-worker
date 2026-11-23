"""Run one current source-only rider fixture through its saved finalizer."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CASE = HERE.name + '__rider_bicycle_clear'
RECIPE = HERE / 'rider-v2-bicycle-clear-primary/fixture-recipe.json'
CONSTRUCTION = HERE / 'draft-rider-cases/rider_bicycle_clear/primary/construction.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, env):
    return subprocess.run(command, cwd=ROOT, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          timeout=300)


def materialize(attempt, env):
    response = run([sys.executable, str(ROOT/'runtime.py'), 'fixture',
                    '--recipe', str(RECIPE), '--output', str(attempt)], env)
    if response.returncode:
        raise AssertionError(response.stdout)
    bundle = json.loads(CONSTRUCTION.read_text())
    config = next(item['content'] for item in bundle['files']
                  if item['path'] == 'config.json')
    (attempt/'config.json').write_text(config)
    for source in (HERE/'native').glob('*.py'):
        shutil.copy2(source, attempt/source.name)
    assert not (attempt/'channels').exists()
    return json.loads(response.stdout)


def finalize(attempt, env):
    return run([sys.executable, str(attempt/'finalize_rider.py'),
                '--attempt', str(attempt), '--output',
                str(attempt/'analysis-report.json')], env)


def main():
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(
        ROOT/'.runtime-work/c10052-rider-current-saved')
    env['PYTHONPATH'] = str(ROOT/'runtime/pipeline/scenario_pipeline') + (
        os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    (ROOT/'.runtime-work').mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(dir=ROOT/'.runtime-work',
                                     prefix='c10052-rider-current-saved-') as temporary:
        scratch = Path(temporary)
        positive = scratch/'positive'
        receipt = materialize(positive, env)
        result = finalize(positive, env)
        if result.returncode:
            raise AssertionError(result.stdout)
        report = json.loads((positive/'analysis-report.json').read_text())
        evidence = json.loads((positive/'result.json').read_text())
        assert evidence['case_id'] == CASE and report['accepted'] is False
        channels = sorted((positive/'channels').glob('*.jsonl'))
        assert len(channels) == len(evidence['recording_description']['channels'])
        assert all(len(channel.read_text().splitlines()) == 480 for channel in channels)
        sys.path.insert(0, str(ROOT/'runtime/pipeline/scenario_pipeline'))
        from worker_exchange.runtime_cli import process
        converted_root = scratch/'converted'
        decoder_error = None
        try:
            converted = process(positive, converted_root,
                                ROOT/'runtime/pipeline/library',
                                ROOT/'.runtime-work/c10052-decoder/.lake/build/bin/adapterCheck',
                                diagnostic_fixture=True)
            assert converted['converted'] and converted['decoder_checked']
        except (RuntimeError, ValueError) as error:
            decoder_error = str(error)
        adapter_report = (json.loads((converted_root/'adapter_report.json').read_text())
                          if (converted_root/'adapter_report.json').is_file() else {})
        decoder_diagnostic = {
            'error': decoder_error,
            'required_measurements_complete': adapter_report.get('required_measurements_complete'),
            'atom_coverage': adapter_report.get('atom_coverage'),
            'decoder_validation': adapter_report.get('decoder_validation'),
        }
        (HERE/'rider-core-coverage-diagnostic.json').write_text(
            json.dumps(decoder_diagnostic, sort_keys=True, indent=2)+'\n')
        negative = scratch/'negative'
        materialize(negative, env)
        (negative/'rider-source-manifest.json').unlink()
        rejected = finalize(negative, env)
        assert rejected.returncode != 0
        assert 'Missing required source: rider-source-manifest.json' in rejected.stdout
        assert not (negative/'result.json').exists()
        summary = {'format': 'c10052-rider-current-saved-diagnostic-v1',
                   'passed': True, 'selected': False, 'accepted': False,
                   'case_id': CASE, 'recipe_sha256': sha(RECIPE),
                   'fixture_sha256': receipt['fixture_sha256'],
                   'construction_sha256': sha(CONSTRUCTION),
                   'finalizer_sha256': sha(HERE/'native/finalize_rider.py'),
                   'derived_channel_count': len(channels),
                   'derived_rows_per_channel': 480,
                   'source_frame_count': report['original_joins']['frames'],
                   'core_conversion_wrote_trace': (converted_root/'trace.json').is_file(),
                   'lean_decoder_passed': decoder_error is None,
                   'lean_decoder_sha256': sha(ROOT/'.runtime-work/c10052-decoder/.lake/build/bin/adapterCheck'),
                   'core_coverage_diagnostic_sha256': sha(HERE/'rider-core-coverage-diagnostic.json'),
                   'simultaneous_conflict_frames': report['measurements'][
                       'rider_conflict_observation']['value'][
                           'simultaneous_conflict_frames'],
                   'missing_source_negative_exit_code': rejected.returncode,
                   'missing_source_error': 'Missing required source: rider-source-manifest.json',
                   'source_hashes': report['original_joins']['source_hashes'],
                   'scope': 'synthetic saved finalizer only; no original Native claim'}
    path = HERE/'rider-current-saved-proof.json'
    path.write_text(json.dumps(summary, sort_keys=True, indent=2)+'\n')
    print(json.dumps(summary, sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
