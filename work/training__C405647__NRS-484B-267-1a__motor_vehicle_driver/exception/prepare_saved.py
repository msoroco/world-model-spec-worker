"""Join synthetic Native-coordinate requests and separate cue review on CPU."""
import hashlib
import json
from pathlib import Path
import shutil

from measure_saved import FRAME, LAW_SHA256, measure

NAMES = ('native-requests.jsonl', 'synthetic-officer-visibility.jsonl',
         'video_frames.jsonl', 'direction-review.json', 'officer_reference.source')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def prepare(source, output, case):
    source, output = Path(source), Path(output)
    if case not in ('exception_1_1', 'exception_1_2'):
        raise ValueError('Unknown exception case')
    for name in NAMES:
        if not (source / name).is_file():
            raise ValueError('Missing saved source: ' + name)
    review = json.loads((source / 'direction-review.json').read_text())
    if review.get('source_kind') != 'synthetic_cpu' or \
            review.get('source_sha256') != sha(source / 'officer_reference.source'):
        raise ValueError('Direction review source hash or provenance differs')
    native = rows(source / 'native-requests.jsonl')
    visible = rows(source / 'synthetic-officer-visibility.jsonl')
    videos = rows(source / 'video_frames.jsonl')
    annotations = review.get('frames')
    if not isinstance(annotations, list) or \
            any(len(x) != 480 for x in (native, visible, videos, annotations)):
        raise ValueError('Saved source frame count differs')
    saved = []
    for i, (n, v, video, annotation) in enumerate(zip(native, visible, videos, annotations)):
        if n.get('frame') != i or v.get('frame') != i or \
                video.get('video_frame') != i or video.get('native_frame') != i or \
                annotation.get('frame') != i or n.get('time_s') != round(i / 20, 4) or \
                v.get('time_s') != n['time_s'] or video.get('time_s') != n['time_s']:
            raise ValueError('Native/video/direction frame join differs')
        if annotation.get('cue_visible') != v.get('direction_cue_in_frame') or \
                type(annotation.get('cue_visible')) is not bool:
            raise ValueError('Direction cue annotation differs from source')
        if annotation.get('identity_verified') or annotation.get('communication_verified'):
            raise ValueError('Synthetic direction promoted to physical proof')
        requested = n['officer_direction_request']['requested']
        if bool(requested) != (case == 'exception_1_2' and
                              n['officer_direction_request']['content'] == 'remain_in_inner_lane'):
            raise ValueError('Direction request content differs')
        subject, approach = n['subject_request'], n['approach_request']
        sx, sy = float(subject['x_m']), -float(subject['y_m'])
        ax, ay = float(approach['x_m']), -float(approach['y_m'])
        body = [[round(sx + dx, 4), round(sy + dy, 4)] for dx, dy in
                ((-2.25, -.9), (-2.25, .9), (2.25, -.9), (2.25, .9))]
        saved.append({'frame': i, 'time_s': n['time_s'], 'native_frame': i,
                      'video_frame': i, 'coordinate_frame': FRAME,
                      'source_kind': 'synthetic_cpu',
                      'subject': {'x_m': sx, 'y_m': sy},
                      'approach': {'x_m': ax, 'y_m': ay},
                      'subject_body_xy_m': body,
                      'direction_requested': requested,
                      'direction_review': annotation})
    if output.exists():
        raise ValueError('Retain prior saved packet; choose a new output directory')
    output.mkdir(parents=True)
    for name in NAMES:
        shutil.copyfile(source / name, output / name)
    scope = json.loads((Path(__file__).parent / 'statutory-scope.json').read_text())
    if scope.get('assignment_law_text_sha256') != LAW_SHA256:
        raise ValueError('Law source hash differs')
    scope.update(case_suffix=case, coordinate_frame=FRAME,
                 source_kind='synthetic_cpu',
                 native_source_hashes={name: sha(output / name) for name in NAMES},
                 officer_identity_or_direction_verified=False,
                 physical_success_claimed=False)
    (output / 'source-scope.json').write_text(json.dumps(scope, sort_keys=True) + '\n')
    (output / 'actor-frames.jsonl').write_text(''.join(
        json.dumps(row, sort_keys=True) + '\n' for row in saved))
    result = measure(output)
    (output / 'saved-preview.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--case', required=True)
    args = parser.parse_args()
    print(json.dumps(prepare(args.source, args.output, args.case), indent=2))
