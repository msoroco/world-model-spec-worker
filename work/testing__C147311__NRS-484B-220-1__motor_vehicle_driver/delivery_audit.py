"""Independent full-duration source audit for the paired one-way cases."""
import argparse
import hashlib
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]/'runtime/scenario_pipeline'))

from camera_setup import PROFILE
from one_way_measurements import analyze
from worker_exchange.media import audit as decode_video
from worker_exchange.measurement_contract import verify_report

CAMERAS = tuple(PROFILE)
ASSIGNMENT = 'testing__C147311__NRS-484B-220-1__motor_vehicle_driver'


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def audit(attempt, package, *, expected_frames=900, diagnostic_fixture=False):
    """Recompute original joins, source measurements and every decoded camera frame.

    A shorter expected_frames value is useful only for diagnostic fixtures. Delivery
    requires the default 900 frames at the pinned 20 Hz, 45-second duration.
    """
    attempt, package = Path(attempt), Path(package)
    if type(expected_frames) is not int or expected_frames < 2:
        raise ValueError('Positive exact frame count required')
    config = json.loads((attempt/'config.json').read_text())
    if (config.get('law_id') != 'NRS-484B-220-1' or config.get('cell_id') != 'C147311' or
            config.get('rate_hz') != 20 or config.get('duration_s') != 45 or
            config.get('selected_case_id') not in
            (ASSIGNMENT+'__source_verified_with_designation',
             ASSIGNMENT+'__source_verified_against_designation')):
        raise ValueError('Exact one-way cell, case and capture settings required')
    frame_map = attempt/'video_frames.jsonl'
    rows = _rows(frame_map)
    if len(rows) != expected_frames:
        raise ValueError('Full original frame-map duration required')
    last_frame, last_time = -1, float('-inf')
    for index, row in enumerate(rows):
        frame, time = row.get('carla_frame'), row.get('time_s')
        if (row.get('video_frame') != index or type(frame) is not int or
                frame <= last_frame or type(time) not in (int, float) or
                not math.isfinite(time) or time <= last_time or
                (index and abs(time-last_time-0.05) > 1e-3)):
            raise ValueError('Original frame, time or 20 Hz join failed')
        last_frame, last_time = frame, time
    measured = analyze(attempt)
    if len(measured['samples']) != expected_frames:
        raise ValueError('Source measurement duration differs from cameras')
    analysis_path = attempt/'analysis-report.json'
    analysis = json.loads(analysis_path.read_text())
    contract = json.loads((package/'measurement-contract.json').read_text())
    verified = verify_report(contract, analysis, attempt)
    if set(verified) != {'one_way_direction'}:
        raise ValueError('One-way measurement contract not verified')
    decodes = {}
    for name, dimensions in PROFILE.items():
        video = attempt/(name+'.mkv')
        if not video.is_file():
            raise ValueError('Missing original camera: '+name)
        receipt = decode_video(video, expected_frames, mapping_sha256=_sha(frame_map))
        if receipt['dimensions'] != list(dimensions):
            raise ValueError('Original camera dimensions differ: '+name)
        decodes[name] = {'sha256': receipt['video_sha256'], 'decoded_frames': receipt['frames']}
    if not diagnostic_fixture:
        if expected_frames != 900:
            raise ValueError('Full 900-frame Native delivery required')
        provenance = json.loads((attempt/'acquisition-provenance.json').read_text())
        if provenance.get('provenance_kind') != 'native' or provenance.get('diagnostic_fixture'):
            raise ValueError('Native original source provenance required')
        result = json.loads((attempt/'result.json').read_text())
        if (result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met' or
                not result.get('maneuver_completed')):
            raise ValueError('Original physical completion required')
        review = json.loads((attempt/'pixel-review.json').read_text())
        if (review.get('case_id') != config['selected_case_id'] or
                review.get('original_frame_map_sha256') != _sha(frame_map) or
                review.get('source_decodes') != decodes or not review.get('independent_reviewer') or
                not review.get('method') or not review.get('sign_visible_frames') or
                review.get('complete_body_visible_frames') != list(range(900))):
            raise ValueError('Independent original-camera pixel reviewer required')
    return {'format': 'worker-c147311-independent-delivery-audit',
            'case_id': config['selected_case_id'], 'expected_frames': expected_frames,
            'original_frame_map_sha256': _sha(frame_map),
            'analysis_sha256': _sha(analysis_path), 'verified_measurements': sorted(verified),
            'source_decodes': decodes, 'software_audit_passed': True,
            'diagnostic_fixture_only': diagnostic_fixture,
            'physical_acceptance_claimed': False, 'legal_conclusion': 'unresolved'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--diagnostic-fixture', action='store_true')
    args = parser.parse_args()
    if args.case not in (ASSIGNMENT+'__source_verified_with_designation',
                         ASSIGNMENT+'__source_verified_against_designation'):
        raise ValueError('Exact selected case required')
    receipt = audit(args.attempt, Path(__file__).resolve().parent,
                    expected_frames=9 if args.diagnostic_fixture else 900,
                    diagnostic_fixture=args.diagnostic_fixture)
    if receipt['case_id'] != args.case:
        raise ValueError('Audit selected another case')
    print(json.dumps(receipt, sort_keys=True))
