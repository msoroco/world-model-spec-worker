"""Measure source-bound officer cue and motion from retained saved frames."""
import hashlib
import json
from pathlib import Path

LAW_SHA256 = '05acca6d9cdbea0707963bae635458009d558500a8d40a96ce4fa9d8ca5a8d86'
FRAME = 'authored_opendrive_xy'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def measure(folder):
    folder = Path(folder)
    for name in ('source-scope.json', 'actor-frames.jsonl'):
        if not (folder / name).is_file():
            raise ValueError('Missing required source: ' + name)
    scope = json.loads((folder / 'source-scope.json').read_text())
    if scope.get('assignment_law_text_sha256') != LAW_SHA256 or \
            scope.get('coordinate_frame') != FRAME:
        raise ValueError('Law or coordinate source differs')
    case = scope.get('case_suffix')
    if case not in ('exception_1_1', 'exception_1_2'):
        raise ValueError('Unknown exception case')
    frames = rows(folder / 'actor-frames.jsonl')
    if len(frames) != 480:
        raise ValueError('Saved frame count differs')
    cues, requested, gaps = [], [], []
    for i, row in enumerate(frames):
        if row.get('frame') != i or row.get('time_s') != round(i / 20, 4) or \
                row.get('coordinate_frame') != FRAME or \
                row.get('source_kind') != 'synthetic_cpu':
            raise ValueError('Saved frame/time/provenance differs')
        direction = row.get('direction_review')
        if not isinstance(direction, dict) or type(direction.get('cue_visible')) is not bool:
            raise ValueError('Direction review absent')
        if direction.get('identity_verified') or direction.get('communication_verified'):
            raise ValueError('Synthetic direction promoted to physical proof')
        if direction['cue_visible']:
            if direction.get('content') != 'remain_in_inner_lane' or \
                    direction.get('recipient') != 'subject_driver':
                raise ValueError('Synthetic cue content or recipient differs')
            cues.append(i)
        if row.get('direction_requested'):
            requested.append(i)
        subject, approach = row.get('subject'), row.get('approach')
        if not isinstance(subject, dict) or not isinstance(approach, dict):
            raise ValueError('Saved participant absent')
        if abs(float(subject['y_m']) + 1.75) > 1e-4 or \
                abs(float(approach['y_m']) + 1.75) > 1e-4:
            raise ValueError('Paired lane changed')
        body = row.get('subject_body_xy_m')
        if not isinstance(body, list) or len(body) != 4 or \
                abs(sum(float(v[0]) for v in body) / 4 - float(subject['x_m'])) > .1 or \
                abs(sum(float(v[1]) for v in body) / 4 - float(subject['y_m'])) > .1:
            raise ValueError('Saved body footprint differs')
        gaps.append(float(subject['x_m']) - float(approach['x_m']))
    if (case == 'exception_1_1' and (cues or requested)) or \
            (case == 'exception_1_2' and (not cues or not requested)):
        raise ValueError('Controlled exception request or cue differs')
    catchup = next((i for i, gap in enumerate(gaps) if gap <= 4.5), None)
    if catchup is None:
        raise ValueError('Approach never reaches subject')
    return {'format': 'c405647-exception-saved-measurement-v1',
            'case_suffix': case,
            'source_hashes': {n: sha(folder / n) for n in
                              ('source-scope.json', 'actor-frames.jsonl')},
            'observed_frame_count': len(frames),
            'catchup_frame': catchup,
            'first_requested_direction_frame': requested[0] if requested else None,
            'first_synthetic_cue_frame': cues[0] if cues else None,
            'synthetic_cue_frames': len(cues),
            'cue_overlaps_request': bool(set(cues) & set(requested)),
            'physical_officer_identity_or_communication_verified': False,
            'legal_exception_verdict': None,
            'scope': 'synthetic saved cue and motion integration only'}


if __name__ == '__main__':
    import sys
    print(json.dumps(measure(sys.argv[1]), indent=2))
