"""Exact bundled C422978 finalizer CPU positives and source-removal negatives."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

FOLDER = Path(__file__).resolve().parent
ROOT = FOLDER.parents[1]
sys.path.insert(0, str(ROOT / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize, execution_env
from worker_exchange.measurement_contract import validate as validate_contract, verify_report
from worker_exchange.native_output import validate_result
from batch_pipeline.validation import recording_evidence

MANIFEST = FOLDER / 'draft-execution-manifest.json'
SOURCES = ('native-observed.jsonl', 'native-map-readback.json',
           'video_frames.jsonl', 'capture/evidence.jsonl')
VIDEOS = ('overview.mkv', 'front.mkv', 'sidewalk.mkv', 'rear.mkv')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fixture(bundle, case, candidate, video):
    source = FOLDER / 'native/saved-fixtures' / case / candidate
    for name in SOURCES:
        target = bundle / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / name, target)
    shutil.copyfile(FOLDER / 'native/context-fixtures' / case / candidate / 'city-context.json',
                    bundle / 'city-context.json')
    for name in VIDEOS: shutil.copyfile(video, bundle / name)
    observed = [json.loads(line) for line in (bundle / 'native-observed.jsonl').read_text().splitlines()]
    (bundle / 'trace.jsonl').write_text(''.join(json.dumps({
        'frame': row['native_frame'], 'time_s': row['time_s'],
        'position_m': [*row['center_native_xy_m'], .5],
        'speed_mps': row['speed_mps']}) + '\n' for row in observed))


def invoke(bundle):
    return subprocess.run([sys.executable, str(bundle / 'finalize.py'), '--attempt', str(bundle),
                           '--output', str(bundle / 'analysis-report.json')],
                          cwd=bundle, env=execution_env(), text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)


def prove():
    manifest = json.loads(MANIFEST.read_text())
    contract = json.loads((FOLDER / 'native/measurement-contract.json').read_text())
    dispositions = json.loads((FOLDER / 'case-plan.json').read_text())['requirement_dispositions']
    scratch = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c422978-finalize-'))
    video = scratch / 'synthetic.mkv'
    ffmpeg = ROOT / '.runtime-work/linux_arm64/ffmpeg'
    subprocess.run([str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
                    '-i', 'color=c=blue:s=16x16:r=20:d=24', '-c:v', 'ffv1', str(video)],
                   check=True, timeout=120)
    results = []
    for entry in manifest['cases']:
        case = entry['case_id'].rsplit('__', 1)[-1]
        validate_contract(contract, dispositions,
                          (FOLDER / 'native/finalize.py').read_text(), entry['case_id'])
        for candidate in ('primary','fallback1','fallback2','fallback3'):
            bundle = scratch / (case + '-' + candidate)
            materialize(MANIFEST, entry['case_id'], bundle, candidate)
            fixture(bundle, case, candidate, video)
            run = invoke(bundle)
            if run.returncode:
                raise ValueError(f'{case}/{candidate}: finalizer failed: {run.stdout[-1200:]}')
            report = json.loads((bundle / 'analysis-report.json').read_text())
            verify_report(contract, report, bundle)
            result = validate_result(json.loads((bundle / 'result.json').read_text()))
            assert result['case_id'] == entry['case_id']
            assert result['target_checks'][0]['matched'] is True
            assert result['provenance_kind'] == 'synthetic_local_diagnostic'
            assert not result['accepted'] and not result['setup_confirmed']
            recording_evidence(result,
                               json.loads((bundle / 'construction.json').read_text())['recording_description'],
                               lambda ref: bundle / ref)
            bad = scratch / (case + '-' + candidate + '-missing')
            materialize(MANIFEST, entry['case_id'], bad, candidate)
            fixture(bad, case, candidate, video)
            (bad / 'native-observed.jsonl').unlink()
            failure = invoke(bad)
            if (failure.returncode == 0 or
                    contract['negative']['error_contains'] not in failure.stdout):
                raise ValueError(f'{case}/{candidate}: missing original source accepted')
            missing_context = scratch / (case + '-' + candidate + '-missing-context')
            materialize(MANIFEST, entry['case_id'], missing_context, candidate)
            fixture(missing_context, case, candidate, video)
            (missing_context / 'city-context.json').unlink()
            context_failure = invoke(missing_context)
            context_error = 'Missing required source: city-context.json'
            if context_failure.returncode == 0 or context_error not in context_failure.stdout:
                raise ValueError(f'{case}/{candidate}: missing spatial context accepted')
            output = FOLDER / 'draft-candidates' / case / candidate
            shutil.copyfile(bundle / 'analysis-report.json', output / 'finalization-analysis.json')
            shutil.copyfile(bundle / 'result.json', output / 'finalization-result.json')
            (output / 'finalization-negative.log').write_text(failure.stdout)
            (output / 'finalization-context-negative.log').write_text(context_failure.stdout)
            ref = entry if candidate == 'primary' else next(
                r for r in entry['candidates'] if r['id'] == candidate)
            results.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                            'construction_sha256': ref['construction_sha256'],
                            'analysis_sha256': sha(output / 'finalization-analysis.json'),
                            'result_sha256': sha(output / 'finalization-result.json'),
                            'negative_log_sha256': sha(output / 'finalization-negative.log'),
                            'context_negative_log_sha256': sha(output / 'finalization-context-negative.log'),
                            'measurement_contract_sha256': sha(FOLDER / 'native/measurement-contract.json')})
            print(case, candidate, 'contract positive and missing-source negative passed', flush=True)
    proof = {'format': 'c422978-exact-finalization-proof-v1',
             'manifest_sha256': sha(MANIFEST), 'results': results,
             'core_video_or_original_native_claimed': False}
    (FOLDER / 'exact-finalization-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    return proof


if __name__ == '__main__':
    print(json.dumps({'results': len(prove()['results'])}))
