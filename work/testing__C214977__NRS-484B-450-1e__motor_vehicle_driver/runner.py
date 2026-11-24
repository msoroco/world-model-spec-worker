"""Exact C214977 crosswalk Native source acquisition entrypoint."""
from __future__ import annotations

import argparse
import json
import os
import shutil
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


def _stage_sources(source_root, attempt, refs):
    """Copy only reviewed original source bytes before Native capture begins."""
    from crosswalk import sealed_json, require
    attempt = Path(attempt).resolve()
    for ref in refs:
        require(ref['path'].startswith('source-inputs/'), 'reviewed sources need source-inputs/ paths')
        sealed_json(ref, source_root)
        source = (source_root/ref['path']).resolve()
        target = (attempt/ref['path']).resolve()
        require(target.is_relative_to(attempt) and not target.exists(), 'source staging collision')
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source,target)
        sealed_json(ref, attempt)


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
    exception_source = _ref(exception_ref) if exception_ref else None
    packet = sealed_json(exception_source, source_root) if exception_source else None
    if config['case']['exception'] != 'none' and packet is None:
        raise ValueError('reviewed exact exception packet required')
    if packet is not None:
        if not packet.get('instruction_source') or not packet.get('review_source'):
            raise ValueError('original instruction and independent review sources required')
        sealed_json(packet['instruction_source'], source_root)
        sealed_json(packet['review_source'], source_root)
        if (packet.get('source_sha256') != packet['instruction_source']['sha256'] or
                packet.get('reviewed_instruction_sha256') != packet['review_source']['sha256']):
            raise ValueError('exception source or review hash differs')
    refs = [site_ref, vehicle_ref]
    if exception_source:
        refs += [exception_source, packet['instruction_source'], packet['review_source']]
    attempt = Path(args.output_dir)
    _stage_sources(source_root, attempt, refs)
    source_root = attempt.resolve()

    import carla
    client = carla.Client(args.host or 'localhost', int(args.port or 2000))
    client.set_timeout(20.0)
    saved = snapshot(client)
    adapter = None
    sensors = {}
    receipt = None
    restoration = None
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
        receipt = capture(adapter, site_ref, vehicle_ref, config['case'], source_root,
                          attempt, exception_ref=exception_source)
    finally:
        try:
            if adapter is not None:
                adapter.cleanup()
            else:
                for sensor in sensors.values():
                    sensor.destroy()
        finally:
            restoration = restore(client, saved)
    if receipt is None or restoration is None:
        raise ValueError('Native capture or world restoration incomplete')
    from native_output_bridge import seal_original_capture
    seal_original_capture(attempt, config['case'], saved['opendrive'],
                          restoration_verified=restoration['restored'])
    return receipt


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
