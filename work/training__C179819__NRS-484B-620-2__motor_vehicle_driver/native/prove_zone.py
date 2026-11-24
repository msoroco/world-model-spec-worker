"""CPU-only signed-zone source and velocity diagnostic."""
import copy
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from measure_zone import AID, COUNT, MPS_PER_MPH, measure


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
    assignment = Path(__file__).resolve().parents[3] / 'inputs' / AID / 'assignment.json'
    assert assignment.is_file()
    with tempfile.TemporaryDirectory(prefix='zone-', dir=os.environ['TMPDIR']) as name:
        root = Path(name)
        for camera in ('forward', 'rear', 'left', 'right'):
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=32x24:r=20',
                            '-frames:v', str(COUNT), '-c:v', 'ffv1', '-y', str(root / ('camera_'+camera+'.mkv'))], check=True)
        frames = [{'video_frame': i, 'native_frame': i+1000, 'time_s': round(i*.05, 3)} for i in range(COUNT)]
        motion = [{'video_frame': i, 'native_frame': i+1000, 'source_kind': 'synthetic_native_sample',
                   'road_id': 'paved_road', 'travel_direction_id': 'east',
                   'ego_x_m': i*.5, 'ego_y_m': 0.0,
                   'velocity_x_mps': 35*MPS_PER_MPH, 'velocity_y_mps': 0.0, 'velocity_z_mps': 0.0}
                  for i in range(COUNT)]
        context = {'assignment_id': AID, 'review_kind': 'synthetic_diagnostic',
                   'reviewer': 'synthetic CPU diagnostic',
                   'camera_sha256': {p.name: sha(p) for p in root.glob('camera_*.mkv')},
                   'zone_establishment_source': 'synthetic administrative declaration',
                   'installed_sign_source': 'synthetic sign fixture',
                   'authorized_value_source': 'synthetic sign face',
                   'zone_boundary_source': 'synthetic station fixture',
                   'governing_road_direction_source': 'synthetic route fixture',
                   'vehicle_class_source': 'synthetic blueprint fixture',
                   'road_id': 'paved_road', 'travel_direction_id': 'east',
                   'zone_established': True, 'appropriate_sign_installed': True,
                   'sign_governs_road_direction': True, 'ego_is_motor_vehicle': True,
                   'authorized_mph': 35.0, 'zone_station_bounds_m': [50.0, 200.0],
                   'road_axis_xy': [1.0, 0.0]}
        fp, mp, cp = (root / n for n in ('video_frames.jsonl', 'native_motion.jsonl', 'speed_zone_context.json'))
        save(fp, frames)
        save(mp, motion)
        cp.write_text(json.dumps(context))
        at_limit = measure(root)
        assert at_limit['first_zone_frame'] == 100 and at_limit['last_zone_frame'] == 400
        assert not at_limit['frames_above_authorized_in_zone']
        below = copy.deepcopy(motion)
        for row in below:
            row['velocity_x_mps'] = 34.5*MPS_PER_MPH
        save(mp, below)
        below_result = measure(root)
        assert not below_result['frames_above_authorized_in_zone']
        above = copy.deepcopy(motion)
        for row in above:
            row['velocity_x_mps'] = 35.5*MPS_PER_MPH
        save(mp, above)
        above_result = measure(root)
        assert len(above_result['frames_above_authorized_in_zone']) == 301
        save(mp, motion)
        ctx = copy.deepcopy(context)
        ctx['zone_established'] = False
        cp.write_text(json.dumps(ctx))
        unestablished = measure(root)
        assert not unestablished['source_reviewed_activation_complete']
        cp.write_text(json.dumps(context))
        failures = {}
        bad = copy.deepcopy(context)
        bad['camera_sha256']['camera_forward.mkv'] = '0'*64
        cp.write_text(json.dumps(bad))
        failures['camera_binding'] = rejects(root, 'camera bytes')
        bad = copy.deepcopy(context)
        bad.pop('zone_establishment_source')
        cp.write_text(json.dumps(bad))
        failures['establishment_source'] = rejects(root, 'zone_establishment_source')
        bad = copy.deepcopy(context)
        bad['authorized_mph'] = None
        cp.write_text(json.dumps(bad))
        failures['authorized_value'] = rejects(root, 'authorized speed')
        cp.write_text(json.dumps(context))
        bad_motion = copy.deepcopy(motion)
        bad_motion[200]['native_frame'] = bad_motion[199]['native_frame']
        save(mp, bad_motion)
        failures['frame_join'] = rejects(root, 'frame/provenance')
        bad_motion = copy.deepcopy(motion)
        bad_motion[200]['road_id'] = 'other_road'
        save(mp, bad_motion)
        failures['road_governance'] = rejects(root, 'sign governance')
        bad_motion = copy.deepcopy(motion)
        bad_motion[200]['source_kind'] = 'original_native_velocity'
        save(mp, bad_motion)
        failures['false_native_provenance'] = rejects(root, 'frame/provenance')
        save(mp, motion)
        fp.unlink()
        failures['missing_frame_source'] = rejects(root, 'video_frames.jsonl')
        print(json.dumps({'format': 'zone-cpu-proof', 'assignment_id': AID,
                          'assignment_sha256': sha(assignment), 'passed': True,
                          'at_limit_frames_above': len(at_limit['frames_above_authorized_in_zone']),
                          'below_frames_above': len(below_result['frames_above_authorized_in_zone']),
                          'above_frames_above': len(above_result['frames_above_authorized_in_zone']),
                          'unestablished_activation': unestablished['source_reviewed_activation_complete'],
                          'negative_rejections': failures, 'synthetic_only': True,
                          'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
