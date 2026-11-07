"""Exact eight-bundle saved analysis with decoded pixels and source negatives."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.runtime_cli import materialize, execution_env
from worker_exchange.native_output import validate_result
from worker_exchange.measurement_contract import validate as validate_contract, verify_report
from batch_pipeline.validation import recording_evidence
from batch_pipeline.carla import validate_attempt

FFMPEG = REPO / '.runtime-work/linux_arm64/ffmpeg'
MEDIA = REPO / '.runtime-work/c111331-signal-cpu-video'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def trace_from(source, output):
    rows = [json.loads(line) for line in (source / 'native_samples.jsonl').read_text().splitlines()]
    with (output / 'trace.jsonl').open('x') as stream:
        for row in rows:
            x, y = row['native_center_xy_m']
            stream.write(json.dumps({'frame': row['native_frame'], 'time_s': row['time_s'],
                'position': {'x': x, 'y': y, 'z': .5}, 'position_m': [x, y, .5],
                'heading_deg': row['native_yaw_deg'],
                'speed_mps': 20 * ((rows[1]['native_center_xy_m'][1] - rows[0]['native_center_xy_m'][1]))},
                allow_nan=False) + '\n')


def attempt(case, candidate, destination):
    case_id = HERE.parent.name + '__' + case
    materialize(HERE / 'package-manifest.json', case_id, destination, candidate)
    source = HERE / 'synthetic-saved' / case / candidate
    for name in ('native_samples.jsonl', 'video_frames.jsonl'):
        shutil.copy2(source / name, destination / name)
    shutil.copy2(MEDIA / case / candidate / 'signal_reference.mkv', destination / 'signal_reference.mkv')
    trace_from(source, destination)
    return case_id


def invoke(destination):
    env = execution_env()
    env['PATH'] = str(FFMPEG.parent) + os.pathsep + env.get('PATH', '')
    return subprocess.run([sys.executable, str(destination / 'finalize.py'),
        '--attempt', str(destination), '--output', str(destination / 'analysis-report.json')],
        cwd=destination, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, timeout=180)


def prove():
    if not FFMPEG.is_file():
        raise FileNotFoundError(FFMPEG)
    scratch = Path(tempfile.mkdtemp(dir=REPO / '.runtime-work', prefix='c111331-saved-finalizer-'))
    retained = HERE / 'saved-receipts'
    plan = json.loads((HERE.parent / 'case-plan.json').read_text())
    proposals = json.loads((HERE / 'proposals/cases.json').read_text())
    os.environ['PATH'] = str(FFMPEG.parent) + os.pathsep + os.environ.get('PATH', '')
    results = []
    for case in ('reference', 'contrast'):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            key = case + '-' + candidate
            positive = scratch / (key + '-positive')
            case_id = attempt(case, candidate, positive)
            acquisition = {name: sha(positive / name) for name in (
                'native_samples.jsonl', 'video_frames.jsonl', 'signal_reference.mkv', 'trace.jsonl')}
            passed = invoke(positive)
            if passed.returncode:
                raise RuntimeError('Exact saved positive failed: ' + passed.stdout[-1200:])
            if any(sha(positive / name) != digest for name, digest in acquisition.items()):
                raise ValueError('Finalizer changed an acquired source')
            report = json.loads((positive / 'analysis-report.json').read_text())
            result = validate_result(json.loads((positive / 'result.json').read_text()))
            contract = json.loads((HERE / 'measurement-contracts' / (case + '.json')).read_text())
            validate_contract(contract, plan['requirement_dispositions'],
                              (positive / 'finalize.py').read_text(), case_id)
            verified_measurements = verify_report(contract, report, positive)
            if len(verified_measurements) != 5:
                raise ValueError('All five source topics need measured outputs')
            if report['case_id'] != case_id or result['case_id'] != case_id or result['accepted'] or result['setup_confirmed'] or result['behavior_attempted'] or result['maneuver_completed']:
                raise ValueError('Synthetic diagnostic promoted to physical result')
            if report['synthetic_video_proof']['decoded_frames'] != 480 or report['synthetic_video_proof']['original_carla_pixels_verified']:
                raise ValueError('Decoded video proof differs')
            def artifact(reference):
                path = positive / reference
                if not path.is_file() or not path.stat().st_size:
                    raise ValueError('Recording evidence file absent: ' + reference)
                return path
            recording_evidence(result, json.loads((positive / 'construction.json').read_text())['recording_description'], artifact)
            proposal_case = next(p for p in proposals['cases'] if p['case_id'] == case_id)
            validate_attempt(positive, {'case': proposal_case,
                'cell': {'cell_id': 'C111331'}, 'actor': 'motor_vehicle_driver'},
                json.loads((positive / 'construction.json').read_text()),
                {'recorded_exit_code': 0}, {})
            negative = scratch / (key + '-negative')
            attempt(case, candidate, negative)
            (negative / 'native_samples.jsonl').unlink()
            rejected = invoke(negative)
            if rejected.returncode == 0 or 'Missing required source: native_samples.jsonl' not in rejected.stdout:
                raise AssertionError('Exact missing-source negative accepted: ' + rejected.stdout[-800:])
            wrong_video = scratch / (key + '-wrong-video')
            attempt(case, candidate, wrong_video)
            other_case = 'contrast' if case == 'reference' else 'reference'
            shutil.copy2(MEDIA / other_case / candidate / 'signal_reference.mkv',
                         wrong_video / 'signal_reference.mkv')
            mismatched = invoke(wrong_video)
            if mismatched.returncode == 0 or 'Decoded signal color disagrees with saved Native phase' not in mismatched.stdout:
                raise AssertionError('Exact wrong-signal-video negative accepted: ' + mismatched.stdout[-800:])
            wrong_join = scratch / (key + '-wrong-join')
            attempt(case, candidate, wrong_join)
            frame_rows = [json.loads(line) for line in (wrong_join / 'video_frames.jsonl').read_text().splitlines()]
            frame_rows[200]['carla_frame'] = -1
            (wrong_join / 'video_frames.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in frame_rows))
            rejected_join = invoke(wrong_join)
            if rejected_join.returncode == 0 or 'Saved Native/trace/video frame join differs' not in rejected_join.stdout:
                raise AssertionError('Exact Core frame-map negative accepted: ' + rejected_join.stdout[-800:])
            target = retained / case / candidate
            target.mkdir(parents=True, exist_ok=True)
            for name in ('analysis-report.json', 'result.json'):
                shutil.copy2(positive / name, target / name)
            (target / 'positive-analysis.log').write_text(passed.stdout)
            (target / 'negative-analysis.log').write_text(rejected.stdout)
            (target / 'wrong-video-analysis.log').write_text(mismatched.stdout)
            (target / 'wrong-join-analysis.log').write_text(rejected_join.stdout)
            results.append({'case': case, 'candidate': candidate, 'case_id': case_id,
                'manifest_sha256': sha(HERE / 'package-manifest.json'),
                'construction_sha256': sha(HERE / 'package-candidates' / case / candidate / 'construction.json'),
                'acquisition_sha256': acquisition,
                'analysis_report_sha256': sha(target / 'analysis-report.json'),
                'result_sha256': sha(target / 'result.json'),
                'positive_log_sha256': sha(target / 'positive-analysis.log'),
                'negative_log_sha256': sha(target / 'negative-analysis.log'),
                'wrong_video_log_sha256': sha(target / 'wrong-video-analysis.log'),
                'wrong_join_log_sha256': sha(target / 'wrong-join-analysis.log'),
                'negative_error': 'Missing required source: native_samples.jsonl',
                'wrong_video_error': 'Decoded signal color disagrees with saved Native phase',
                'wrong_join_error': 'Saved Native/trace/video frame join differs',
                'measurement_contract_sha256': sha(HERE / 'measurement-contracts' / (case + '.json')),
                'measurement_keys': sorted(verified_measurements),
                'pinned_native_attempt_validation': 'passed',
                'physical_success_claimed': False})
    summary = {'format': 'c111331-exact-synthetic-saved-finalizer-v1',
               'manifest_sha256': sha(HERE / 'package-manifest.json'),
               'rows': results, 'accepted_recording_claimed': False}
    (HERE / 'saved-finalizer-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return {'passed': True, 'bundles': len(results), 'negative_rejections': 3 * len(results),
            'summary_sha256': sha(HERE / 'saved-finalizer-summary.json')}


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
