"""Run exact unselected saved finalizers over synthetic joined CPU sources."""
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
sys.path.insert(0, str(FOLDER / 'native'))
from worker_exchange.runtime_cli import materialize, execution_env
from worker_exchange.native_output import validate_result
from worker_exchange.measurement_contract import validate as validate_measurements, verify_report
from batch_pipeline.validation import recording_evidence
from prove_saved import packet, save

MANIFEST = FOLDER / 'draft-execution-manifest.json'
VIDEOS = ('overview.mkv', 'front_lamp.mkv', 'right_edge.mkv', 'rear_approach.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_rows(path, values):
    path.write_text(''.join(json.dumps(value, sort_keys=True) + '\n' for value in values))


def invoke(bundle):
    return subprocess.run([sys.executable, str(bundle / 'finalize.py'),
                           '--attempt', str(bundle), '--output', str(bundle / 'analysis-report.json')],
                          cwd=bundle, env=execution_env(), text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)


def fixture(bundle, case, candidate, video):
    scope, actors = packet(case, candidate)
    save(bundle, scope, actors)
    mapping, trace = [], []
    for actor in actors:
        frame = actor['native_frame']
        time = actor['time_s']
        center = actor['subject']['center_xy_m']
        mapping.append({'video_frame': actor['video_frame'], 'carla_frame': frame,
                        'native_frame': frame, 'time_s': time})
        trace.append({'frame': frame, 'time_s': time,
                      'position': {'x': center[0], 'y': center[1], 'z': .5},
                      'heading_deg': actor['subject']['heading_deg'],
                      'speed_mps': actor['subject']['speed_mps']})
    write_rows(bundle / 'video_frames.jsonl', mapping)
    write_rows(bundle / 'trace.jsonl', trace)
    for name in VIDEOS:
        shutil.copyfile(video, bundle / name)


def prove():
    ffmpeg = ROOT / '.runtime-work/linux_arm64/ffmpeg'
    if not ffmpeg.is_file():
        raise ValueError('Pinned local FFmpeg absent')
    manifest = json.loads(MANIFEST.read_text())
    contract = json.loads((FOLDER / 'native/selected-measurement-contract.json').read_text())
    dispositions = json.loads((FOLDER / 'case-plan.json').read_text())['requirement_dispositions']
    scratch = Path(tempfile.mkdtemp(dir=ROOT / '.runtime-work', prefix='c405647-1b-finalization-'))
    video = scratch / 'synthetic.mkv'
    subprocess.run([str(ffmpeg), '-hide_banner', '-loglevel', 'error', '-f', 'lavfi',
                    '-i', 'color=c=blue:s=16x16:r=20:d=24', '-c:v', 'ffv1',
                    str(video)], check=True, timeout=120)
    results = []
    for entry in manifest['cases']:
        case = entry['case_id'].rsplit('__', 1)[-1]
        validate_measurements(contract, dispositions,
                              (FOLDER / 'native/finalize.py').read_text(), entry['case_id'])
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            bundle = scratch / (case + '-' + candidate)
            materialize(MANIFEST, entry['case_id'], bundle, candidate)
            fixture(bundle, case, candidate, video)
            positive = invoke(bundle)
            if positive.returncode:
                raise ValueError(f'{case}/{candidate}: finalizer failed: {positive.stdout[-1200:]}')
            report = json.loads((bundle / 'analysis-report.json').read_text())
            verify_report(contract, report, bundle)
            result = validate_result(json.loads((bundle / 'result.json').read_text()))
            assert report['case_id'] == result['case_id'] == entry['case_id']
            assert result['accepted'] is False and result['setup_confirmed'] is False
            assert result['target_checks'][0]['matched'] is True
            assert result['provenance_kind'] == 'synthetic_local_diagnostic'
            recording_evidence(result,
                               json.loads((bundle / 'construction.json').read_text())['recording_description'],
                               lambda ref: bundle / ref)
            bad = scratch / (case + '-' + candidate + '-bad-join')
            materialize(MANIFEST, entry['case_id'], bad, candidate)
            fixture(bad, case, candidate, video)
            mapping = [json.loads(line) for line in (bad / 'video_frames.jsonl').read_text().splitlines()]
            mapping[100]['carla_frame'] += 1
            write_rows(bad / 'video_frames.jsonl', mapping)
            failure = invoke(bad)
            if failure.returncode == 0 or 'Saved actor/trace/video frame join differs' not in failure.stdout:
                raise ValueError(f'{case}/{candidate}: corrupt join accepted')
            missing = scratch / (case + '-' + candidate + '-missing-actor')
            materialize(MANIFEST, entry['case_id'], missing, candidate)
            fixture(missing, case, candidate, video)
            (missing / contract['negative']['remove'][0]).unlink()
            missing_failure = invoke(missing)
            if (missing_failure.returncode == 0 or
                    contract['negative']['error_contains'] not in missing_failure.stdout):
                raise ValueError(f'{case}/{candidate}: missing required source accepted')
            output = FOLDER / 'draft-candidates' / case / candidate
            shutil.copyfile(bundle / 'analysis-report.json', output / 'finalization-analysis.json')
            shutil.copyfile(bundle / 'result.json', output / 'finalization-result.json')
            (output / 'finalization-negative.log').write_text(failure.stdout)
            (output / 'measurement-negative.log').write_text(missing_failure.stdout)
            results.append({'case_id': entry['case_id'], 'candidate_id': candidate,
                            'construction_sha256': (entry if candidate == 'primary' else next(
                                row for row in entry['candidates'] if row['id'] == candidate))['construction_sha256'],
                            'analysis_sha256': sha(output / 'finalization-analysis.json'),
                            'result_sha256': sha(output / 'finalization-result.json'),
                            'negative_log_sha256': sha(output / 'finalization-negative.log'),
                            'measurement_negative_log_sha256': sha(output / 'measurement-negative.log'),
                            'frame_count': 480, 'recording_channels': 3,
                            'physical_acceptance_claimed': False})
            print(case, candidate, 'finalizer positive and changed-join negative passed', flush=True)
    proof = {'format': 'c405647-1b-exact-finalization-proof-v1',
             'manifest_sha256': sha(MANIFEST), 'results': results,
             'core_video_compatibility_claimed': False}
    (FOLDER / 'exact-finalization-proof.json').write_text(json.dumps(proof, indent=2) + '\n')
    return proof


if __name__ == '__main__':
    print(json.dumps({'results': len(prove()['results'])}))
