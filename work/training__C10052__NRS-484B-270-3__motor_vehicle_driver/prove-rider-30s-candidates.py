"""Exercise every exact 30 s rider candidate with retained source-only media."""
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
FIXTURE = ROOT / '.runtime-work/c10052-rider-30s-primary-fixture'
DECODER = ROOT / '.runtime-work/c10052-decoder/.lake/build/bin/adapterCheck'
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def command(args, env):
    completed = subprocess.run(args, cwd=ROOT, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               timeout=300)
    if completed.returncode:
        raise AssertionError(completed.stdout)
    return completed.stdout


def main():
    assert FIXTURE.is_dir() and DECODER.is_file()
    env = dict(os.environ)
    env['SCENARIO_PIPELINE_OUTPUT_ROOT'] = str(ROOT / '.runtime-work/c10052-rider-candidate-proof')
    env['PYTHONPATH'] = str(ROOT / 'runtime/pipeline/scenario_pipeline') + (
        os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    recipe = json.loads(RECIPE.read_text())
    assert len(recipe['sources']) == 616
    manifest = json.loads(MANIFEST.read_text())
    entry = next(item for item in manifest['cases'] if item['case_id'] == CASE)
    selected = {'primary': {'construction': entry['construction'],
                            'construction_sha256': entry['construction_sha256']}}
    selected.update({item['id']: item for item in entry['candidates']})
    rows = []
    with tempfile.TemporaryDirectory(dir=ROOT / '.runtime-work',
                                     prefix='c10052-rider-candidate-') as temp:
        scratch = Path(temp)
        sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
        from worker_exchange.runtime_cli import process, render
        from worker_exchange.media import audit
        for candidate in CANDIDATES:
            spec = selected[candidate]
            construction = PACKAGE / spec['construction']
            assert sha(construction) == spec['construction_sha256']
            positive = scratch / candidate / 'positive'
            command([sys.executable, str(ROOT / 'runtime.py'), 'materialize',
                     '--manifest', str(MANIFEST), '--case', CASE,
                     '--candidate', candidate, '--output', str(positive)], env)
            for source in FIXTURE.iterdir():
                target = positive / source.name
                if target.exists():
                    raise AssertionError('Fixture shadows construction: ' + source.name)
                if source.is_dir():
                    shutil.copytree(source, target)
                else:
                    shutil.copy2(source, target)
            assert not (positive / 'channels').exists()
            command([sys.executable, str(positive / 'finalize_rider.py'),
                     '--attempt', str(positive), '--output',
                     str(positive / 'analysis-report.json')], env)
            report = json.loads((positive / 'analysis-report.json').read_text())
            result = json.loads((positive / 'result.json').read_text())
            assert report['candidate_id'] == candidate
            assert report['original_joins']['frames'] == 600
            assert result['case_id'] == CASE
            channels = sorted((positive / 'channels').glob('*.jsonl'))
            assert len(channels) == len(result['recording_description']['channels'])
            assert all(len(path.read_text().splitlines()) == 600 for path in channels)
            converted_root = scratch / candidate / 'converted'
            converted = process(positive, converted_root,
                                ROOT / 'runtime/pipeline/library', DECODER,
                                diagnostic_fixture=True)
            assert converted['converted'] and converted['decoder_checked']
            video = render(positive, converted_root, {'case_id': CASE})
            decoded = audit(video['video'], 600,
                            mapping_sha256=video['frame_map_sha256'],
                            receipt=positive / 'final-decode.json')
            assert video['frames'] == 600 and decoded['passed']
            negative = scratch / candidate / 'negative'
            shutil.copytree(positive, negative)
            for generated in ('result.json', 'analysis-report.json'):
                (negative / generated).unlink()
            (negative / 'rider-source-manifest.json').unlink()
            rejected = subprocess.run(
                [sys.executable, str(negative / 'finalize_rider.py'),
                 '--attempt', str(negative), '--output',
                 str(negative / 'analysis-report.json')], cwd=ROOT, env=env,
                text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                timeout=300)
            expected = 'Missing required source: rider-source-manifest.json'
            assert rejected.returncode != 0 and expected in rejected.stdout
            rows.append({'candidate_id': candidate,
                         'construction_sha256': sha(construction),
                         'original_frames': report['original_joins']['frames'],
                         'camera_frames': report['video_frames'],
                         'derived_channel_count': len(channels),
                         'core_lean_passed': True,
                         'final_decode_passed': decoded['passed'],
                         'missing_source_rejected': True,
                         'measured_values': result['measured_values'],
                         'source_hashes': report['original_joins']['source_hashes']})
    assert len({row['construction_sha256'] for row in rows}) == 4
    proof = {'format': 'c10052-rider-30s-candidate-saved-diagnostic-v1',
             'case_id': CASE, 'selected': False, 'accepted': False,
             'manifest_sha256': sha(MANIFEST), 'recipe_sha256': sha(RECIPE),
             'source_count': len(recipe['sources']), 'candidates': rows,
             'scope': 'synthetic source-only CPU proof; no original Native evidence'}
    destination = PACKAGE / 'candidate-saved-proof.json'
    destination.write_text(json.dumps(proof, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'proof_sha256': sha(destination), 'candidate_count': len(rows),
                      'source_frames': 600, 'selected': False}, sort_keys=True))


if __name__ == '__main__':
    main()
