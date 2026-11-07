"""Bind proposed Native actor capture to a separately attributed pixel review.

The CPU mock mode exercises the same file, decode and frame joins. It never
turns an authored request or a mock annotation into an observed legal fact.
"""
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess

from measure_saved import FRAME, LAW_SHA256

NAMES = ('observed-actors.jsonl', 'video_frames.jsonl',
         'officer-direction-review.json', 'officer_reference.mkv')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def decoded_hashes(path, ffmpeg=None):
    command = ffmpeg or shutil.which('ffmpeg')
    if not command:
        raise ValueError('FFmpeg decoder absent')
    result = subprocess.run([str(command), '-hide_banner', '-loglevel', 'error',
                             '-i', str(path), '-map', '0:v:0', '-f', 'framehash',
                             '-hash', 'sha256', '-'], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=180, check=False)
    if result.returncode:
        raise ValueError('Officer video decode failed: ' + result.stderr[-300:])
    hashes = []
    for line in result.stdout.splitlines():
        if line.startswith('#') or not line.strip():
            continue
        cells = [cell.strip() for cell in line.split(',')]
        if len(cells) != 6 or cells[0] != '0' or len(cells[5]) != 64 or \
                any(char not in '0123456789abcdef' for char in cells[5]):
            raise ValueError('Decoded officer framehash malformed')
        hashes.append(cells[5])
    if len(hashes) != 480:
        raise ValueError('Decoded officer frame count differs')
    return hashes


def point(value):
    if not isinstance(value, list) or len(value) != 2:
        raise ValueError('Native coordinate absent')
    x, y = map(float, value)
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError('Native coordinate nonfinite')
    return [x, -y]


def prepare(source, output, case, ffmpeg=None):
    source, output = Path(source), Path(output)
    if case not in ('exception_1_1', 'exception_1_2'):
        raise ValueError('Unknown exception case')
    for name in NAMES:
        if not (source / name).is_file():
            raise ValueError('Missing original-path source: ' + name)
    review = json.loads((source / NAMES[2]).read_text())
    mode = review.get('source_kind')
    if mode not in ('original_pixel_review', 'cpu_mock_original_path'):
        raise ValueError('Direction review provenance differs')
    if mode == 'original_pixel_review' and not review.get('reviewer'):
        raise ValueError('Original officer review attribution absent')
    if mode == 'cpu_mock_original_path' and review.get('reviewer') != 'cpu_test':
        raise ValueError('CPU mock reviewer differs')
    if review.get('source_video_sha256') != sha(source / NAMES[3]):
        raise ValueError('Officer review video source hash differs')
    actors, videos, annotations = rows(source / NAMES[0]), rows(source / NAMES[1]), review.get('frames')
    if not isinstance(annotations, list) or any(len(x) != 480 for x in (actors, videos, annotations)):
        raise ValueError('Original-path frame count differs')
    hashes = decoded_hashes(source / NAMES[3], ffmpeg)
    saved = []
    prior_time = None
    for i, (actor, video, note) in enumerate(zip(actors, videos, annotations)):
        kind = 'original_native' if mode == 'original_pixel_review' else 'cpu_mock'
        native_id = actor.get('native_frame')
        if actor.get('source_kind') != kind or actor.get('frame') != i or \
                video.get('video_frame') != i or video.get('native_frame') != native_id or \
                video.get('carla_frame') != native_id or note.get('video_frame') != i or \
                note.get('native_frame') != native_id:
            raise ValueError('Native actor/video/officer frame join differs')
        if note.get('pixel_frame_sha256') != hashes[i]:
            raise ValueError('Officer review decoded pixel frame hash differs')
        if actor.get('actual_direction_identity_content_recipient_observed') is not None:
            raise ValueError('Requested direction substituted for observed review')
        if type(note.get('cue_visible')) is not bool or \
                type(note.get('identity_verified')) is not bool or \
                type(note.get('communication_verified')) is not bool:
            raise ValueError('Officer review observation absent')
        if mode == 'cpu_mock_original_path' and (note['identity_verified'] or note['communication_verified']):
            raise ValueError('CPU mock promoted to physical officer proof')
        if note['communication_verified'] and not (note['identity_verified'] and
                note.get('content') and note.get('recipient') and note.get('source_note')):
            raise ValueError('Officer communication attribution incomplete')
        if note['cue_visible'] and not (note.get('content') and note.get('recipient')):
            raise ValueError('Officer cue annotation incomplete')
        time_s = float(actor['time_s'])
        if not math.isfinite(time_s) or (prior_time is not None and abs(time_s - prior_time - .05) > .01) or \
                abs(float(video['time_s']) - time_s) > .001:
            raise ValueError('Native actor/video time join differs')
        prior_time = time_s
        participants = actor.get('actors', {})
        subject, approach = participants.get('subject'), participants.get('approach')
        if not isinstance(subject, dict) or not isinstance(approach, dict):
            raise ValueError('Native participant absent')
        body = subject.get('native_body_xy_m')
        if not isinstance(body, list) or len(body) != 4:
            raise ValueError('Native body footprint absent')
        saved.append({'frame': i, 'time_s': round(i / 20, 4), 'native_frame': native_id,
                      'video_frame': i, 'coordinate_frame': FRAME, 'source_kind': mode,
                      'subject': dict(zip(('x_m', 'y_m'), point(subject['native_center_xy_m']))),
                      'approach': dict(zip(('x_m', 'y_m'), point(approach['native_center_xy_m']))),
                      'subject_body_xy_m': [point(vertex) for vertex in body],
                      'direction_requested': actor.get('officer_direction_requested'),
                      'direction_review': note})
    if output.exists():
        raise ValueError('Retain prior packet; choose a new output directory')
    output.mkdir(parents=True)
    scope = json.loads((Path(__file__).parent / 'statutory-scope.json').read_text())
    if scope.get('assignment_law_text_sha256') != LAW_SHA256:
        raise ValueError('Law source hash differs')
    scope.update(case_suffix=case, coordinate_frame=FRAME, source_kind=mode,
                 native_source_hashes={name: sha(source / name) for name in NAMES},
                 officer_identity_or_direction_verified=False,
                 physical_success_claimed=False)
    (output / 'source-scope.json').write_text(json.dumps(scope, sort_keys=True) + '\n')
    (output / 'actor-frames.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in saved))
    cues = [row['frame'] for row in saved if row['direction_review']['cue_visible']]
    requests = [row['frame'] for row in saved if row['direction_requested']]
    catchup = next((row['frame'] for row in saved if
                    row['subject']['x_m'] - row['approach']['x_m'] <= 4.5), None)
    result = {'format': 'c405647-exception-original-path-v1', 'case_suffix': case,
              'source_kind': mode, 'frames': len(saved), 'source_hashes': scope['native_source_hashes'],
              'cue_frames': len(cues), 'first_cue_frame': cues[0] if cues else None,
              'first_requested_direction_frame': requests[0] if requests else None,
              'cue_overlaps_request': bool(set(cues) & set(requests)),
              'approach_catchup_frame': catchup,
              'verified_communication_frames': sum(row['direction_review']['communication_verified'] for row in saved),
              'physical_success_claimed': False, 'legal_exception_verdict': None}
    (output / 'saved-preview.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--ffmpeg')
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output, args.case, args.ffmpeg), indent=2))
