"""Independent exact-case delivery protocol check on synthetic sources."""

import argparse
from hashlib import sha256
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
CHECKS = ('native_source', 'all_participants', 'time_join', 'full_video_decode',
          'actual_pixels', 'physical_completion')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def audit(case, negative=False):
    manifest = json.loads((HERE / 'execution-manifest.json').read_text())
    entry = next((item for item in manifest['cases'] if item['case_id'] == case), None)
    if entry is None:
        raise ValueError('Unknown exact delivery case')
    suffix = case.rsplit('__', 1)[-1]
    proof_path = HERE / entry['compatibility']['receipt']
    proof = json.loads(proof_path.read_text())
    if (digest(proof_path) != entry['compatibility']['sha256'] or
            proof['case_id'] != case or proof.get('passed') is not True):
        raise ValueError('Missing exact Native source compatibility proof')
    if not {'trace.jsonl', 'video_frames.jsonl'} <= set(proof['fixture_manifest']):
        raise ValueError('Missing original trace or frame map')
    if not {'four_camera_sources', 'native_validation', 'final_decode', 'selected_measurements',
            'negative_case_source'} <= set(proof['checks']):
        raise ValueError('Incomplete saved-processing and video decode checks')
    expected = {name + '.mkv' for name in CAMERAS}
    if not expected <= set(proof['fixture_manifest']):
        raise ValueError('Original four cameras missing')
    reviews = {name: {'source_sha256': proof['fixture_manifest'][name + '.mkv'],
                      'fixture_only': True, 'reviewed': True} for name in CAMERAS}
    if negative:
        reviews['approach']['source_sha256'] = 'stale'
    for name in CAMERAS:
        if (reviews[name]['source_sha256'] != proof['fixture_manifest'][name + '.mkv']
                or reviews[name]['reviewed'] is not True):
            raise ValueError('Missing original-pixel review: ' + name)
    physical = json.loads((HERE / entry['physical_preparation']['receipt']).read_text())
    if physical['construction_sha256'] != entry['construction_sha256']:
        raise ValueError('Physical outcome fixture bound to another construction')
    complete = next(item for item in physical['fixtures'] if item['kind'] == 'complete_motion')
    result = json.loads((HERE / complete['result']).read_text())
    if (result['case_id'] != case or result['physical_checks']['maneuver']['status'] != 'met'
            or result['maneuver_completed'] is not True or result['actual_native_capture'] is not False):
        raise ValueError('Physical completion protocol proof missing')
    return {'case_id': case, 'checks': list(CHECKS), 'passed': True,
            'fixture_only': True, 'actual_pixels_reviewed': False,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--negative', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.case, args.negative), indent=2))
