"""Independent full-duration source audit for the paired one-way cases."""
import hashlib
import json
import math
from pathlib import Path

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


def audit(attempt, package, *, expected_frames=900):
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
    return {'format': 'worker-c147311-independent-delivery-audit',
            'case_id': config['selected_case_id'], 'expected_frames': expected_frames,
            'original_frame_map_sha256': _sha(frame_map),
            'analysis_sha256': _sha(analysis_path), 'verified_measurements': sorted(verified),
            'source_decodes': decodes, 'software_audit_passed': True,
            'physical_acceptance_claimed': False, 'legal_conclusion': 'unresolved'}
