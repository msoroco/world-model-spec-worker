"""Exercise the exact official-branch saved bridge and finalizer on CPU fixtures."""
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
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from geometry import synthetic_subject_body_xy  # noqa: E402
from prepare_saved import prepare  # noqa: E402
from worker_exchange.runtime_cli import execution_env, materialize  # noqa: E402
from worker_exchange.native_output import validate_result  # noqa: E402
from batch_pipeline.validation import recording_evidence  # noqa: E402

VIDEOS = ('overview.mkv', 'front_lamp.mkv', 'rear_approach.mkv',
          'subject_reference.mkv')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def fixture(source, case, candidate):
    source.mkdir()
    requests = [json.loads(line) for line in (
        HERE / 'drafts' / case / candidate / 'native-requests.jsonl').read_text().splitlines()]
    observed, mapping, annotations = [], [], []
    for index, row in enumerate(requests):
        native_frame = 1000 + index
        subject = row['subject_request']
        approach = row['approach_request']
        authored_body = synthetic_subject_body_xy(
            {'x_m': subject['x_m'], 'y_m': -subject['y_m']})
        native_body = [[x, -y] for x, y in authored_body]
        observed.append({'frame': index, 'native_frame': native_frame,
                         'time_s': row['time_s'], 'source_kind': 'synthetic_cpu',
                         'front_red_flash_on': None,
                         'actors': {
                             'subject': {'native_center_xy_m': [subject['x_m'], subject['y_m']],
                                         'native_body_xy_m': native_body},
                             'approach': {'native_center_xy_m': [approach['x_m'], approach['y_m']]}}})
        mapping.append({'video_frame': index, 'native_frame': native_frame,
                        'carla_frame': native_frame, 'time_s': row['time_s']})
        annotations.append({'video_frame': index, 'native_frame': native_frame,
                            'front_red_flash_on': row['lamp_request']['front_red_flash_on']})
    write_rows(source / 'observed-actors.jsonl', observed)
    write_rows(source / 'video_frames.jsonl', mapping)
    (source / 'front_lamp.source').write_bytes(
        ('synthetic official lamp source ' + case + ' ' + candidate + '\n').encode())
    (source / 'front-lamp-review.json').write_text(json.dumps({
        'source_kind': 'synthetic_cpu', 'source_video_sha256': sha(source / 'front_lamp.source'),
        'frames': annotations}, sort_keys=True) + '\n')


def invoke(attempt):
    return subprocess.run([sys.executable, str(attempt / 'finalize.py'),
                           '--attempt', str(attempt), '--output',
                           str(attempt / 'analysis-report.json')],
                          cwd=attempt, env=execution_env(), text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)


def prove():
    ffmpeg = REPO / '.runtime-work/linux_arm64/ffmpeg'
    assert ffmpeg.is_file()
    scratch = Path(tempfile.mkdtemp(dir=REPO / '.runtime-work', prefix='c405647-official-saved-'))
    results = []
    for case in ('official_1', 'official_2'):
        case_id = HERE.parent.name + '__' + case
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            key = case + '-' + candidate
            source, prepared, attempt = (scratch / (key + '-' + suffix)
                                         for suffix in ('source', 'prepared', 'attempt'))
            fixture(source, case, candidate)
            bridge = prepare(source, prepared, case)
            assert bridge['passed'] and bridge['frames'] == 480
            materialize(HERE / 'package-manifest.json', case_id, attempt, candidate)
            for path in prepared.iterdir():
                shutil.copyfile(path, attempt / path.name)
            actors = [json.loads(line) for line in (attempt / 'actor-frames.jsonl').read_text().splitlines()]
            frames = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
            trace = [{'frame': frame['native_frame'], 'time_s': frame['time_s'],
                      'position': {'x': actor['subject']['x_m'],
                                   'y': actor['subject']['y_m'], 'z': 0.0},
                      'heading_deg': 0.0, 'speed_mps': 4.0}
                     for actor, frame in zip(actors, frames)]
            write_rows(attempt / 'trace.jsonl', trace)
            for name in VIDEOS:
                subprocess.run([str(ffmpeg), '-hide_banner', '-loglevel', 'error',
                                '-f', 'lavfi', '-i', 'color=c=blue:s=16x16:r=20:d=24',
                                '-c:v', 'ffv1', '-n', str(attempt / name)],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               check=True, timeout=120)
            positive = invoke(attempt)
            if positive.returncode:
                raise AssertionError('Saved finalizer failed: ' + positive.stdout[-1500:])
            result = validate_result(json.loads((attempt / 'result.json').read_text()))
            report = json.loads((attempt / 'analysis-report.json').read_text())
            assert report['case_id'] == case_id and result['case_id'] == case_id
            assert result['accepted'] is False and result['setup_confirmed'] is False
            def artifact(reference):
                path = attempt / reference
                assert path.is_file() and path.stat().st_size
                return path
            recording_evidence(result,
                               json.loads((attempt / 'construction.json').read_text())['recording_description'],
                               artifact)
            negative = scratch / (key + '-negative')
            shutil.copytree(attempt, negative)
            (negative / 'analysis-report.json').unlink()
            (negative / 'result.json').unlink()
            shutil.rmtree(negative / 'channels')
            (negative / 'source-scope.json').unlink()
            rejected = invoke(negative)
            if rejected.returncode == 0 or 'Missing required source: source-scope.json' not in rejected.stdout:
                raise AssertionError('Missing source was accepted: ' + rejected.stdout[-1000:])
            retained = HERE / 'saved-fixtures' / case / candidate
            if retained.exists():
                shutil.rmtree(retained)
            retained.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(attempt, retained)
            (retained / 'negative-analysis.log').write_text(rejected.stdout)
            results.append({'case_id': case_id, 'candidate_id': candidate,
                            'bridge_frames': bridge['frames'],
                            'result_valid': True, 'recording_evidence_valid': True,
                            'negative_error': 'Missing required source: source-scope.json',
                            'negative_log_sha256': sha(retained / 'negative-analysis.log'),
                            'analysis_report_sha256': sha(retained / 'analysis-report.json'),
                            'result_sha256': sha(retained / 'result.json'),
                            'physical_success_claimed': False})
            print(key, 'saved positive/negative pass', flush=True)
    summary = {'format': 'c405647-official-synthetic-saved-v1', 'passed': True,
               'source_kind': 'synthetic_cpu', 'results': results,
               'scope': 'saved bridge and finalizer only; no Native, original pixels, Core/Lean or acceptance'}
    (HERE / 'saved-proof.json').write_text(json.dumps(summary, indent=2) + '\n')
    return summary


if __name__ == '__main__':
    print(json.dumps(prove(), sort_keys=True))
