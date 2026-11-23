"""Exercise source-bound 15-foot projection measurement with synthetic rows."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile

from projection_measure import FEET_PER_METER, measure, sha

ROOT = Path(__file__).resolve().parents[2]


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def rejected(call, message):
    try:
        call()
    except ValueError as exc:
        assert message in str(exc), (message, str(exc))
        return
    raise AssertionError('Expected rejection: ' + message)


def run():
    scratch = ROOT / '.runtime-work'
    scratch.mkdir(exist_ok=True)
    outcomes = []
    with tempfile.TemporaryDirectory(dir=scratch, prefix='c229398-projection-') as tmp:
        tmp = Path(tmp)
        curb_path = tmp / 'curb.json'
        footprints_path = tmp / 'footprints.jsonl'
        source_path = tmp / 'curb-source.txt'
        source_path.write_text('synthetic curb')
        curb = {'format': 'c229398-reviewed-curb-v1', 'reviewed': True,
                'source_kind': 'synthetic_native_sample',
                'source_sha256': hashlib.sha256(b'synthetic curb').hexdigest(),
                'source_file': source_path.name,
                'origin_xy_m': [0, 0], 'street_normal_xy': [0, 1]}
        write(curb_path, curb)
        for target_ft, expected in ((14, 'below'), (15, 'at'), (16, 'above')):
            y = target_ft / FEET_PER_METER
            vehicle = {'vertices_xy_m': [[-1, 0], [1, 0], [1, y - 1], [-1, y - 1]]}
            load = {'vertices_xy_m': [[-0.5, y - 1], [0.5, y - 1], [0.5, y], [-0.5, y]]}
            rows = [{'frame': i, 'source_kind': 'synthetic_native_sample',
                     'curb_sha256': sha(curb_path),
                     'participants': {'vehicle': vehicle, 'load': load, 'trailer': None}}
                    for i in range(600)]
            footprints_path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            got = measure(curb_path, footprints_path, allow_synthetic=True)
            assert got['frames'] == 600 and got['duration_seconds'] == 30
            assert abs(got['maximum_projection_perpendicular_to_curb_ft'] - target_ft) < 1e-9
            assert got['source_kind'] == 'synthetic_native_sample'
            assert not got['physical_acceptance_claimed'] and not got['legal_acceptance_claimed']
            outcomes.append({'requested_ft': target_ft, 'boundary': expected,
                             'measured_ft': got['maximum_projection_perpendicular_to_curb_ft'],
                             'footprints_sha256': got['footprints_sha256']})
            if target_ft != 15:
                continue
            rejected(lambda: measure(curb_path, footprints_path), 'Original curb source review required')
            bad = copy.deepcopy(rows)
            bad[300]['participants']['trailer'] = {'vertices_xy_m':
                [[-0.3, y], [0.3, y], [0.3, y + 1], [-0.3, y + 1]]}
            footprints_path.write_text(''.join(json.dumps(row) + '\n' for row in bad))
            trailer = measure(curb_path, footprints_path, allow_synthetic=True)
            assert trailer['maximum_projection_perpendicular_to_curb_ft'] > 18
            bad[300]['participants'].pop('load')
            footprints_path.write_text(''.join(json.dumps(row) + '\n' for row in bad))
            rejected(lambda: measure(curb_path, footprints_path, allow_synthetic=True),
                     'Vehicle, load and trailer inventories required')
            rows[200]['curb_sha256'] = '0' * 64
            footprints_path.write_text(''.join(json.dumps(row) + '\n' for row in rows))
            rejected(lambda: measure(curb_path, footprints_path, allow_synthetic=True),
                     'Curb calibration changed')
            footprints_path.write_text(''.join(json.dumps(row) + '\n' for row in rows[:-1]))
            rejected(lambda: measure(curb_path, footprints_path, allow_synthetic=True),
                     'Missing or extra footprint frame')
            source_path.write_text('changed curb')
            rejected(lambda: measure(curb_path, footprints_path, allow_synthetic=True),
                     'Curb source bytes changed')
            source_path.write_text('synthetic curb')
    return {'format': 'c229398-projection-measure-cpu-proof-v1', 'passed': True,
            'source_kind': 'synthetic_native_sample', 'cases': outcomes,
            'negative_checks': ['production_relabels_synthetic', 'missing_part_inventory',
                                'changed_curb_hash', 'missing_frame',
                                'changed_curb_source_bytes'],
            'trailer_maximum_changes_measurement': True,
            'original_native_observed': False,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps(run(), indent=2))
