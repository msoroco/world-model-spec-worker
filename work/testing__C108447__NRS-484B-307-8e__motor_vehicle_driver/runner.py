"""Exact C108447 Native capture entrypoint for an owner-supplied original site.

An exclusive Native owner supplies world, ego, reviewed map packet, signal and
camera observers. This portable entrypoint can check the binding on a CPU host;
the source and CARLA owner are supplied only at the eventual physical run.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from case_observation import PREFIX, SUFFIXES
from native_capture import capture


def check() -> dict:
    config = json.loads(Path('config.json').read_text())
    case_id = config.get('selected_case_id')
    if (case_id not in [PREFIX + name for name in SUFFIXES]
            or config.get('case', {}).get('case_id') != case_id
            or config.get('law_id') != 'NRS-484B-307-8e'
            or config.get('cell_id') != 'C108447'
            or config.get('actor') != 'motor_vehicle_driver'):
        raise ValueError('exact law, cell, actor and case binding required')
    if config.get('rate_hz') != 20 or config.get('duration_s') != 45:
        raise ValueError('900-frame 20 Hz capture profile required')
    cameras = config.get('cameras', [])
    if [(item.get('name'), item.get('width'), item.get('height')) for item in cameras] != [
            ('overview', 1920, 1080), ('approach', 1280, 720),
            ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]:
        raise ValueError('four original camera profiles required')
    if config.get('capture_provenance') != 'original Native samples required':
        raise ValueError('original Native capture provenance required')
    if config.get('target_speed_mps') not in (5.0, 3.5):
        raise ValueError('selected engineering route speed required')
    return {'case_id': case_id, 'offline_binding_passed': True,
            'physical_acceptance_claimed': False}


def capture_original(*, world, ego, map_packet, property_id, purpose,
                     actor_source, signal_observer, camera_observer,
                     destination_street_id, output_dir: Path, control_applier):
    """Run the selected exact case with original owner-held Native objects."""
    selected = check()['case_id']
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    return capture(world=world, ego=ego, map_packet=map_packet,
                   property_id=property_id, case_id=selected,
                   purpose=purpose, actor_source=actor_source,
                   signal_observer=signal_observer,
                   destination_street_id=destination_street_id,
                   output=output_dir / 'trace.json', ticks=900,
                   target_speed_mps=json.loads(Path('config.json').read_text())['target_speed_mps'],
                   control_applier=control_applier,
                   camera_observer=camera_observer,
                   media_directory=output_dir)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    if not args.check:
        parser.error('original Native owner must call capture_original with source objects')
    print(json.dumps(check(), sort_keys=True))
