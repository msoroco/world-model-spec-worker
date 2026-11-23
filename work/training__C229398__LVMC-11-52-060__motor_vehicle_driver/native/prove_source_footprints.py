"""Prove raw actor snapshot conversion feeds the curb projection measure."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile

from projection_measure import FEET_PER_METER, measure, sha
from source_footprints import build

ROOT = Path(__file__).resolve().parents[2]


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def reject(call, expected):
    try:
        call()
    except ValueError as exc:
        assert expected in str(exc), (expected, str(exc))
        return
    raise AssertionError('Expected rejection: ' + expected)


def actor(actor_id, center_y, half_y, parent=None):
    value = {'actor_id': actor_id, 'center_xy_m': [0, center_y],
             'half_extent_xy_m': [0.5, half_y], 'yaw_deg': 0}
    if parent:
        value['attached_to'] = parent
    return value


def run():
    scratch = ROOT / '.runtime-work'
    scratch.mkdir(exist_ok=True)
    results = []
    with tempfile.TemporaryDirectory(dir=scratch, prefix='c229398-actors-') as tmp:
        tmp = Path(tmp)
        curb_path, raw_path, footprints_path = (tmp / 'curb.json', tmp / 'actors.jsonl',
                                                 tmp / 'footprints.jsonl')
        source_path = tmp / 'curb-source.txt'
        source_path.write_text('synthetic curb')
        write(curb_path, {'format': 'c229398-reviewed-curb-v1', 'reviewed': True,
                          'source_kind': 'synthetic_native_sample',
                          'source_sha256': hashlib.sha256(b'synthetic curb').hexdigest(),
                          'source_file': source_path.name,
                          'origin_xy_m': [0, 0], 'street_normal_xy': [0, 1]})
        for feet in (14, 15, 16):
            maximum_y = feet / FEET_PER_METER
            vehicle = actor('ego', maximum_y - 1.5, 0.5)
            load = actor('load', maximum_y - 0.5, 0.5, 'ego')
            rows = [{'frame': frame, 'source_kind': 'synthetic_native_sample',
                     'actors': {'vehicle': vehicle, 'load': load, 'trailer': None}}
                    for frame in range(600)]
            raw_path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            receipt = build(raw_path, curb_path, footprints_path, allow_synthetic=True)
            result = measure(curb_path, footprints_path, allow_synthetic=True)
            assert receipt['footprints_sha256'] == result['footprints_sha256']
            assert abs(result['maximum_projection_perpendicular_to_curb_ft'] - feet) < 1e-9
            results.append({'requested_ft': feet, 'measured_ft':
                            result['maximum_projection_perpendicular_to_curb_ft'],
                            'raw_actors_sha256': receipt['raw_actors_sha256'],
                            'footprints_sha256': receipt['footprints_sha256']})
            if feet != 15:
                continue
            reject(lambda: build(raw_path, curb_path, footprints_path),
                   'Actor frame/source identity mismatch')
            bad = copy.deepcopy(rows)
            bad[0]['actors']['load']['attached_to'] = 'other'
            raw_path.write_text(''.join(json.dumps(row) + '\n' for row in bad))
            reject(lambda: build(raw_path, curb_path, footprints_path,
                                 allow_synthetic=True), 'Load/trailer association missing')
            bad = copy.deepcopy(rows)
            bad[0]['actors']['trailer'] = actor('trailer', maximum_y + 1, 0.5, 'ego')
            raw_path.write_text(''.join(json.dumps(row) + '\n' for row in bad))
            build(raw_path, curb_path, footprints_path, allow_synthetic=True)
            trailer = measure(curb_path, footprints_path, allow_synthetic=True)
            assert trailer['maximum_projection_perpendicular_to_curb_ft'] > 19
            bad[0]['actors']['trailer']['actor_id'] = 'load'
            raw_path.write_text(''.join(json.dumps(row) + '\n' for row in bad))
            reject(lambda: build(raw_path, curb_path, footprints_path,
                                 allow_synthetic=True), 'Actor identity reused across parts')
    return {'format': 'c229398-source-footprints-cpu-proof-v1', 'passed': True,
            'cases': results, 'source_kind': 'synthetic_native_sample',
            'negative_checks': ['production_relabels_synthetic',
                                'wrong_load_association', 'duplicate_actor_identity'],
            'trailer_maximum_changes_measurement': True,
            'original_native_observed': False,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
