"""Prove source hashes and original-vs-fixture review separation."""

import json
from pathlib import Path

from source_review import ROLES, load, sha


def reject(fn, phrase):
    try:
        fn()
    except ValueError as exc:
        assert phrase in str(exc), str(exc)
    else:
        raise AssertionError("expected rejection: " + phrase)


root = Path('.runtime-work/c202465-lvmc-source-proof').resolve()
root.mkdir(parents=True, exist_ok=True)
road_sha = "1"*64
records = {
    "railway": {"crossing_kind": "at_grade", "railway_type": "electric",
                "railway_identity": "fixture electric railway", "crossing_xyz_m": [0, 0, 0],
                "rail_unit_direction_xy": [0, 1], "surveyed_left_extent_m": 122,
                "surveyed_right_extent_m": 122,
                "rail_vehicle_actor_ids": {"left": 2, "right": 3}},
    "approach": {"driver_role": "motor_vehicle_driver", "municipal_jurisdiction_verified": True,
                 "approach_maneuver": "cross_railway", "approach_direction_xy": [1, 0],
                 "surveyed_approach_length_m": 50,
                 "ego_spawn_xyz_m": [-50, 0, 2], "ego_spawn_yaw_deg": 0},
    "flagman": {"source_method": "original_actor_and_duty_readback",
                "on_duty_at_capture_start": False},
    "signal": {"source_method": "original_device_visibility_and_state_readback",
               "installed": False, "clearly_visible": False,
               "indicates_immediate_approach": False},
}
for role in ROLES:
    source = root / (role + '.source.txt')
    source.write_text('schema-only diagnostic source ' + role + '\n')
    data = dict(records[role], role=role, road_sha256=road_sha,
                source_sha256=sha(source), review_status='schema_only',
                provenance_kind='synthetic_fixture', reviewer_id='cpu-schema-test')
    (root / (role + '.json')).write_text(json.dumps(data, indent=2) + '\n')
assert len(load(root, road_sha, diagnostic_fixture=True)) == 4
reject(lambda: load(root, road_sha), 'review differs')
wrong = json.loads((root / 'railway.json').read_text())
wrong['surveyed_left_extent_m'] = 120
(root / 'railway.json').write_text(json.dumps(wrong, indent=2) + '\n')
reject(lambda: load(root, road_sha, diagnostic_fixture=True), 'both 400-foot')
wrong['surveyed_left_extent_m'] = 122
(root / 'railway.json').write_text(json.dumps(wrong, indent=2) + '\n')
(root / 'signal.source.txt').write_text('stale signal source\n')
reject(lambda: load(root, road_sha, diagnostic_fixture=True), 'review differs')
print('PASS: source-hashed railway, jurisdiction and exception review contract')
