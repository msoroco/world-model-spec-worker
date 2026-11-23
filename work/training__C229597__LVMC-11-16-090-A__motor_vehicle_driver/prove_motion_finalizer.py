"""CPU-check source-derived saved analysis with a synthetic Native-shaped sample."""
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(attempt, output):
    return subprocess.run((sys.executable, str(P / 'measure_episode.py'),
                           '--attempt', str(attempt), '--output', str(output)),
                          cwd=ROOT, capture_output=True, text=True)


def main():
    base = ROOT / '.runtime-work/c229597-motion-finalizer-v1'
    if base.exists():
        raise ValueError('Use a fresh proof directory')
    positive = base / 'positive'
    negative = base / 'negative'
    positive.mkdir(parents=True)
    negative.mkdir(parents=True)
    construction = P / 'draft-primary/reference/primary/construction.json'
    proposal = json.loads(construction.read_text())
    config = next(x['content'] for x in proposal['files'] if x['path'] == 'config.json')
    for attempt in (positive, negative):
        shutil.copyfile(construction, attempt / 'construction.json')
        (attempt / 'config.json').write_text(config)
        (attempt / 'acquisition-provenance.json').write_text(json.dumps({
            'case_id': proposal['case_id'], 'provenance_kind': 'synthetic_fixture',
            'diagnostic_fixture': True}, indent=2) + '\n')
    trace = []
    mapping = []
    for index in range(600):
        native = 1000 + index
        time_s = index / 20
        speed = 4 + index / 100
        trace.append({'frame': native, 'video_frame': index,
                      'native_frame': native, 'time_s': time_s,
                      'position_m': [index * .2, 0, 0],
                      'velocity_mps': [speed, 0, 0],
                      'acceleration_mps2': [.2, 0, 0]})
        mapping.append({'video_frame': index, 'carla_frame': native,
                        'native_frame': native, 'time_s': time_s})
    for attempt in (positive, negative):
        current = [dict(x) for x in mapping]
        if attempt == negative:
            current[-1]['carla_frame'] += 1
        (attempt / 'trace.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in trace))
        (attempt / 'video_frames.jsonl').write_text(''.join(json.dumps(x) + '\n' for x in current))
    video = base / 'synthetic-camera.mkv'
    subprocess.run(('ffmpeg', '-v', 'error', '-f', 'lavfi', '-i',
                    'testsrc2=size=128x72:rate=20', '-frames:v', '600',
                    '-c:v', 'ffv1', str(video)), check=True, timeout=180)
    for attempt in (positive, negative):
        for view in VIEWS:
            shutil.copyfile(video, attempt / (view + '.mkv'))
    good = run(positive, positive / 'analysis-report.json')
    (P / 'motion-finalizer-positive.log').write_text(good.stdout + good.stderr)
    if good.returncode:
        raise ValueError('Positive saved analysis failed: ' + good.stderr[-800:])
    report = json.loads((positive / 'analysis-report.json').read_text())
    result = json.loads((positive / 'result.json').read_text())
    if (report['case_id'] != proposal['case_id']
            or result['provenance_kind'] != 'synthetic_local_diagnostic'
            or result['accepted'] is not False
            or result['legal_verdict_claimed'] is not False
            or report['measurements']['text_0_motion']['value']['frames'] != 600):
        raise ValueError('Positive source measurement identity differs')
    bad = run(negative, negative / 'analysis-report.json')
    (P / 'motion-finalizer-negative.log').write_text(bad.stdout + bad.stderr)
    if (bad.returncode == 0 or 'Original source frame/timestamp join differs'
            not in bad.stderr or (negative / 'result.json').exists()):
        raise ValueError('Corrupted final frame was not rejected')
    receipt = {'format': 'c229597-source-motion-finalizer-proof',
               'construction_sha256': sha(construction),
               'finalizer_sha256': sha(P / 'measure_episode.py'),
               'positive_log_sha256': sha(P / 'motion-finalizer-positive.log'),
               'negative_log_sha256': sha(P / 'motion-finalizer-negative.log'),
               'report_sha256': sha(positive / 'analysis-report.json'),
               'result_sha256': sha(positive / 'result.json'),
               'source_trace_sha256': sha(positive / 'trace.jsonl'),
               'source_map_sha256': sha(positive / 'video_frames.jsonl'),
               'source_video_sha256': sha(video),
               'frames_joined': 600, 'corrupt_final_frame_rejected': True,
               'source_kind': 'synthetic_native_sample',
               'diagnostic_only': True, 'delivery_ready': False}
    (P / 'motion-finalizer-proof.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'frames_joined': 600, 'corrupt_final_frame_rejected': True}))


if __name__ == '__main__':
    main()
