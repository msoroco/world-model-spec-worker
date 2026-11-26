"""Source-bound original Native acquisition for an exact lamp-direction case.

The adapter owns the CARLA endpoint and camera synchronization. It must return
actual Native readbacks; requested lamp values never substitute for them.
"""

import hashlib
import json
from pathlib import Path
import shutil

from lamp_direction import construct, measure_original, require
from source_packet import ASSIGNMENT, verify


CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_new(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(data)


def acquire(adapter, packet_path, output_dir):
    """Capture 900 original 20 Hz ticks and four exact-frame camera sources."""
    packet_path, output_dir = Path(packet_path).resolve(), Path(output_dir).resolve()
    case_name = json.loads(packet_path.read_text())['case_id'].removeprefix(ASSIGNMENT + '__')
    checked = verify(packet_path, case_name)
    scene, case = checked['packet']['scene'], checked['case']
    require(adapter.loaded_map_sha256() == scene.get('map_sha256'),
            'reviewed Native map bytes differ')
    require(not output_dir.exists(), 'retain previous Native attempt')
    output_dir.mkdir(parents=True)
    packet_copy = output_dir / 'lamp-context-packet.json'
    shutil.copyfile(packet_path, packet_copy)
    for field, entry in checked['packet']['sources'].items():
        path = packet_path.parent / entry['path']
        destination = (output_dir / entry['path']).resolve()
        require(destination.is_relative_to(output_dir) and
                destination != packet_copy, 'source file destination invalid: ' + field)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, destination)
    settings = adapter.snapshot_settings()
    owned = []
    capture = None
    rows = []
    camera_map = {name: [] for name in CAMERAS}
    try:
        adapter.configure_sync(rate_hz=20)
        require(adapter.readback_sync(rate_hz=20) is True,
                'Native 20 Hz world settings readback missing')
        built = construct(adapter, scene, case)
        owned.extend(built['owned'])
        vehicle = owned[-1]
        camera_actors = adapter.spawn_cameras(vehicle, CAMERAS, scene)
        require(isinstance(camera_actors, dict) and set(camera_actors) == set(CAMERAS) and
                all(camera_actors.values()), 'four original camera actors missing')
        owned.extend(camera_actors[name] for name in CAMERAS)
        capture = adapter.start_pipeline_capture(vehicle, output_dir, ASSIGNMENT + '__' + case_name)
        require(capture is not None and callable(getattr(capture, 'capture', None)) and
                callable(getattr(capture, 'close', None)), 'PipelineCapture missing')
        for index in range(900):
            tick, images = adapter.tick_capture(index, scene, camera_actors)
            require(isinstance(tick, dict) and isinstance(images, dict) and
                    set(images) == set(CAMERAS), 'original tick or camera set missing')
            require(tick.get('original_frame') is not None and
                    isinstance(tick.get('time_s'), (int, float)), 'original frame identity missing')
            capture.capture(tick['original_frame'], tick['time_s'])
            for name in CAMERAS:
                image = images[name]
                require(isinstance(image, dict) and
                        image.get('original_frame') == tick['original_frame'] and
                        isinstance(image.get('bytes'), bytes) and image['bytes'] and
                        image.get('sensor_id') == adapter.actor_id(camera_actors[name]),
                        'original camera frame/source missing: ' + name)
                relative = f'cameras/{name}/{index:04d}.png'
                write_new(output_dir / relative, image['bytes'])
                camera_map[name].append({'original_frame': tick['original_frame'],
                                         'sensor_id': image['sensor_id'],
                                         'path': relative, 'sha256': digest(image['bytes'])})
            rows.append(tick)
        report = measure_original(rows, scene, case)
        report.update({'source_packet_sha256': checked['packet_sha256'],
                       'source_sha256': checked['source_sha256'],
                       'map_sha256': scene['map_sha256'],
                       'vehicle_class_source_sha256': scene['vehicle_class_source_sha256'],
                       'route_source_sha256': scene['route_source_sha256'],
                       'required_lamp_provisions_source_sha256': scene['required_lamp_provisions_source_sha256']})
        write_new(output_dir / 'original-lamp-ticks.jsonl',
                  ''.join(json.dumps(row, sort_keys=True) + '\n' for row in rows).encode())
        write_new(output_dir / 'camera-source-manifest.json',
                  (json.dumps({'case_id': ASSIGNMENT + '__' + case_name,
                               'cameras': camera_map}, sort_keys=True) + '\n').encode())
        write_new(output_dir / 'lamp-measurement.json',
                  (json.dumps(report, sort_keys=True) + '\n').encode())
    finally:
        cleanup_errors = []
        if capture is not None:
            try:
                capture.close()
            except Exception as error:
                cleanup_errors.append('pipeline close: ' + str(error))
        for actor in reversed(owned):
            try:
                adapter.destroy(actor)
            except Exception as error:
                cleanup_errors.append('actor destroy: ' + str(error))
        try:
            adapter.restore_settings(settings)
            require(adapter.readback_restored(settings) is True,
                    'Native world settings restore readback missing')
        except Exception as error:
            cleanup_errors.append('world restore: ' + str(error))
        require(not cleanup_errors, 'Native cleanup failed: ' + '; '.join(cleanup_errors))
    release = {'case_id': ASSIGNMENT + '__' + case_name,
               'owned_actor_ids': [adapter.actor_id(actor) for actor in owned],
               'world_restored': True, 'last_original_frame': rows[-1]['original_frame']}
    write_new(output_dir / 'native-owner-release.json',
              (json.dumps(release, sort_keys=True) + '\n').encode())
    return report
