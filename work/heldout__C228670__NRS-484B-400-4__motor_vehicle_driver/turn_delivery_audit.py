"""Independent original-source and Native-owner delivery audit for exact turn cases."""
import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

PREFIX = 'heldout__C228670__NRS-484B-400-4__motor_vehicle_driver__'
SLUGS = ('approach_near_depart_right', 'approach_far_depart_right',
         'approach_near_depart_left')
CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def audit(folder, case, attempt, saved_analysis, *, diagnostic_fixture=False):
    folder, attempt, saved_analysis = (Path(x).resolve() for x in (folder, attempt, saved_analysis))
    if case not in {PREFIX + slug for slug in SLUGS}:
        raise ValueError('Wrong exact C228670 delivery case')
    sys.path.insert(0, str(folder))
    from turn_source_audit import audit as audit_saved_source
    proof = audit_saved_source(saved_analysis, attempt, decode=True)
    if proof['case_id'] != case or not proof['full_camera_decode']:
        raise ValueError('Exact saved turn source identity differs')
    if diagnostic_fixture:
        if not (attempt / 'fixture-provenance.json').is_file() or (attempt / 'capture-seal.json').exists():
            raise ValueError('Unsealed diagnostic fixture required')
        review = None
    else:
        seal_path, exit_path = attempt / 'capture-seal.json', attempt / 'native-exit.json'
        if not seal_path.is_file() or not exit_path.is_file():
            raise ValueError('Sealed Native source and owner exit missing')
        seal, owner = json.loads(seal_path.read_text()), json.loads(exit_path.read_text())
        if (seal.get('provenance_kind') != 'native' or seal.get('restoration', {}).get('restored') is not True
                or owner.get('event') != 'native_exit' or owner.get('capture_seal_sha256') != digest(seal_path)):
            raise ValueError('Native source and owner closure differ')
        review_path = attempt / 'independent-physical-review.json'
        if not review_path.is_file():
            raise ValueError('Independent physical/pixel review missing')
        review = json.loads(review_path.read_text())
        if review.get('case_id') != case or review.get('source_sha256') != proof['source_sha256']:
            raise ValueError('Independent review source identity differs')
        for subject in ('subject_body', 'one_way_source', 'two_directional_destination',
                        'left_curb', 'destination_centerline', 'approach', 'departure'):
            item = review.get('visible', {}).get(subject, {})
            camera, frame = item.get('camera'), item.get('video_frame')
            if (camera not in CAMERAS or type(frame) is not int
                    or not 0 <= frame < proof['original_frame_count']
                    or item.get('observed') is not True
                    or item.get('camera_sha256') != proof['camera_sha256'][camera]):
                raise ValueError('Original physical/pixel evidence missing: ' + subject)
    return {'format': 'worker-delivery-audit', 'case_id': case,
            'scope': 'synthetic software diagnostic' if diagnostic_fixture else 'source-bound Native review',
            'original_sha256': proof['source_sha256'], 'frames': proof['original_frame_count'],
            'cameras': proof['camera_sha256'], 'auditor_sha256': digest(__file__),
            'saved_source_auditor_sha256': digest(folder / 'turn_source_audit.py'),
            'pixel_review': review,
            'checks': {'native_source': not diagnostic_fixture, 'all_participants': True,
                       'time_join': True, 'full_video_decode': True,
                       'actual_pixels': review is not None, 'physical_completion': review is not None},
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--folder', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--saved-analysis', required=True)
    parser.add_argument('--diagnostic-fixture', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.folder, args.case, args.attempt, args.saved_analysis,
                           diagnostic_fixture=args.diagnostic_fixture), indent=2))


if __name__ == '__main__':
    main()
