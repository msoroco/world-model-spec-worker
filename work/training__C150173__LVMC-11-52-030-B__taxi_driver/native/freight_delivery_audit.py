"""Independent original-pixel and body audit for taxi light-express cases."""
import argparse
import hashlib
import json
from pathlib import Path

from audit_freight_original import audit as audit_original
from freight_finalize import source_measurement


VIEWS = {'overview', 'approach', 'reference_corner', 'driver_reference'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text())


def pixels(attempt, name, videos):
    review = read(attempt / name)
    observations = review.get('source_pixels')
    if not isinstance(observations, list) or not observations:
        raise ValueError('Original freight actual-pixel review missing: ' + name)
    for item in observations:
        view, frame = item.get('camera'), item.get('video_frame')
        if (view not in VIEWS or type(frame) is not int or not 0 <= frame < 600 or
                item.get('video_sha256') != videos[view]['sha256'] or
                item.get('observed_visible') is not True or not item.get('observation')):
            raise ValueError('Original freight actual-pixel review is not video-bound: ' + name)
    return {'review': name, 'sha256': sha(attempt / name),
            'frames': [item['video_frame'] for item in observations]}


def audit(attempt, case_id, diagnostic_test=False):
    attempt = Path(attempt).resolve()
    config = read(attempt / 'config.json')
    if config.get('case_id') != case_id or config.get('selected_case_id') != case_id:
        raise ValueError('Freight delivery audit selects another exact case')
    original = audit_original(attempt)
    measured = source_measurement(attempt)
    result = read(attempt / 'result.json')
    analysis = read(attempt / 'analysis-report.json')
    reported = analysis.get('measurements', {}).get('freight_yellow_zone_measurement', {}).get('value')
    if (result.get('case_id') != case_id or result.get('measured_values') != measured or
            reported != measured or measured.get('source_manifest_sha256') !=
            original['source_manifest_sha256'] or
            abs(measured['cargo_displacement_m'] - original['cargo_displacement_m']) > .001):
        raise ValueError('Freight delivery analysis differs from independent original body audit')
    commercial = read(attempt / 'commercial-status-review.json')
    if commercial.get('observed_commercial_use') is not True:
        raise ValueError('Original actor-bound commercial classification unconfirmed')
    pixel_reviews = [pixels(attempt, name, original['videos']) for name in
                     ('sign-review.json', 'freight-purpose-review.json')]
    native = [json.loads(line) for line in (attempt / 'freight-native.jsonl').read_text().splitlines()]
    def center_x(row):
        return sum(vertex[0] for vertex in row['cargo_body_vertices_xyz_m']) / 8
    dx = center_x(native[-1]) - center_x(native[0])
    purpose = measured['observed_purpose']
    motion = measured['cargo_transfer_motion_frames']
    if ((purpose == 'loading_light_express' and not (dx < -1 and motion > 0)) or
            (purpose == 'unloading_light_express' and not (dx > 1 and motion > 0)) or
            (purpose == 'waiting_without_transfer' and not (abs(dx) < .01 and motion == 0))):
        raise ValueError('Original freight cargo motion differs from reviewed purpose')
    return {'format': 'c150173-independent-freight-delivery-audit-v1',
            'case_id': case_id, 'source_manifest_sha256': original['source_manifest_sha256'],
            'capture_seal_sha256': original['capture_seal_sha256'],
            'analysis_report_sha256': sha(attempt / 'analysis-report.json'),
            'result_sha256': sha(attempt / 'result.json'),
            'pixel_reviews': pixel_reviews,
            'checks': {'native_source': True, 'all_participants': True,
                       'time_join': True, 'full_video_decode': True,
                       'actual_pixels': True, 'physical_completion': True},
            'eligible_for_local_acceptance': not diagnostic_test,
            'diagnostic_test': diagnostic_test,
            'legal_verdict': None}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output')
    args = parser.parse_args()
    report = audit(args.attempt, args.case)
    if args.output:
        destination = Path(args.output)
        if destination.exists():
            raise ValueError('Fresh freight delivery audit output required')
        destination.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({'case_id': args.case,
                      'eligible_for_local_acceptance': report['eligible_for_local_acceptance']}))
