"""Source-bound delivery acceptance protocol; diagnostic fixture only."""
import argparse
from hashlib import sha256
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')


def sha(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def audit(case, negative=False):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entries = [item for item in manifest['cases'] if item['case_id'] == case]
    if len(entries) != 1:
        raise ValueError('Unknown exact delivery case')
    entry = entries[0]
    suffix = case.rsplit('__', 1)[-1]
    compat_path = HERE / entry['compatibility']['receipt']
    compat = json.loads(compat_path.read_text())
    if sha(compat_path) != entry['compatibility']['sha256'] or compat.get('case_id') != case or compat.get('candidate_id') != 'primary' or not compat.get('passed'):
        raise ValueError('Missing current primary Native source compatibility proof')
    required = {'trace.jsonl', 'ego_road_frames.jsonl', 'video_frames.jsonl',
                'road_exception_context.json'} | {name + '.mkv' for name in CAMERAS}
    if not required <= set(compat['fixture_manifest']):
        raise ValueError('Missing required original source or four-camera stream')
    if not {'four_camera_sources', 'native_validation', 'final_decode', 'selected_measurements',
            'negative_case_source'} <= set(compat['checks']):
        raise ValueError('Missing Native validation or complete source decode')
    audit_name = suffix.replace('_', '-') + '-delivery-proof.json'
    delivery_path = HERE / audit_name
    delivery = json.loads(delivery_path.read_text())
    if delivery.get('case_id') != case or not delivery.get('originals_joined') or not delivery.get('analysis_recomputed') or not delivery.get('four_camera_full_decode'):
        raise ValueError('Independent original-source delivery audit missing')
    for name, digest in delivery.get('source_sha256', {}).items():
        if compat['fixture_manifest'].get(name) != digest:
            raise ValueError('Delivery source differs from compatibility source: ' + name)
    reviews = {name: compat['fixture_manifest'][name + '.mkv'] for name in CAMERAS}
    if negative:
        reviews['approach'] = 'stale'
    for name in CAMERAS:
        if (delivery['source_video_sha256'].get(name) != reviews[name] or
                compat['fixture_manifest'][name + '.mkv'] != reviews[name]):
            raise ValueError('Missing original-pixel review: ' + name)
    physical_spec = entry.get('physical_preparation', {})
    physical_path = HERE / physical_spec['receipt']
    physical = json.loads(physical_path.read_text())
    if sha(physical_path) != physical_spec['sha256'] or physical.get('construction_sha256') != entry['construction_sha256']:
        raise ValueError('Physical outcome protocol bound to another construction')
    complete = next(item for item in physical['fixtures'] if item['kind'] == 'complete_motion')
    result = json.loads((HERE / complete['result']).read_text())
    if (result['case_id'] != case or result['physical_checks']['maneuver']['status'] != 'met' or
            result['maneuver_completed'] is not True or result['actual_native_capture'] is not False):
        raise ValueError('Physical completion fixture proof missing')
    return {'case_id': case, 'checks': list(CHECKS), 'passed': True, 'fixture_only': True,
            'actual_pixels_reviewed': False, 'actual_native_capture': False,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.negative), indent=2))
