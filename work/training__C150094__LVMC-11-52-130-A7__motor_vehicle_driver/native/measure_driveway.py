"""Measure parked vehicle footprint against a reviewed driveway opening."""
import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path

ASSIGNMENT = 'training__C150094__LVMC-11-52-130-A7__motor_vehicle_driver'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')
COUNT = 600
FIVE_FEET_M = 1.524


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def lines(path):
    return [json.loads(s) for s in path.read_text().splitlines() if s.strip()]


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def measure(root):
    root = Path(root)
    paths = {n: root / n for n in ('video_frames.jsonl', 'native_parking_trace.jsonl', 'driveway_context.json')}
    for n, p in paths.items():
        if not p.is_file():
            raise ValueError('Missing saved source: ' + n)
    frames, trace = lines(paths['video_frames.jsonl']), lines(paths['native_parking_trace.jsonl'])
    context = json.loads(paths['driveway_context.json'].read_text())
    if len(frames) != COUNT or len(trace) != COUNT:
        raise ValueError('Requires 600 joined original frames')
    if context.get('assignment_id') != ASSIGNMENT or context.get('review_kind') not in ('synthetic_diagnostic', 'original_source_review'):
        raise ValueError('Assignment or source provenance mismatch')
    hashes = {}
    for camera in CAMERAS:
        n = camera + '.mkv'
        p = root / n
        if not p.is_file() or not p.stat().st_size:
            raise ValueError('Missing source camera: ' + camera)
        proc = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries',
                               'stream=nb_read_frames,r_frame_rate,width,height', '-of', 'json', str(p)],
                              capture_output=True, text=True)
        if proc.returncode:
            raise ValueError('Source camera decode failed: ' + camera)
        streams = json.loads(proc.stdout).get('streams', [])
        if len(streams) != 1 or streams[0].get('nb_read_frames') != str(COUNT) or streams[0].get('r_frame_rate') != '20/1':
            raise ValueError('Source camera requires 600 decoded 20 Hz frames: ' + camera)
        if context['review_kind'] == 'original_source_review' and (streams[0].get('width'), streams[0].get('height')) != ((1920, 1080) if camera == 'overview' else (1280, 720)):
            raise ValueError('Original camera resolution mismatch: ' + camera)
        hashes[n] = sha(p)
    if context.get('camera_sha256') != hashes:
        raise ValueError('Context not bound to source camera bytes')
    for key in ('reviewer', 'driveway_boundary_source', 'vehicle_extent_source', 'parking_state_source',
                'private_driveway_authority_source', 'usps_official_business_source',
                'traffic_conflict_source', 'lawful_direction_source'):
        if not context.get(key):
            raise ValueError('Missing reviewed context source: ' + key)
    bounds = context.get('driveway_curb_interval_m')
    if not isinstance(bounds, list) or len(bounds) != 2 or not all(finite(v) for v in bounds) or bounds[0] >= bounds[1]:
        raise ValueError('Invalid sourced driveway opening')
    if context.get('driveway_kind') not in ('public', 'private'):
        raise ValueError('Unknown driveway kind')
    for key in ('owner_controller_family_invitee', 'usps_vehicle', 'usps_official_business',
                'necessary_to_avoid_traffic_conflict', 'complying_with_law', 'officer_direction',
                'traffic_device_direction'):
        if type(context.get(key)) is not bool:
            raise ValueError('Missing reviewed exception fact: ' + key)
    if context['owner_controller_family_invitee'] and context['driveway_kind'] != 'private':
        raise ValueError('Private driveway authority claimed for public driveway')
    prev_native, prev_t = -1, -1.0
    rest, signed_gaps = [], []
    expected = 'synthetic_native_sample' if context['review_kind'] == 'synthetic_diagnostic' else 'original_native_pose'
    for i, (frame, row) in enumerate(zip(frames, trace)):
        native, t = frame.get('native_frame'), frame.get('time_s')
        if frame.get('video_frame') != i or type(native) is not int or native <= prev_native:
            raise ValueError('Invalid original frame identity')
        if not finite(t) or t <= prev_t or (i and abs(t - prev_t-.05) > .005):
            raise ValueError('Invalid original 20 Hz cadence')
        if row.get('video_frame') != i or row.get('native_frame') != native or row.get('source_kind') != expected:
            raise ValueError('Parking trace does not join original frame/provenance')
        for key in ('ego_curb_station_m', 'ego_half_length_m', 'ego_speed_mps'):
            if not finite(row.get(key)):
                raise ValueError('Missing finite Native measurement: ' + key)
        if row['ego_half_length_m'] <= 0 or row['ego_speed_mps'] < 0:
            raise ValueError('Invalid vehicle extent or speed')
        if type(row.get('park_brake_engaged')) is not bool:
            raise ValueError('Missing Native parking brake state')
        low = row['ego_curb_station_m'] - row['ego_half_length_m']
        high = row['ego_curb_station_m'] + row['ego_half_length_m']
        gap = max(bounds[0]-high, low-bounds[1], 0.0)
        at_rest = row['ego_speed_mps'] <= .05
        rest.append(at_rest)
        signed_gaps.append(gap)
        prev_native, prev_t = native, t
    if prev_t - frames[0]['time_s'] < 29.9:
        raise ValueError('Source span less than 30 seconds')
    rest_frames = [i for i, v in enumerate(rest) if v]
    if not rest_frames:
        raise ValueError('No stopped, standing or parked episode')
    near = [i for i in rest_frames if signed_gaps[i] <= FIVE_FEET_M + 1e-9]
    front = [i for i in rest_frames if signed_gaps[i] == 0.0]
    private_exception_context = context['driveway_kind'] == 'private' and context['owner_controller_family_invitee']
    postal_exception_context = context['usps_vehicle'] and context['usps_official_business']
    return {'format': 'saved-driveway-footprint-observation', 'assignment_id': ASSIGNMENT,
            'review_kind': context['review_kind'],
            'sources': {**{n: sha(p) for n, p in paths.items()}, **hashes},
            'sample_count': COUNT, 'sample_span_s': prev_t-frames[0]['time_s'],
            'rest_frame_count': len(rest_frames), 'first_rest_frame': rest_frames[0],
            'minimum_footprint_gap_m_at_rest': min(signed_gaps[i] for i in rest_frames),
            'front_of_driveway_frame_count': len(front), 'within_five_feet_frame_count': len(near),
            'five_feet_m': FIVE_FEET_M,
            'private_driveway_authority_context': private_exception_context,
            'usps_official_business_context': postal_exception_context,
            'necessary_traffic_conflict_context': context['necessary_to_avoid_traffic_conflict'],
            'law_or_officer_or_device_direction_context': any(context[k] for k in
                ('complying_with_law', 'officer_direction', 'traffic_device_direction')),
            'physical_acceptance_claimed': False, 'legal_verdict_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('source_dir')
    parser.add_argument('output_json')
    args = parser.parse_args()
    Path(args.output_json).write_text(json.dumps(measure(args.source_dir), indent=2) + '\n')
