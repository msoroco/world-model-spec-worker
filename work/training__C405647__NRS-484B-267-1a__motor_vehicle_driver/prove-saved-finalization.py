"""Exercise exact materialized C405647 diagnostic saved finalization on CPU."""
import json
import hashlib
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / 'runtime/pipeline/scenario_pipeline'))
from worker_exchange.runtime_cli import execution_env, materialize
from worker_exchange.native_output import validate_result
from batch_pipeline.validation import recording_evidence

VIDEOS = ('overview.mkv', 'front_lamp.mkv', 'rear_approach.mkv',
          'subject_reference.mkv')


def _write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))


def _fixture(attempt, case, ffmpeg):
    prepared = HERE / 'synthetic-bridge' / case / 'prepared'
    for name in ('source-scope.json', 'actor-frames.jsonl',
                 'observed-actors.jsonl', 'front-lamp-review.json', 'front_lamp.source'):
        shutil.copyfile(prepared / name, attempt / name)
    shutil.copyfile(prepared / 'video_frames.jsonl', attempt / 'video_frames.jsonl')
    actors = [json.loads(line) for line in (attempt / 'actor-frames.jsonl').read_text().splitlines()]
    mapping = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    trace = []
    for actor, frame in zip(actors, mapping):
        trace.append({'frame': frame['native_frame'], 'time_s': frame['time_s'],
                      'position': {'x': actor['subject']['x_m'],
                                   'y': actor['subject']['y_m'], 'z': 0.0},
                      'heading_deg': 0.0, 'speed_mps': 4.0})
    _write_rows(attempt / 'trace.jsonl', trace)
    for name in VIDEOS:
        subprocess.run([str(ffmpeg), '-hide_banner', '-loglevel', 'error',
                        '-f', 'lavfi', '-i', 'color=c=blue:s=16x16:r=20:d=24',
                        '-c:v', 'ffv1', '-n', str(attempt / name)],
                       check=True, timeout=120)


def _invoke(attempt):
    return subprocess.run([sys.executable, str(attempt / 'finalize.py'),
                           '--attempt', str(attempt), '--output',
                           str(attempt / 'analysis-report.json')],
                          cwd=attempt, env=execution_env(), text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          timeout=120)


def prove():
    ffmpeg = REPO / '.runtime-work/linux_arm64/ffmpeg'
    if not ffmpeg.is_file():
        raise ValueError('Pinned local FFmpeg binary absent')
    results = []
    with tempfile.TemporaryDirectory(prefix='c405647-finalization-') as temporary:
        scratch = Path(temporary)
        for case, candidate in ((case, candidate)
                                for case in ('witness_1', 'witness_2')
                                for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3')):
            case_id = HERE.name + '__' + case
            attempt = scratch / (case + '-' + candidate)
            materialize(HERE / 'draft-execution-manifest.json', case_id,
                        attempt, candidate)
            _fixture(attempt, case, ffmpeg)
            complete = _invoke(attempt)
            if complete.returncode:
                raise AssertionError('Finalization failed: ' + complete.stdout[-2000:])
            result = validate_result(json.loads((attempt / 'result.json').read_text()))
            report = json.loads((attempt / 'analysis-report.json').read_text())
            assert report['case_id'] == case_id and result['case_id'] == case_id
            assert result['setup_confirmed'] is False and result['accepted'] is False
            assert result['target_checks'][0]['matched'] is True
            def artifact(reference):
                path = attempt / reference
                assert path.is_file() and path.stat().st_size
                return path
            recording_evidence(result,
                               json.loads((attempt / 'construction.json').read_text())['recording_description'],
                               artifact)
            changed = scratch / (case + '-' + candidate + '-bad-join')
            shutil.copytree(attempt, changed)
            (changed / 'analysis-report.json').unlink()
            (changed / 'result.json').unlink()
            shutil.rmtree(changed / 'channels')
            mapping = [json.loads(line) for line in (changed / 'video_frames.jsonl').read_text().splitlines()]
            mapping[100]['carla_frame'] += 1
            _write_rows(changed / 'video_frames.jsonl', mapping)
            scope = json.loads((changed / 'source-scope.json').read_text())
            scope['native_source_hashes']['video_frames.jsonl'] = hashlib.sha256(
                (changed / 'video_frames.jsonl').read_bytes()).hexdigest()
            (changed / 'source-scope.json').write_text(json.dumps(scope, sort_keys=True) + '\n')
            failure = _invoke(changed)
            if failure.returncode == 0 or 'Saved actor/trace/video frame join differs' not in failure.stdout:
                raise AssertionError('Changed frame join did not reject: ' + failure.stdout[-1000:])
            changed = scratch / (case + '-' + candidate + '-bad-source')
            shutil.copytree(attempt, changed)
            (changed / 'analysis-report.json').unlink()
            (changed / 'result.json').unlink()
            shutil.rmtree(changed / 'channels')
            (changed / 'observed-actors.jsonl').write_text('changed raw actor source\n')
            failure = _invoke(changed)
            if failure.returncode == 0 or 'Saved Native source hash differs: observed-actors.jsonl' not in failure.stdout:
                raise AssertionError('Changed Native source did not reject: ' + failure.stdout[-1000:])
            results.append({'case_id': case_id, 'candidate_id': candidate,
                            'frames': 480, 'four_videos': len(VIDEOS),
                            'native_result_valid': True, 'recording_evidence_valid': True,
                            'changed_frame_join_and_native_source_rejected': True,
                            'physical_success_claimed': False})
    return {'passed': True, 'results': results,
            'scope': 'synthetic CPU saved finalization; no Native behavior, original pixels, Core/Lean or accepted recording'}


if __name__ == '__main__':
    print(json.dumps(prove(), indent=2))
