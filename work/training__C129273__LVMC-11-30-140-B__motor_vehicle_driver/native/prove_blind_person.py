"""Thirty-second synthetic source diagnostics for a stop and precaution comparison."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from measure_blind_person import FRAMES, RATE_HZ, SOURCES, measure, sha

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def write(path, obj):
    path.write_text(json.dumps(obj, sort_keys=True) + '\n')


def refresh(folder):
    write(folder / 'source-manifest.json', {
        'format': 'c129273-retained-sources-v1',
        'sha256': {name: sha(folder / name) for name in SOURCES},
    })


def make(folder, mode, marker='white_red_tipped_cane', blindness='wholly'):
    folder.mkdir()
    write(folder / 'road.json', {
        'cell_id': 'C129273', 'layout': 'mountain_road', 'maneuver': 'travel',
        'control': 'blind_pedestrian', 'ego_lane_y_m': 0.0, 'pedestrian_x_m': 50.0,
        'source_kind': 'synthetic_native_sample',
    })
    write(folder / 'pedestrian.json', {
        'person_id': 202, 'blindness': blindness, 'marker': marker,
        'marker_source': 'synthetic_native_sample',
    })
    rows = []
    x = 0.0
    release = {'stop': 260, 'early_release': 140, 'nonstop': None}[mode]
    for i in range(FRAMES):
        if mode == 'nonstop':
            speed = 8.0
        elif i < 80:
            speed = 8.0
        elif i <= 119:
            speed = round(8.0 - 0.2 * (i - 79), 6)
        elif release is not None and i >= release:
            speed = min(5.0, round(0.2 * (i - release + 1), 6))
        else:
            speed = 0.0
        x = round(x + speed / RATE_HZ, 6)
        person_y = min(5.0, max(0.0, round((i - 229) * 0.2, 6)))
        rows.append({
            'frame': i, 'native_frame': 1000 + i, 'time_s': i / RATE_HZ,
            'ego_id': 101, 'ego_role': 'motor_vehicle_driver',
            'person_id': 202, 'ego_front_x_m': x, 'ego_speed_mps': speed,
            'person_y_m': person_y, 'person_marker_observed': i >= 70,
        })
    (folder / 'frames.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    refresh(folder)


def reject(folder, expected):
    try:
        measure(folder)
    except ValueError as error:
        assert expected in str(error), str(error)
        return str(error)
    raise AssertionError('Bad source was accepted: ' + expected)


def mutate_row(folder, frame, key, value):
    rows = [json.loads(line) for line in (folder / 'frames.jsonl').read_text().splitlines()]
    rows[frame][key] = value
    (folder / 'frames.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    refresh(folder)


def prove():
    output_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '')).resolve()
    assert ROOT / '.runtime-work' in output_root.parents
    with tempfile.TemporaryDirectory(prefix='c129273-source-', dir=ROOT / '.runtime-work') as name:
        scratch = Path(name)
        scenarios = {
            'red_tipped_stop': ('stop', 'white_red_tipped_cane', 'wholly'),
            'white_cane_partial_stop': ('stop', 'white_cane', 'partially'),
            'assisted_stop': ('stop', 'assisted_person', 'wholly'),
            'red_tipped_nonstop': ('nonstop', 'white_red_tipped_cane', 'wholly'),
            'red_tipped_early_release': ('early_release', 'white_red_tipped_cane', 'wholly'),
        }
        results = {}
        for key, args in scenarios.items():
            make(scratch / key, *args)
            results[key] = measure(scratch / key)
        for key in ('red_tipped_stop', 'white_cane_partial_stop', 'assisted_stop'):
            row = results[key]
            assert row['first_full_stop_frame'] == 119
            assert row['first_post_stop_release_frame'] == 260
            assert row['first_geometric_contact_frame'] is None
            assert row['release_person_y_m'] == 5.0
            assert row['minimum_surface_gap_before_release_m'] > 0
        assert results['red_tipped_stop']['first_marker_observed_frame'] == 70
        assert results['red_tipped_stop']['first_deceleration_frame'] == 80
        assert results['red_tipped_nonstop']['first_full_stop_frame'] is None
        assert results['red_tipped_nonstop']['first_geometric_contact_frame'] is not None
        assert results['red_tipped_early_release']['first_full_stop_frame'] == 119
        assert results['red_tipped_early_release']['first_post_stop_release_frame'] == 140
        assert results['red_tipped_early_release']['first_geometric_contact_frame'] is not None
        assert results['red_tipped_early_release']['release_person_y_m'] == 0.0
        assert results['red_tipped_stop']['source_sha256']['road.json'] == results['red_tipped_nonstop']['source_sha256']['road.json']
        assert results['red_tipped_stop']['source_sha256']['pedestrian.json'] == results['red_tipped_nonstop']['source_sha256']['pedestrian.json']
        negatives = {}
        base = scratch / 'red_tipped_stop'
        bad = scratch / 'tampered_hash'; shutil.copytree(base, bad)
        mutate_row(bad, 100, 'ego_speed_mps', 7.7)
        (bad / 'frames.jsonl').write_text((bad / 'frames.jsonl').read_text().replace('"ego_speed_mps": 7.7', '"ego_speed_mps": 7.8', 1))
        negatives['source_hash'] = reject(bad, 'source hash mismatch')
        bad = scratch / 'missing_frame'; shutil.copytree(base, bad)
        lines = (bad / 'frames.jsonl').read_text().splitlines()
        (bad / 'frames.jsonl').write_text('\n'.join(lines[:-1]) + '\n')
        refresh(bad); negatives['missing_frame'] = reject(bad, '600 source frames required')
        bad = scratch / 'wrong_actor'; shutil.copytree(base, bad)
        mutate_row(bad, 150, 'person_id', 999)
        negatives['actor_join'] = reject(bad, 'frame/time/actor join')
        bad = scratch / 'motion_break'; shutil.copytree(base, bad)
        mutate_row(bad, 150, 'ego_front_x_m', -100.0)
        negatives['motion_continuity'] = reject(bad, 'ego displacement/speed continuity')
        bad = scratch / 'missing_marker_source'; shutil.copytree(base, bad)
        person = json.loads((bad / 'pedestrian.json').read_text())
        person.pop('marker_source'); write(bad / 'pedestrian.json', person)
        refresh(bad); negatives['marker_source'] = reject(bad, 'person identity/blindness/marker source')
    receipt = {
        'format': 'c129273-blind-person-source-proof-v1',
        'assignment_id': HERE.parent.name, 'frames': FRAMES,
        'rate_hz': RATE_HZ, 'duration_s': FRAMES / RATE_HZ,
        'positive_diagnostic_scenarios': results, 'negative_source_checks': negatives,
        'measurement_script_sha256': sha(HERE / 'measure_blind_person.py'),
        'proof_script_sha256': sha(HERE / 'prove_blind_person.py'),
        'synthetic_only': True, 'original_native_observed': False,
        'physical_contact_claimed': False, 'legal_verdict_claimed': False,
        'delivery_ready': False,
    }
    target = HERE / 'blind-person-source-proof.json'
    target.write_text(json.dumps(receipt, sort_keys=True, indent=2) + '\n')
    print(json.dumps({'scenarios': len(results), 'negative_checks': len(negatives),
                      'proof_sha256': sha(target)}, sort_keys=True))


if __name__ == '__main__':
    prove()
