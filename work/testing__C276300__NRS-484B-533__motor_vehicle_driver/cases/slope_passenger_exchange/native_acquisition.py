"""Own and release original 20 Hz grade-standing capture resources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from grade_stand import construct, measure_original
from source_packet import verify


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
REQUIRED_ADAPTER_METHODS = (
    'loaded_map_sha256', 'snapshot_settings', 'configure_sync',
    'readback_sync', 'restore_settings', 'readback_restored',
    'spawn_vehicle', 'spawn_person', 'set_standing_route',
    'set_other_route', 'set_person_action', 'set_engine',
    'set_parking_brake', 'set_front_wheels', 'spawn_cameras',
    'tick_capture', 'destroy', 'actor_id',
    'read_engine_ignition_and_rpm', 'read_parking_brake_and_torque',
    'read_front_wheel_vectors', 'read_responsible_person_action',
)


def check_native_adapter(adapter):
    """Reject operators without original mechanical/person readback seams."""
    missing = [name for name in REQUIRED_ADAPTER_METHODS
               if not callable(getattr(adapter, name, None))]
    if missing:
        raise ValueError('Native source readback unavailable: ' + ', '.join(missing))


def _write(path: Path, data: bytes):
    with path.open('xb') as stream:
        stream.write(data)


def acquire(adapter, packet_path: Path, output: Path) -> dict:
    packet_path, output = Path(packet_path), Path(output)
    checked = verify(packet_path)
    scene, case = checked['scene'], checked['case']
    check_native_adapter(adapter)
    if adapter.loaded_map_sha256() != scene['map_opendrive_sha256']:
        raise ValueError('loaded original OpenDRIVE differs from reviewed site')
    if output.exists():
        raise ValueError('Native attempt output already exists')
    output.mkdir(parents=True)
    shutil.copy2(packet_path, output / 'source-packet.json')
    for ref in json.loads(packet_path.read_text())['source_refs'].values():
        shutil.copy2(packet_path.parent / ref['path'], output / ref['path'])
    initial = adapter.snapshot_settings()
    owned = []
    rows = []
    cameras = {name: [] for name in CAMERAS}
    restored = False
    try:
        adapter.configure_sync(rate_hz=20)
        if adapter.readback_sync(rate_hz=20) is not True:
            raise ValueError('Native 20 Hz readback failed')
        created = construct(adapter, scene, case)
        owned.extend(created['owned'])
        sensors = adapter.spawn_cameras(owned[0], CAMERAS, scene)
        if (not isinstance(sensors, dict) or set(sensors) != set(CAMERAS) or
                any(item is None for item in sensors.values())):
            raise ValueError('four original camera actors required')
        owned.extend(sensors[name] for name in CAMERAS)
        for index in range(900):
            tick, images = adapter.tick_capture(index, scene, sensors)
            if (not isinstance(tick, dict) or not isinstance(images, dict) or
                    set(images) != set(CAMERAS)):
                raise ValueError('original tick or image missing')
            frame = tick.get('original_frame')
            original_reads = (
                (adapter.read_engine_ignition_and_rpm(frame),
                 ('engine_ignition_on', 'engine_rpm')),
                (adapter.read_parking_brake_and_torque(frame),
                 ('brake_engaged', 'brake_torque_nm')),
                (adapter.read_front_wheel_vectors(frame),
                 ('front_wheel_vector_xy',)),
                (adapter.read_responsible_person_action(frame),
                 ('person_id', 'person_distance_m', 'person_action')),
            )
            for observed, fields in original_reads:
                if not isinstance(observed, dict) or any(
                        name not in observed or tick.get(name) != observed[name]
                        for name in fields):
                    raise ValueError('original mechanical/person readback differs: ' +
                                     ', '.join(fields))
            rows.append(tick)
            for name in CAMERAS:
                data = images[name]
                if not isinstance(data, bytes) or not data:
                    raise ValueError('original camera PNG bytes missing: ' + name)
                filename = f'{name}-{tick["original_frame"]}.png'
                _write(output / filename, data)
                cameras[name].append({
                    'original_frame': tick['original_frame'],
                    'time_s': tick['time_s'], 'path': filename,
                    'sha256': hashlib.sha256(data).hexdigest(),
                })
        measurement = measure_original(rows, scene, case)
        _write(output / 'original-ticks.jsonl',
               ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows).encode())
        _write(output / 'camera-source-manifest.json',
               (json.dumps({'cameras': cameras}, sort_keys=True, indent=2) + '\n').encode())
        _write(output / 'grade-standing-measurement.json',
               (json.dumps(measurement, sort_keys=True, indent=2) + '\n').encode())
    finally:
        destroyed = []
        failures = []
        for actor in reversed(owned):
            try:
                adapter.destroy(actor)
                destroyed.append(adapter.actor_id(actor))
            except Exception as error:
                failures.append(str(error))
        try:
            adapter.restore_settings(initial)
            restored = adapter.readback_restored(initial) is True
        except Exception as error:
            failures.append(str(error))
        if failures or not restored:
            raise ValueError('Native owner cleanup failed: ' + '; '.join(failures))
    release = {'case_id': checked['case_id'], 'world_restored': restored,
               'owned_actor_ids': [adapter.actor_id(actor) for actor in owned],
               'destroyed_actor_ids': destroyed,
               'last_original_frame': rows[-1]['original_frame']}
    _write(output / 'native-owner-release.json',
           (json.dumps(release, sort_keys=True, indent=2) + '\n').encode())
    return {'case_id': checked['case_id'], 'source_frame_count': len(rows),
            'owner_release': release}
