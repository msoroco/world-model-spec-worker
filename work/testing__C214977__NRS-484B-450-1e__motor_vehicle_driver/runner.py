"""Exact C214977 crosswalk Native source acquisition entrypoint."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def load_config():
    c = json.loads((ROOT/'config.json').read_text())
    assert (c['law_id'], c['cell_id'], c['actor']) == ('NRS-484B-450-1e','C214977','motor_vehicle_driver')
    assert c['selected_case_id'] == c['case']['case_id']
    assert c['rate_hz'] == 20 and c['duration_s'] == 45
    assert [v['name'] for v in c['cameras']] == ['overview','approach','reference_corner','driver_reference']
    assert c['case']['action'] in ('stop','stand','park')
    assert c['case']['destination'] in ('on','off')
    return c

def _ref(path):
    if not path:
        raise ValueError('reviewed source reference path required')
    return json.loads(Path(path).read_text())


def run_native(config, args):
    from crosswalk import sealed_json
    from native_capture import capture
    from carla_adapter import CarlaCrosswalkAdapter, spawn_reviewed_cameras
    from worker_exchange.world_restore import snapshot, restore

    source_root_value = args.source_root or os.environ.get('C214977_SOURCE_ROOT')
    if not source_root_value or not args.output_dir:
        raise ValueError('reviewed source root and fresh attempt output required')
    source_root = Path(source_root_value).resolve()
    if not source_root.is_dir():
        raise ValueError('reviewed source root missing')
    site_ref = _ref(args.site_ref or os.environ.get('C214977_SITE_REF'))
    vehicle_ref = _ref(args.vehicle_ref or os.environ.get('C214977_VEHICLE_REF'))
    site = sealed_json(site_ref, source_root)
    sealed_json(vehicle_ref, source_root)
    exception_ref = args.exception_ref or os.environ.get('C214977_EXCEPTION_REF')
    packet = sealed_json(_ref(exception_ref), source_root) if exception_ref else None
    if config['case']['exception'] != 'none' and packet is None:
        raise ValueError('reviewed exact exception packet required')

    import carla
    client = carla.Client(args.host or 'localhost', int(args.port or 2000))
    client.set_timeout(20.0)
    saved = snapshot(client)
    adapter = None
    sensors = {}
    try:
        world = client.get_world()
        settings = world.get_settings()
        settings.synchronous_mode = True
        settings.fixed_delta_seconds = 0.05
        world.apply_settings(settings)
        readback = world.get_settings()
        if not readback.synchronous_mode or abs(readback.fixed_delta_seconds - 0.05) > 1e-9:
            raise ValueError('Native 20 Hz settings readback failed')
        sensors = spawn_reviewed_cameras(world, carla, site, config['cameras'])
        adapter = CarlaCrosswalkAdapter(world, carla, case_id=config['selected_case_id'],
                                        cameras=sensors, exception_packet=packet)
        adapter.owned.extend(sensors.values())
        return capture(adapter, site_ref, vehicle_ref, config['case'], source_root,
                       Path(args.output_dir))
    finally:
        try:
            if adapter is not None:
                adapter.cleanup()
            else:
                for sensor in sensors.values():
                    sensor.destroy()
        finally:
            restore(client, saved)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host')
    parser.add_argument('--port')
    parser.add_argument('--source-root')
    parser.add_argument('--site-ref')
    parser.add_argument('--vehicle-ref')
    parser.add_argument('--exception-ref')
    a = parser.parse_args()
    c = load_config()
    if a.check:
        print(json.dumps({'case_id':c['selected_case_id'],'identity_checked':True,
                          'capture_profile_checked':True,'simulation_started':False}))
        return
    receipt = run_native(c, a)
    print(json.dumps({'case_id': receipt['case_id'], 'native_source_recorded': True,
                      'frame_count': receipt['frame_count'], 'physical_acceptance': 'unreviewed'}))


if __name__ == '__main__': main()
