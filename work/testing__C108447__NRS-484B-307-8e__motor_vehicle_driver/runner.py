"""Exact C108447 Native capture entrypoint for an owner-supplied original site.

An exclusive Native owner supplies world, ego, reviewed map packet, signal and
camera observers. This portable entrypoint can check the binding on a CPU host;
the source and CARLA owner are supplied only at the eventual physical run.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
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


def run_capture(output_dir: Path, host: str, port: int) -> dict:
    """Dispatch the local Native owner, then seal canonical original sources."""
    from canonical_bridge import bridge
    from native_dispatch import dispatch

    selected = check()['case_id']
    root = Path(output_dir).resolve()
    if not root.is_dir() or not (root / 'construction.json').is_file():
        raise ValueError('materialized canonical capture directory required')
    environment = ('C108447_ORIGINAL_OPENDRIVE', 'C108447_PARCEL_AUTHORITY',
                   'C108447_SITE_REVIEW', 'C108447_NATIVE_OWNER_MODULE')
    if any(not os.environ.get(name) for name in environment):
        raise ValueError('original site files and local Native owner module required: ' +
                         ', '.join(environment))
    road, authority, review_path, owner_module = [Path(os.environ[name]).resolve()
                                                   for name in environment]
    if not owner_module.is_file():
        raise ValueError('local Native owner module file required')
    review = json.loads(review_path.read_text())
    context = review.get('case_contexts', {}).get(selected, {})
    purpose, actor_source = context.get('purpose'), context.get('actor_source')
    if (not isinstance(purpose, dict) or not purpose.get('source') or
            not isinstance(actor_source, dict) or not actor_source.get('source')):
        raise ValueError('separate reviewed case purpose and actor sources required')
    spec = importlib.util.spec_from_file_location('c108447_local_native_owner', owner_module)
    if spec is None or spec.loader is None:
        raise ValueError('loadable local Native owner module required')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not callable(getattr(module, 'owner_factory', None)) or not callable(getattr(module, 'export_graph', None)):
        raise ValueError('Native owner_factory and original export_graph callables required')
    original = root / 'original-attempt'
    dispatched = dispatch(
        owner_factory=lambda packet, case: module.owner_factory(host, port, packet, case),
        opendrive=road, authority=authority, review_receipt=review_path,
        property_id=review['property_id'], case_id=selected,
        purpose=purpose, actor_source=actor_source, attempt=original,
        native_export_fn=lambda owner, attempt, capture:
            module.export_graph(owner, root, attempt, capture))
    bridged = bridge(root, original, release=dispatched['release'])
    return {'case_id': selected, 'native_capture_recorded': True,
            'frame_count': bridged['frame_count'],
            'physical_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--host')
    parser.add_argument('--port', type=int)
    args = parser.parse_args()
    if args.check and not any((args.output_dir, args.host, args.port)):
        print(json.dumps(check(), sort_keys=True))
    elif not args.check and args.output_dir and args.host and args.port:
        try:
            print(json.dumps(run_capture(args.output_dir, args.host, args.port),
                             sort_keys=True))
        except Exception as error:
            status = Path(args.output_dir) / 'native-run-status.json'
            if not status.exists():
                status.write_text(json.dumps({'errors': [
                    {'type': type(error).__name__, 'message': str(error)}],
                    'physical_acceptance_claimed': False},
                    indent=2, sort_keys=True) + '\n')
            raise
    else:
        parser.error('choose --check or --output-dir DIR --host HOST --port PORT')
