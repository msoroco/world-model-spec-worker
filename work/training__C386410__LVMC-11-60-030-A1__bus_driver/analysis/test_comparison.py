"""Positive and adversarial tests for fixed conditions in location comparison."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

sys.dont_write_bytecode = True
assignment = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(assignment))
from comparison_audit import audit


def save(root, kind):
    zone = {'kind': kind, 'id': kind + '-R1', 'route_id': 'R1'}
    if kind != 'other_street':
        data = b'<OpenDRIVE><signal name="BUS ROUTE TERMINUS"/></OpenDRIVE>\n'
        (root / 'road.xodr').write_bytes(data)
        zone['designation_source'] = {'path': 'road.xodr', 'sha256': hashlib.sha256(data).hexdigest()}
    context = {'vehicle_class': 'route_bus_non_tour', 'route_id': 'R1',
               'street_id': 'native-road-1', 'controller_policy': 'approach_then_stationary_brake_v1',
               'weather_policy': 'ClearNoon', 'capture_profile': {'rate_hz': 20, 'frames': 600,
               'cameras': {name: [100, 100] for name in ('overview', 'approach', 'reference_corner', 'driver_reference')}},
               'zone': zone}
    (root / 'bus-context.json').write_text(json.dumps(context))
    history = []
    frame_map = []
    for i in range(600):
        history.append({'video_frame': i, 'native_frame': i + 10, 'time_s': i / 20,
                        'bus_speed_mps': 0, 'parking_brake_applied': True,
                        'driver_present': True, 'occupied_zone_id': zone['id']})
        frame_map.append({'video_frame': i, 'native_frame': i + 10,
                          'camera_native_frames': {name: i + 10 for name in ('overview', 'approach', 'reference_corner', 'driver_reference')}})
    (root / 'bus-history.jsonl').write_text('\n'.join(map(json.dumps, history)) + '\n')
    (root / 'video_frames.jsonl').write_text('\n'.join(map(json.dumps, frame_map)) + '\n')
    for name in ('overview', 'approach', 'reference_corner', 'driver_reference'):
        (root / (name + '.mkv')).write_bytes(b'synthetic-' + name.encode())


with tempfile.TemporaryDirectory() as temporary:
    left, right = Path(temporary) / 'reference_corner', Path(temporary) / 'driver_reference'
    left.mkdir()
    right.mkdir()
    save(left, 'route_destination')
    save(right, 'other_street')
    result = audit(left, right, 'location_terminus', source_kind='synthetic_native_sample')
    assert result['passed'] and result['legal_judgment'] == 'unresolved'
    print('positive isolated location comparison')
    context_path = right / 'bus-context.json'
    original = context_path.read_text()
    changed = json.loads(original)
    changed['weather_policy'] = 'WetNoon'
    context_path.write_text(json.dumps(changed))
    try:
        audit(left, right, 'location_terminus', source_kind='synthetic_native_sample')
    except ValueError as error:
        assert 'fixed comparison condition differs: weather_policy' in str(error)
        print('negative fixed weather', error)
    else:
        raise AssertionError('weather difference accepted')
    context_path.write_text(original)
    (right / 'driver_reference.mkv').unlink()
    try:
        audit(left, right, 'location_terminus', source_kind='synthetic_native_sample')
    except ValueError as error:
        assert 'missing required source: driver_reference.mkv' in str(error)
        print('negative missing source', error)
    else:
        raise AssertionError('missing camera accepted')
