"""Independent electric walking/riding source comparison, before physical review."""
import argparse
import importlib.util
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / 'native'))
from electric_finalize import validate_electric_recording


def ordinary_pre_audit():
    spec = importlib.util.spec_from_file_location('ordinary_comparison_audit',
                                                  HERE / 'comparison-audit.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.audit


def audit(walk_attempt, ride_attempt, machine_class):
    if machine_class not in {'electric_bicycle', 'electric_scooter'}:
        raise ValueError('Exact electric comparison class required')
    walk_attempt, ride_attempt = Path(walk_attempt).resolve(), Path(ride_attempt).resolve()
    walk_binding = validate_electric_recording(walk_attempt)
    ride_binding = validate_electric_recording(ride_attempt)
    if walk_binding['machine_class'] != machine_class or ride_binding['machine_class'] != machine_class:
        raise ValueError('Electric comparison class source differs')
    if (walk_binding['blueprint_id'] != ride_binding['blueprint_id'] or
            walk_binding['review_sha256'] != ride_binding['review_sha256'] or
            walk_binding['review_source_sha256'] != ride_binding['review_source_sha256']):
        raise ValueError('Electric comparison fixed reviewed asset differs')
    walk_context = json.loads((walk_attempt / 'restriction-context.json').read_text())
    ride_context = json.loads((ride_attempt / 'restriction-context.json').read_text())
    for key in ('native_sign_survey', 'native_sidewalk_survey', 'sign_orientation',
                'sidewalk_xy_m', 'street_name', 'west_boundary', 'east_boundary'):
        if walk_context.get(key) != ride_context.get(key):
            raise ValueError('Electric comparison fixed Native context differs: ' + key)
    walk_config = json.loads((walk_attempt / 'config.json').read_text())
    ride_config = json.loads((ride_attempt / 'config.json').read_text())
    for key in ('law_id', 'cell_id', 'actor', 'rate_hz', 'duration_s',
                'cameras', 'requested_speed_mps'):
        if walk_config.get(key) != ride_config.get(key):
            raise ValueError('Electric comparison fixed capture policy differs: ' + key)
    def sources(root):
        return (root / 'bicycle-poses.jsonl', root / 'restriction-context.json',
                root / 'video_frames.jsonl')
    ordinary = ordinary_pre_audit()(sources(walk_attempt), sources(ride_attempt))
    return {**ordinary, 'format': 'worker-electric-comparison-source-preaudit-v1',
            'machine_class': machine_class,
            'comparison_id': machine_class + '_walk_versus_ride',
            'fixed_reviewed_asset_blueprint_id': walk_binding['blueprint_id'],
            'fixed_review_sha256': walk_binding['review_sha256'],
            'fixed_review_source_sha256': walk_binding['review_source_sha256'],
            'fixed_native_context_checked': True,
            'fixed_capture_policy_checked': True,
            'physical_acceptance_claimed': False,
            'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--walk-attempt', required=True)
    parser.add_argument('--ride-attempt', required=True)
    parser.add_argument('--machine-class', required=True)
    args = parser.parse_args()
    print(json.dumps(audit(args.walk_attempt, args.ride_attempt,
                           args.machine_class), sort_keys=True))
