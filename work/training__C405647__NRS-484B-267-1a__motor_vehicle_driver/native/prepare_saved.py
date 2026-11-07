"""Join observed actor frames to separately reviewed lamp pixels for saved analysis.

The bridge changes CARLA's reflected y coordinates to authored OpenDRIVE y.
It never derives a red-lamp observation from CARLA Special1 control state.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess

from measure_saved import LAW_SHA256, COORDINATE_FRAME, measure

BASE_NAMES = ('observed-actors.jsonl', 'video_frames.jsonl', 'front-lamp-review.json')


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read_rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def _authored(point):
    if not isinstance(point, (tuple, list)) or len(point) != 2:
        raise ValueError('Native XY point absent')
    x, y = float(point[0]), float(point[1])
    if not math.isfinite(x) or not math.isfinite(y):
        raise ValueError('Native XY point nonfinite')
    return [x, -y]


def _decoded_frame_hashes(path, ffmpeg):
    executable = ffmpeg or shutil.which('ffmpeg')
    if not executable:
        raise ValueError('Original lamp video decoder absent')
    result = subprocess.run([str(executable), '-hide_banner', '-loglevel', 'error',
                             '-i', str(path), '-map', '0:v:0', '-f', 'framehash',
                             '-hash', 'sha256', '-'], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=180, check=False)
    if result.returncode:
        raise ValueError('Original lamp video decode failed')
    hashes = []
    for line in result.stdout.splitlines():
        if line.startswith('#') or not line.strip():
            continue
        columns = [part.strip() for part in line.split(',')]
        if len(columns) != 6 or columns[0] != '0' or len(columns[5]) != 64 or \
                any(char not in '0123456789abcdef' for char in columns[5]):
            raise ValueError('Original lamp video framehash malformed')
        hashes.append(columns[5])
    if len(hashes) != 480:
        raise ValueError('Original lamp video decoded frame count differs')
    return hashes


def prepare(source, output, case, ffmpeg=None):
    source, output = Path(source), Path(output)
    if case not in ('witness_1', 'witness_2'):
        raise ValueError('Unknown controlled case')
    review_path = source / 'front-lamp-review.json'
    if not review_path.is_file():
        raise ValueError('Missing Native or lamp-review source: front-lamp-review.json')
    review = json.loads(review_path.read_text())
    kind = review.get('source_kind')
    if kind not in ('synthetic_cpu', 'original_pixel_review'):
        raise ValueError('Lamp review provenance differs')
    video_name = 'front_lamp.mkv' if kind == 'original_pixel_review' else 'front_lamp.source'
    names = (*BASE_NAMES, video_name)
    for name in names:
        if not (source / name).is_file():
            raise ValueError('Missing Native or lamp-review source: ' + name)
    actors = _read_rows(source / BASE_NAMES[0])
    frames = _read_rows(source / BASE_NAMES[1])
    review = json.loads((source / BASE_NAMES[2]).read_text())
    if len(actors) != len(frames) or len(actors) != 480:
        raise ValueError('Original frame count or join differs')
    video_sha = _sha(source / video_name)
    if review.get('source_video_sha256') != video_sha:
        raise ValueError('Lamp review video source hash differs')
    annotations = review.get('frames')
    if not isinstance(annotations, list) or len(annotations) != 480:
        raise ValueError('Lamp review frame count differs')
    if kind == 'original_pixel_review' and not review.get('reviewer'):
        raise ValueError('Original lamp review attribution absent')
    decoded_hashes = _decoded_frame_hashes(source / video_name, ffmpeg) if \
        kind == 'original_pixel_review' else None
    saved = []
    prior_time = None
    for index, (row, video, annotation) in enumerate(zip(actors, frames, annotations)):
        expected_kind = 'original_native' if kind == 'original_pixel_review' else 'synthetic_cpu'
        if row.get('source_kind') != expected_kind:
            raise ValueError('Actor/review provenance differs')
        native_frame = row.get('native_frame')
        if (row.get('frame') != index or video.get('video_frame') != index or
                video.get('native_frame') != native_frame or
                video.get('carla_frame') != native_frame or
                annotation.get('native_frame') != native_frame or
                annotation.get('video_frame') != index):
            raise ValueError('Native actor/video/lamp frame join differs')
        if row.get('front_red_flash_on') is not None:
            raise ValueError('Raw Native light control substituted for pixel review')
        if type(annotation.get('front_red_flash_on')) is not bool:
            raise ValueError('Lamp pixel annotation absent')
        if decoded_hashes is not None and annotation.get('pixel_frame_sha256') != decoded_hashes[index]:
            raise ValueError('Lamp review decoded pixel frame hash differs')
        time_s = float(row['time_s'])
        if not math.isfinite(time_s) or (prior_time is not None and
                                         abs(time_s - prior_time - .05) > .01):
            raise ValueError('Native frame time cadence differs')
        if abs(float(video['time_s']) - time_s) > .001:
            raise ValueError('Native actor/video time join differs')
        prior_time = time_s
        participant = row.get('actors', {})
        subject, approach = participant.get('subject'), participant.get('approach')
        if not isinstance(subject, dict) or not isinstance(approach, dict):
            raise ValueError('Native participant absent')
        body = subject.get('native_body_xy_m')
        if not isinstance(body, list) or len(body) != 4:
            raise ValueError('Native body footprint absent')
        saved.append({'frame': index, 'time_s': index / 20,
                      'native_frame': native_frame, 'video_frame': index,
                      'coordinate_frame': COORDINATE_FRAME,
                      'source_kind': expected_kind,
                      'subject': dict(zip(('x_m', 'y_m'), _authored(subject['native_center_xy_m']))),
                      'approach': dict(zip(('x_m', 'y_m'), _authored(approach['native_center_xy_m']))),
                      'subject_body_xy_m': [_authored(vertex) for vertex in body],
                      'front_red_flash_on': annotation['front_red_flash_on']})
    if output.exists():
        raise ValueError('Retain prior saved packet; choose a new output directory')
    output.mkdir(parents=True)
    for name in names:
        shutil.copyfile(source / name, output / name)
    scope = json.loads((Path(__file__).parent / 'source-scope.json').read_text())
    if scope.get('assignment_law_text_sha256') != LAW_SHA256:
        raise ValueError('Law source hash differs')
    scope.update(case_suffix=case, coordinate_frame=COORDINATE_FRAME,
                 source_kind=expected_kind,
                 native_source_hashes={name: _sha(output / name) for name in names},
                 front_red_lamp_qualification_verified=False,
                 vehicle_authority_verified=False,
                 physical_success_claimed=False)
    (output / 'source-scope.json').write_text(json.dumps(scope, sort_keys=True) + '\n')
    (output / 'actor-frames.jsonl').write_text(''.join(
        json.dumps(row, sort_keys=True) + '\n' for row in saved))
    measured = measure(output)
    (output / 'saved-motion-preview.json').write_text(json.dumps(measured, indent=2) + '\n')
    return {'passed': True, 'case_suffix': case, 'source_kind': expected_kind,
            'frames': len(saved), 'measurement': measured,
            'physical_success_claimed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--ffmpeg')
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output, args.case, args.ffmpeg), indent=2))
