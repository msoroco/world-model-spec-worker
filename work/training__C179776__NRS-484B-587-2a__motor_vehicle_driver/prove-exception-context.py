"""Synthetic source-shape tests for timed 587(2)(a) context checks."""

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('exception_context', ROOT / 'native' / 'measure_exception_context.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
SCRATCH = ROOT.parent.parent / '.runtime-work' / 'c179776-exception-fixtures'
SCRATCH.mkdir(parents=True, exist_ok=True)


def write(path, value):
    path.write_text(json.dumps(value, sort_keys=True) + '\n')


def fixture(folder, vehicle_class='ordinary_motor_vehicle', sign_allowed=False, emergency=False):
    write(folder / 'designation.json', {
        'controlled_access_highway': True,
        'public_authority_source': 'synthetic authority document with exact highway ID',
        'highway_boundary_source': 'synthetic map and public-highway boundary',
        'access_restriction_source': 'synthetic access restriction record',
    })
    write(folder / 'authority.json', {
        'ego_vehicle_class': vehicle_class,
        'vehicle_class_source': 'synthetic vehicle registration/class record',
        'driver_identity_source': 'synthetic actor and driver identity record',
    })
    write(folder / 'sign.json', {
        'shoulder_use_allowed': sign_allowed,
        'allowed_vehicle_classes': ['tow_car'] if sign_allowed else [],
        'placement_authority_source': 'synthetic authority placement record',
        'posted_message_source': 'synthetic sign message record',
        'physical_sign_source': 'synthetic sign pixel/map readback',
        'permitted_manner_source': 'synthetic signed shoulder manner record',
    })
    write(folder / 'status.json', {'subsection_3_claim': 'unresolved'})
    rows = []
    for i in range(600):
        outside = i >= 200
        rows.append({
            'frame': 1000 + i, 'time_s': i / 20,
            'outside_marked_lane': outside,
            'fully_paved_shoulder': outside,
            'emergency_required': bool(emergency and 200 <= i < 400),
            'footprint_source': 'synthetic frame-joined body and marked map',
            'emergency_event_source': 'synthetic event duration record',
        })
    (folder / 'frames.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    rehash(folder)


def rehash(folder):
    write(folder / 'sources.json', {
        'format': 'c179776-source-bound-exception-context-v1',
        'sha256': {name: module.digest(folder / name) for name in module.REQUIRED},
    })


def reject(folder, mutation, expected, refresh=True):
    mutation(folder)
    if refresh:
        rehash(folder)
    try:
        module.read(folder)
    except (ValueError, FileNotFoundError) as error:
        assert expected in str(error), str(error)
        return str(error)
    raise AssertionError('Invalid exception context accepted')


with tempfile.TemporaryDirectory(dir=SCRATCH) as temporary:
    base = Path(temporary)
    positives = {}
    for name, vehicle_class, sign, emergency in (
        ('ordinary_unsigned', 'ordinary_motor_vehicle', False, False),
        ('timed_emergency', 'ordinary_motor_vehicle', False, True),
        ('signed_tow', 'tow_car', True, False),
        ('unsigned_tow', 'tow_car', False, False),
    ):
        folder = base / name
        folder.mkdir()
        fixture(folder, vehicle_class, sign, emergency)
        positives[name] = module.read(folder)
    assert positives['ordinary_unsigned']['outside_frames'] == 400
    assert positives['timed_emergency']['emergency_outside_frames'] == 200
    assert positives['signed_tow']['signed_class_shoulder_frames'] == 400
    assert positives['unsigned_tow']['signed_class_shoulder_frames'] == 0
    assert all(item['legal_verdict'] is None and not item['physical_original_verified'] for item in positives.values())
    negatives = {}
    folder = base / 'stale_sign'; folder.mkdir(); fixture(folder)
    negatives['stale_sign'] = reject(folder, lambda p: (p / 'sign.json').write_text('{}\n'), 'source hash differs', False)
    folder = base / 'missing_authority'; folder.mkdir(); fixture(folder)
    negatives['missing_authority'] = reject(folder, lambda p: write(p / 'designation.json', {'controlled_access_highway': True}), 'designation authority missing')
    folder = base / 'wrong_sign_class'; folder.mkdir(); fixture(folder, 'coroner_vehicle', True)
    positives['wrong_sign_class'] = module.read(folder)
    assert positives['wrong_sign_class']['signed_class_shoulder_frames'] == 0
    folder = base / 'wrong_class'; folder.mkdir(); fixture(folder)
    negatives['wrong_class'] = reject(folder, lambda p: write(p / 'authority.json', {'ego_vehicle_class': 'unknown', 'vehicle_class_source': 'x', 'driver_identity_source': 'x'}), 'Vehicle class')
    folder = base / 'missing_manner'; folder.mkdir(); fixture(folder, 'tow_car', True)
    def missing_manner(path):
        sign = json.loads((path / 'sign.json').read_text())
        sign.pop('permitted_manner_source')
        write(path / 'sign.json', sign)
    negatives['missing_manner'] = reject(folder, missing_manner, 'shoulder sign source missing')
    folder = base / 'missing_event'; folder.mkdir(); fixture(folder)
    def missing_event(path):
        rows = [json.loads(x) for x in (path / 'frames.jsonl').read_text().splitlines()]
        rows[300].pop('emergency_event_source')
        (path / 'frames.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    negatives['missing_event'] = reject(folder, missing_event, 'temporal source missing')
    folder = base / 'bad_timing'; folder.mkdir(); fixture(folder)
    def bad_timing(path):
        rows = [json.loads(x) for x in (path / 'frames.jsonl').read_text().splitlines()]
        rows[300]['time_s'] = 99
        (path / 'frames.jsonl').write_text(''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows))
    negatives['bad_timing'] = reject(folder, bad_timing, 'temporal source missing')
    folder = base / 'subsection_claim'; folder.mkdir(); fixture(folder)
    negatives['subsection_claim'] = reject(folder, lambda p: write(p / 'status.json', {'subsection_3_claim': 'automatic_exemption'}), 'separate legal review')
    print(json.dumps({'passed': True, 'positives': len(positives), 'negatives': len(negatives),
                      'frames_each': 600, 'exception_scope': 'source-shaped observations only',
                      'legal_verdict': None}, sort_keys=True))
