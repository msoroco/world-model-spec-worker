"""Synthetic CPU proof for saved-source driveway footprint and exceptions."""
import copy
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from measure_driveway import ASSIGNMENT, COUNT, FIVE_FEET_M, measure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, rows):
    path.write_text(''.join(json.dumps(row, sort_keys=True)+'\n' for row in rows))


def rejects(root, fragment):
    try:
        measure(root)
    except ValueError as exc:
        assert fragment in str(exc), (str(exc), fragment)
        return str(exc)
    raise AssertionError('Invalid source accepted: ' + fragment)


def main():
    assignment = Path(__file__).resolve().parents[3] / 'inputs' / ASSIGNMENT / 'assignment.json'
    assert assignment.is_file()
    with tempfile.TemporaryDirectory(prefix='driveway-', dir=os.environ['TMPDIR']) as name:
        root = Path(name)
        for camera in ('overview', 'approach', 'reference_corner', 'driver_reference'):
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=32x24:r=20',
                            '-frames:v', str(COUNT), '-c:v', 'ffv1', '-y', str(root / ('camera_'+camera+'.mkv'))], check=True)
        frames = [{'video_frame': i, 'native_frame': i+1000, 'time_s': round(i*.05, 3)} for i in range(COUNT)]
        trace = [{'video_frame': i, 'native_frame': i+1000, 'source_kind': 'synthetic_native_sample',
                  'ego_curb_station_m': 6.524, 'ego_half_length_m': 2.0,
                  'ego_speed_mps': 0.0, 'park_brake_engaged': True} for i in range(COUNT)]
        context = {'assignment_id': ASSIGNMENT, 'review_kind': 'synthetic_diagnostic',
                   'reviewer': 'synthetic CPU diagnostic',
                   'camera_sha256': {p.name: sha(p) for p in root.glob('camera_*.mkv')},
                   'driveway_boundary_source': 'synthetic curb fixture',
                   'vehicle_extent_source': 'synthetic Native bbox',
                   'parking_state_source': 'synthetic Native brake trace',
                   'private_driveway_authority_source': 'synthetic authority declaration',
                   'usps_official_business_source': 'synthetic business declaration',
                   'traffic_conflict_source': 'synthetic traffic context',
                   'lawful_direction_source': 'synthetic direction context',
                   'driveway_curb_interval_m': [0.0, 3.0], 'driveway_kind': 'private',
                   'owner_controller_family_invitee': False, 'usps_vehicle': False,
                   'usps_official_business': False, 'necessary_to_avoid_traffic_conflict': False,
                   'complying_with_law': False, 'officer_direction': False,
                   'traffic_device_direction': False}
        fp, tp, cp = (root / n for n in ('video_frames.jsonl', 'native_parking_trace.jsonl', 'driveway_context.json'))
        save(fp, frames)
        save(tp, trace)
        cp.write_text(json.dumps(context))
        at_boundary = measure(root)
        assert abs(at_boundary['minimum_footprint_gap_m_at_rest'] - FIVE_FEET_M) < 1e-8
        assert at_boundary['within_five_feet_frame_count'] == COUNT
        outside = copy.deepcopy(trace)
        for row in outside:
            row['ego_curb_station_m'] = 6.525
        save(tp, outside)
        outside_result = measure(root)
        assert outside_result['within_five_feet_frame_count'] == 0
        inside = copy.deepcopy(trace)
        for row in inside:
            row['ego_curb_station_m'] = 1.5
        save(tp, inside)
        inside_result = measure(root)
        assert inside_result['front_of_driveway_frame_count'] == COUNT
        save(tp, trace)
        ctx = copy.deepcopy(context)
        ctx['owner_controller_family_invitee'] = True
        cp.write_text(json.dumps(ctx))
        owner = measure(root)
        assert owner['private_driveway_authority_context']
        ctx = copy.deepcopy(context)
        ctx['usps_vehicle'] = True
        ctx['usps_official_business'] = True
        cp.write_text(json.dumps(ctx))
        postal = measure(root)
        assert postal['usps_official_business_context']
        ctx = copy.deepcopy(context)
        ctx['necessary_to_avoid_traffic_conflict'] = True
        cp.write_text(json.dumps(ctx))
        conflict = measure(root)
        assert conflict['necessary_traffic_conflict_context']
        ctx = copy.deepcopy(context)
        ctx['officer_direction'] = True
        cp.write_text(json.dumps(ctx))
        directed = measure(root)
        assert directed['law_or_officer_or_device_direction_context']
        failures = {}
        bad = copy.deepcopy(context)
        bad['camera_sha256']['camera_overview.mkv'] = '0'*64
        cp.write_text(json.dumps(bad))
        failures['unbound_camera'] = rejects(root, 'camera bytes')
        bad = copy.deepcopy(context)
        bad.pop('private_driveway_authority_source')
        cp.write_text(json.dumps(bad))
        failures['missing_authority_source'] = rejects(root, 'private_driveway_authority_source')
        bad = copy.deepcopy(context)
        bad['driveway_kind'] = 'public'
        bad['owner_controller_family_invitee'] = True
        cp.write_text(json.dumps(bad))
        failures['public_owner_claim'] = rejects(root, 'public driveway')
        cp.write_text(json.dumps(context))
        bad_trace = copy.deepcopy(trace)
        bad_trace[100]['native_frame'] = bad_trace[99]['native_frame']
        save(tp, bad_trace)
        failures['frame_join'] = rejects(root, 'frame/provenance')
        bad_trace = copy.deepcopy(trace)
        bad_trace[100]['ego_half_length_m'] = -1.0
        save(tp, bad_trace)
        failures['invalid_extent'] = rejects(root, 'extent or speed')
        bad_trace = copy.deepcopy(trace)
        bad_trace[100]['source_kind'] = 'original_native_pose'
        save(tp, bad_trace)
        failures['false_native_provenance'] = rejects(root, 'frame/provenance')
        save(tp, trace)
        fp.unlink()
        failures['missing_frame_source'] = rejects(root, 'video_frames.jsonl')
        print(json.dumps({'format': 'driveway-cpu-proof', 'assignment_id': ASSIGNMENT,
                          'assignment_sha256': sha(assignment), 'passed': True,
                          'boundary_gap_m': at_boundary['minimum_footprint_gap_m_at_rest'],
                          'outside_near_frames': outside_result['within_five_feet_frame_count'],
                          'front_frames': inside_result['front_of_driveway_frame_count'],
                          'owner_context': owner['private_driveway_authority_context'],
                          'postal_context': postal['usps_official_business_context'],
                          'conflict_context': conflict['necessary_traffic_conflict_context'],
                          'officer_context': directed['law_or_officer_or_device_direction_context'],
                          'negative_rejections': failures, 'synthetic_only': True,
                          'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
