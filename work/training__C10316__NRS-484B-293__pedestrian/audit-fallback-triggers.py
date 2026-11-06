"""Independent raw-row audit of C10316 synthetic fallback crossings."""
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    receipt = json.loads((HERE / 'fallback-trigger-summary.json').read_text())
    assert receipt['source_kind'] == 'synthetic_cpu_fixture'
    assert not any(receipt[key] for key in ('selected', 'original_native_observed', 'original_pixels_observed'))
    root = REPO / receipt['source_dir']
    expected = {'baseline': (False, False, False), 'spawn': (True, False, False),
                'tracking': (False, True, False), 'visibility': (False, False, True)}
    raw = {}
    for label, flags in expected.items():
        path = root / (label + '.jsonl')
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        assert len(rows) == 240
        assert all(row['source_kind'] == 'synthetic_cpu_fixture' for row in rows)
        assert [row['native_frame'] for row in rows] == list(range(100, 340))
        assert [row['time_s'] for row in rows] == [round(i / 20, 4) for i in range(240)]
        clearance = max(0, -2 - max(point[0] for point in rows[0]['pedestrian_footprint_xy_m']))
        errors = sum(math.dist(row['pedestrian_xy_m'], row['requested_xy_m']) > .2 for row in rows)
        fraction = {role: sum(row['synthetic_camera_annotation'][role] for row in rows) / 240
                    for role in ('approach', 'reference_corner')}
        measured = receipt['cases'][label]
        assert measured['source_sha256'] == sha(path)
        assert math.isclose(measured['spawn_clearance_m'], clearance, abs_tol=1e-9)
        assert measured['path_error_frames_over_0_2_m'] == errors
        assert measured['camera_visible_fraction'] == fraction
        assert (clearance < 1, errors >= 10, min(fraction.values()) < .95) == flags
        assert tuple(measured['fallback' + str(i) + '_trigger'] for i in (1, 2, 3)) == flags
        assert not measured['original_native_observed'] and not measured['original_pixels_observed']
        raw[label] = rows
    baseline = raw['baseline']
    assert all(raw['spawn'][i] == baseline[i] for i in range(1, 240))
    assert all(raw['tracking'][i] == baseline[i] for i in list(range(70)) + list(range(80, 240)))
    assert all(raw['visibility'][i] == baseline[i] for i in range(20, 240))
    assert receipt['cases']['changed_hash']['rejected'] is True
    assert receipt['cases']['wrong_kind']['rejected'] is True
    assert all(row['source_kind'] == 'original_native_capture' for row in
        (json.loads(line) for line in (root / 'wrong_kind.jsonl').read_text().splitlines()))
    print(json.dumps({'source_rows_audited': 960, 'distinct_crossings': 3,
                      'source_hash_negative': True, 'provenance_negative': True,
                      'original_observations': 0}))


if __name__ == '__main__':
    main()
