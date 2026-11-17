"""Verify four terminal no-worker CPU saved paths against exact sources."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CASE = ROOT.name + '__emergency_vehicle_unsigned_no_business'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(candidate):
    if candidate not in ('primary', 'fallback1', 'fallback2', 'fallback3'):
        raise ValueError('Unknown emergency no-worker candidate')
    attempt = REPO / '.runtime-work' / f'c150142-emergency-no-business-{candidate}-native-v1'
    version = REPO / '.runtime-work' / f'c150142-emergency-no-business-{candidate}-result-v1/v0001'
    processing = json.loads((version / 'processing.json').read_text())
    result = json.loads((version / 'analysis/result.json').read_text())
    construction = ROOT / ('selected-primary' if candidate == 'primary'
                           else 'selected-fallbacks') / 'emergency_vehicle_unsigned_no_business'
    if candidate != 'primary':
        construction /= candidate
    construction /= 'construction.json'
    observation = result['measured_values']['signed_curb_observation']
    manifest = json.loads((ROOT / 'execution-manifest-diagnostic-emergency-no-business-draft.json').read_text())
    entry = manifest['cases'][0]
    declared = entry if candidate == 'primary' else next(
        row for row in entry['candidates'] if row['id'] == candidate)
    if declared['construction_sha256'] != digest(construction) or \
            json.loads(construction.read_text()) != json.loads((attempt / 'construction.json').read_text()) or \
            processing['case_id'] != CASE or processing['candidate_id'] != candidate or \
            processing['passed'] is not True or \
            processing['native_revision']['construction_sha256'] != digest(attempt / 'construction.json') or \
            processing['timestamp_joins']['frames'] != 361 or \
            processing['timestamp_joins']['passed'] is not True or \
            processing['final_video_checks']['frames'] != 361 or \
            processing['final_video_checks']['passed'] is not True or \
            processing['physical_acceptance_claimed'] or \
            processing['legal_acceptance_claimed'] or \
            processing['missing_evidence'] or \
            observation['source_kind'] != 'synthetic_native_sample' or \
            observation['frames'] != 361 or \
            observation['red_curb_stationary_duration_s'] != 12 or \
            observation['sign_present'] or \
            observation['native_blueprint'] != 'vehicle.carlamotors.firetruck' or \
            observation['recorded_activity_events'] != [] or \
            observation['necessary_business_established'] is not None or \
            'legal_verdict' in observation:
        raise ValueError('Terminal emergency no-worker saved proof differs')
    source_decodes = []
    for index in range(4):
        receipt = json.loads((version / f'source-{index}.json').read_text())
        if receipt['frames'] != 361 or receipt['passed'] is not True or \
                receipt['video_sha256'] not in {
                    digest(attempt / (view + '.mkv')) for view in VIEWS}:
            raise ValueError('Four-camera source decode differs')
        source_decodes.append(receipt['video_sha256'])
    if len(set(source_decodes)) != 4:
        raise ValueError('Four distinct camera sources missing')
    return {'candidate': candidate, 'construction_sha256': digest(construction),
            'processing_sha256': digest(version / 'processing.json'),
            'frames': 361, 'stationary_duration_s': 12,
            'four_source_decodes': True, 'full_final_decode': True,
            'empty_worker_inventory_source_derived': True,
            'actual_business_absence_established': False,
            'necessary_business_established': False,
            'original_native_observed': False, 'physical_acceptance_claimed': False}


if __name__ == '__main__':
    print(json.dumps({'case_id': CASE,
                      'candidates': [verify(candidate) for candidate in
                                     ('primary', 'fallback1', 'fallback2', 'fallback3')]},
                     indent=2))
