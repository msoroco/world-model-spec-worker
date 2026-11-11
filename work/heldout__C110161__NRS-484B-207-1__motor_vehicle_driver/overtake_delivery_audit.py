"""Independent retained-source check for a processed overtaking attempt."""

from hashlib import sha256
import json
from pathlib import Path

from overtake_measurement import measure


PREFIX = 'heldout__C110161__NRS-484B-207-1__motor_vehicle_driver__'
SUFFIXES = {'left_pass_wide', 'left_pass_narrow',
            'return_before_clear', 'return_after_clear'}
REQUIRED = {'config.json', 'trace.jsonl', 'video_frames.jsonl',
            'participant_footprints.jsonl', 'overview.mkv', 'approach.mkv',
            'reference_corner.mkv', 'driver_reference.mkv'}


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def audit(attempt, processing):
    attempt = Path(attempt).resolve()
    receipt_path = Path(processing).resolve()
    receipt = json.loads(receipt_path.read_text())
    config_path = attempt / 'config.json'
    if not config_path.is_file():
        raise ValueError('Missing original delivery config')
    config = json.loads(config_path.read_text())
    case = config.get('selected_case_id')
    if case not in {PREFIX + suffix for suffix in SUFFIXES}:
        raise ValueError('Unknown exact overtaking case')
    if (receipt.get('case_id') != case or receipt.get('format') != 'worker-saved-processing'
            or receipt.get('passed') is not True or receipt.get('recorded_only') is not True
            or receipt.get('originals_preserved') is not True
            or receipt.get('missing_evidence') is not False
            or receipt.get('candidate_id') != 'primary'
            or receipt.get('physical_acceptance_claimed') is not False
            or receipt.get('legal_acceptance_claimed') is not False):
        raise ValueError('Incomplete or mismatched saved processing receipt')
    if receipt.get('final_video_checks', {}).get('passed') is not True:
        raise ValueError('Four-camera final decode missing')
    hashes = receipt.get('original_source_hashes', {})
    if not REQUIRED <= hashes.keys():
        raise ValueError('Missing required original source hash')
    for name, expected in hashes.items():
        path = (attempt / name).resolve()
        if attempt not in path.parents or not path.is_file() or digest(path) != expected:
            raise ValueError('Original source changed or missing: ' + name)
    construction = attempt / 'construction.json'
    if (not construction.is_file() or
            digest(construction) != receipt.get('analysis_revision', {}).get('construction_sha256')):
        raise ValueError('Selected construction changed')
    result_path = Path(receipt.get('result', '')).resolve()
    if not result_path.is_file() or digest(result_path) != receipt.get('result_sha256'):
        raise ValueError('Saved result changed or missing')
    result = json.loads(result_path.read_text())
    observation = measure(attempt / 'participant_footprints.jsonl')
    expected = {'left_pass_clearance_m': observation['min_abreast_lateral_gap_m'],
                'return_clearance_m': observation['clearance_at_first_return_m']}
    if result.get('case_id') != case or any(
            result.get('realized_observables', {}).get(name, {}).get('value') != value
            for name, value in expected.items()):
        raise ValueError('Saved overtaking result differs from original geometry')
    if result.get('physical_acceptance_claimed') is not False or result.get('legal_acceptance_claimed') is not False:
        raise ValueError('Synthetic saved result claims acceptance')
    return {'format': 'worker-overtake-delivery-source-audit', 'case_id': case,
            'receipt_sha256': digest(receipt_path), 'result_sha256': digest(result_path),
            'original_source_hashes': {name: hashes[name] for name in sorted(REQUIRED)},
            'measured_values': expected, 'source_integrity_passed': True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}
