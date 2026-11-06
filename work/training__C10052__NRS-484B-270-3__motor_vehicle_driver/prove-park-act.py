"""Build and test an unselected synthetic parking-control comparison."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
NATIVE = HERE / 'native'
sys.path.insert(0, str(NATIVE))
from measure_park_act import measure


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, obj):
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + '\n')


def reject(folder, fragment):
    try:
        measure(folder)
    except ValueError as exc:
        assert fragment in str(exc), str(exc)
    else:
        raise AssertionError('Invalid parking source accepted: ' + fragment)


def main():
    base = ROOT / '.runtime-work' / 'c10052-park-act'
    source = HERE / 'draft-facility' / 'probe_b'
    poses = [json.loads(x) for x in (source / 'native_samples.jsonl').read_text().splitlines()]
    assert len(poses) == 480
    outputs = {}
    for variant in ('stationary_stop', 'short_handbrake', 'parking_control'):
        folder = base / variant
        folder.mkdir(parents=True, exist_ok=True)
        for name in ('native_samples.jsonl', 'road_geometry.json'):
            shutil.copyfile(source / name, folder / name)
        controls = []
        for i, pose in enumerate(poses):
            controls.append({
                'native_frame': pose['native_frame'], 'time_s': pose['time_s'],
                'throttle': 0.0, 'brake': 0.5 if 132 <= i < 479 else 0.0,
                'hand_brake': (variant == 'parking_control' and 160 <= i < 440) or
                              (variant == 'short_handbrake' and 160 <= i < 190),
                'control_source': 'synthetic_fixture',
                'synthetic_diagnostic': True,
            })
        (folder / 'native_controls.jsonl').write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in controls))
        names = ('native_samples.jsonl', 'native_controls.jsonl', 'road_geometry.json')
        dump(folder / 'park-act-sources.json', {
            'format': 'c10052-park-act-sources-v1', 'source_kind': 'synthetic_cpu_fixture',
            'sha256': {name: sha(folder / name) for name in names},
        })
        outputs[variant] = measure(folder)
    assert outputs['stationary_stop']['park_control_candidate'] is False
    assert outputs['short_handbrake']['park_control_candidate'] is False
    assert outputs['parking_control']['park_control_candidate'] is True
    assert outputs['parking_control']['held_duration_s'] >= 2
    assert outputs['parking_control']['max_held_facility_overlap_m2'] > 0
    assert outputs['stationary_stop']['source_sha256']['native_samples.jsonl'] == outputs['parking_control']['source_sha256']['native_samples.jsonl']
    assert outputs['short_handbrake']['source_sha256']['native_samples.jsonl'] == outputs['parking_control']['source_sha256']['native_samples.jsonl']
    assert outputs['stationary_stop']['source_sha256']['road_geometry.json'] == outputs['parking_control']['source_sha256']['road_geometry.json']
    bad = base / 'bad'
    if bad.exists():
        shutil.rmtree(bad)
    shutil.copytree(base / 'parking_control', bad)
    manifest = json.loads((bad / 'park-act-sources.json').read_text())
    manifest['source_kind'] = 'original_native'
    dump(bad / 'park-act-sources.json', manifest)
    reject(bad, 'control source differs')
    manifest['source_kind'] = 'synthetic_cpu_fixture'
    dump(bad / 'park-act-sources.json', manifest)
    rows = [json.loads(x) for x in (bad / 'native_controls.jsonl').read_text().splitlines()]
    rows[170]['native_frame'] += 1
    (bad / 'native_controls.jsonl').write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in rows))
    reject(bad, 'source hash differs')
    manifest['sha256']['native_controls.jsonl'] = sha(bad / 'native_controls.jsonl')
    dump(bad / 'park-act-sources.json', manifest)
    reject(bad, 'control/pose join differs')
    result = {'format': 'c10052-park-act-synthetic-proof-v1', 'variants': outputs,
              'negatives': ['synthetic_as_original', 'changed_control_hash', 'control_pose_join'],
              'fixture_root': str(base.relative_to(ROOT)), 'selected': False}
    dump(HERE / 'park-act-summary.json', result)
    print(json.dumps({'stop_candidate': False, 'parking_candidate': True,
                      'held_duration_s': outputs['parking_control']['held_duration_s'],
                      'max_overlap_m2': outputs['parking_control']['max_held_facility_overlap_m2'],
                      'negatives': result['negatives']}, sort_keys=True))


if __name__ == '__main__':
    main()
