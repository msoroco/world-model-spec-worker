"""Source-bound saved geometry measurements for the C405647 controlled pair.

This deliberately reports relative motion and clearance without deciding when
an approach is legally immediate or whether a lamp or vehicle is qualified.
"""
import hashlib
import json
import math
from pathlib import Path

LAW_SHA256 = '05acca6d9cdbea0707963bae635458009d558500a8d40a96ce4fa9d8ca5a8d86'
SUBJECT_LENGTH_M = 4.5
SUBJECT_WIDTH_M = 1.8
INNER_LANE_OUTER_EDGE_Y_M = -3.5
COORDINATE_FRAME = 'authored_opendrive_xy'


def _hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def measure(folder):
    folder = Path(folder)
    for name in ('source-scope.json', 'actor-frames.jsonl'):
        if not (folder / name).is_file():
            raise ValueError('Missing required source: ' + name)
    scope = json.loads((folder / 'source-scope.json').read_text())
    if scope.get('assignment_law_text_sha256') != LAW_SHA256:
        raise ValueError('Law source hash differs')
    case = scope.get('case_suffix')
    if case not in ('official_1', 'official_2'):
        raise ValueError('Unknown controlled case')
    if scope.get('coordinate_frame') != COORDINATE_FRAME:
        raise ValueError('Saved coordinate frame differs')
    rows = _rows(folder / 'actor-frames.jsonl')
    if len(rows) != 480:
        raise ValueError('Saved frame count differs')
    gaps = []
    cleared = []
    lamps = []
    for index, row in enumerate(rows):
        if row.get('frame') != index or abs(row.get('time_s', -1) - index / 20) > 1e-5:
            raise ValueError('Saved frame/time order differs')
        if row.get('source_kind') not in ('synthetic_cpu', 'original_native'):
            raise ValueError('Unknown saved provenance')
        if row.get('coordinate_frame') != COORDINATE_FRAME:
            raise ValueError('Saved coordinate frame differs')
        subject = row.get('subject')
        approach = row.get('approach')
        lamp = row.get('front_red_flash_on')
        if not isinstance(subject, dict) or not isinstance(approach, dict) or type(lamp) is not bool:
            raise ValueError('Saved participant or lamp observation absent')
        try:
            sx, sy = float(subject['x_m']), float(subject['y_m'])
            ax, ay = float(approach['x_m']), float(approach['y_m'])
        except (KeyError, TypeError, ValueError) as error:
            raise ValueError('Saved participant position absent') from error
        if abs(ay + 1.75) > 1e-4:
            raise ValueError('Approach lane changed')
        body = row.get('subject_body_xy_m')
        if not isinstance(body, list) or len(body) != 4:
            raise ValueError('Saved subject body footprint absent')
        try:
            vertices = [tuple(float(value) for value in vertex) for vertex in body]
        except (TypeError, ValueError) as error:
            raise ValueError('Saved subject body footprint invalid') from error
        if (any(len(vertex) != 2 or not all(math.isfinite(value) for value in vertex)
                for vertex in vertices) or len(set(vertices)) != 4):
            raise ValueError('Saved subject body footprint invalid')
        if (abs(sum(x for x, _ in vertices) / 4 - sx) > .1 or
                abs(sum(y for _, y in vertices) / 4 - sy) > .1):
            raise ValueError('Saved subject body center differs')
        gaps.append(sx - ax)
        cleared.append(max(y for _, y in vertices) < INNER_LANE_OUTER_EDGE_Y_M)
        lamps.append(lamp)
    if not lamps[0] or not any(a != b for a, b in zip(lamps, lamps[1:])):
        raise ValueError('Flashing lamp sequence absent')
    catchup = next((i for i, gap in enumerate(gaps) if gap <= SUBJECT_LENGTH_M), None)
    if catchup is None:
        raise ValueError('Requested approach never reaches subject')
    clearance = next((i for i, yes in enumerate(cleared) if yes), None)
    return {
        'format': 'c405647-1a-saved-motion-v1', 'case_suffix': case,
        'source_hashes': {'source-scope.json': _hash(folder / 'source-scope.json'),
                          'actor-frames.jsonl': _hash(folder / 'actor-frames.jsonl')},
        'observed_frame_count': len(rows), 'observed_lamp_transitions': sum(
            a != b for a, b in zip(lamps, lamps[1:])),
        'initial_longitudinal_gap_m': gaps[0],
        'catchup_frame': catchup,
        'first_full_body_inner_lane_clearance_frame': clearance,
        'full_body_cleared_before_catchup': clearance is not None and clearance < catchup,
        'body_footprint_source': 'four retained vertices per saved frame',
        'coordinate_frame': COORDINATE_FRAME,
        'provenance_kinds': sorted({row['source_kind'] for row in rows}),
        'vehicle_authority_verified': False, 'lamp_qualification_verified': False,
        'legal_immediacy_or_yield_verdict': None,
        'scope': 'saved geometric motion and lamp state only'
    }


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('folder')
    args = parser.parse_args()
    print(json.dumps(measure(args.folder), indent=2))
