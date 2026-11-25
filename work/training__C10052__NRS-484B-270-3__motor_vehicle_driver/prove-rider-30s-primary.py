"""Exercise the exact 30 s draft rider bundle against source-only CPU media."""
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
PACKAGE = HERE / 'rider-30s-primary'
MANIFEST = PACKAGE / 'draft-manifest.json'
RECIPE = PACKAGE / 'fixture-recipe.json'
FIXTURE = ROOT / '.runtime-work/c10052-rider-30s-profile-fixture'
DECODER = ROOT / '.runtime-work/c10052-current-decoder/.lake/build/bin/adapterCheck'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run(command, env):
    return subprocess.run(command, cwd=ROOT, env=env, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          timeout=300)


def main():
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c10052-rider-30s-proof')
    env['PYTHONPATH'] = str(ROOT / 'runtime/scenario_pipeline') + (
        os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    assert FIXTURE.is_dir() and DECODER.is_file()
    recipe = json.loads(RECIPE.read_text())
    assert len(recipe['sources']) == 616
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work',
                                     prefix='c10052-rider-30s-proof-') as temp:
        scratch = Path(temp)
        positive = scratch / 'positive'
        materialize = run([sys.executable, str(ROOT / 'runtime.py'), 'materialize',
                           '--manifest', str(MANIFEST), '--case', CASE,
                           '--output', str(positive)], env)
        if materialize.returncode:
            raise AssertionError(materialize.stdout)
        for source in FIXTURE.iterdir():
            target = positive / source.name
            if target.exists():
                raise AssertionError('Fixture shadows construction: ' + source.name)
            if source.is_dir():
                shutil.copytree(source, target)
            else:
                shutil.copy2(source, target)
        assert not (positive / 'channels').exists()
        saved = run([sys.executable, str(positive / 'finalize_rider.py'),
                     '--attempt', str(positive), '--output',
                     str(positive / 'analysis-report.json')], env)
        if saved.returncode:
            raise AssertionError(saved.stdout)
        report = json.loads((positive / 'analysis-report.json').read_text())
        result = json.loads((positive / 'result.json').read_text())
        assert report['original_joins']['frames'] == 600
        channels = sorted((positive / 'channels').glob('*.jsonl'))
        assert len(channels) == len(result['recording_description']['channels'])
        assert all(len(path.read_text().splitlines()) == 600 for path in channels)
        sys.path.insert(0, str(ROOT / 'runtime/scenario_pipeline'))
        from worker_exchange.runtime_cli import process, render
        from worker_exchange.media import audit
        converted_root = scratch / 'converted'
        converted = process(positive, converted_root,
                            ROOT / 'runtime/library', DECODER,
                            diagnostic_fixture=True)
        assert converted['converted'] and converted['decoder_checked']
        video = render(positive, converted_root, {'case_id': CASE})
        decoded = audit(video['video'], 600,
                        mapping_sha256=video['frame_map_sha256'],
                        receipt=positive / 'final-decode.json')
        assert video['frames'] == 600 and decoded['passed']
        negative = scratch / 'negative'
        shutil.copytree(positive, negative)
        for generated in ('result.json', 'analysis-report.json'):
            (negative / generated).unlink()
        (negative / 'rider-source-manifest.json').unlink()
        rejected = run([sys.executable, str(negative / 'finalize_rider.py'),
                        '--attempt', str(negative), '--output',
                        str(negative / 'analysis-report.json')], env)
        expected = 'Missing required source: rider-source-manifest.json'
        assert rejected.returncode != 0 and expected in rejected.stdout
        proof = {'format': 'c10052-rider-30s-primary-diagnostic-v1',
                 'case_id': CASE, 'candidate_id': 'primary',
                 'selected': False, 'accepted': False,
                 'construction_sha256': sha(PACKAGE / 'construction.json'),
                 'manifest_sha256': sha(MANIFEST),
                 'recipe_sha256': sha(RECIPE),
                 'source_count': len(recipe['sources']),
                 'source_frames': report['original_joins']['frames'],
                 'duration_s': result['realized_observables']['rider_clearance_s']['sample_window_s'][-1],
                 'camera_frames': report['video_frames'],
                 'derived_channels': len(channels),
                 'derived_rows_per_channel': 600,
                 'core_lean_passed': True,
                 'render_frames': video['frames'],
                 'final_decode_passed': decoded['passed'],
                 'missing_source_negative_exit_code': rejected.returncode,
                 'missing_source_error': expected,
                 'source_hashes': report['original_joins']['source_hashes'],
                 'scope': 'synthetic source-only package diagnostic; no original Native observation'}
    (PACKAGE / 'primary-proof.json').write_text(json.dumps(proof, sort_keys=True, indent=2) + '\n')
    print(json.dumps(proof, sort_keys=True))


if __name__ == '__main__':
    main()
