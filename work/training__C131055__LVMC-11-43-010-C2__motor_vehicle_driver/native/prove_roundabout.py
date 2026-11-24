"""Synthetic saved-source CPU proof for the roundabout lane measurement."""
import copy
import hashlib
import json
import os
import subprocess
import tempfile
from pathlib import Path

from measure_roundabout import ASSIGNMENT, COUNT, measure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, items):
    path.write_text(''.join(json.dumps(x, sort_keys=True) + '\n' for x in items))


def rejects(root, fragment):
    try:
        measure(root)
    except ValueError as exc:
        assert fragment in str(exc), (str(exc), fragment)
        return str(exc)
    raise AssertionError('Invalid source accepted: ' + fragment)


def main():
    source_assignment = Path(__file__).resolve().parents[3] / 'inputs' / ASSIGNMENT / 'assignment.json'
    assert source_assignment.is_file()
    with tempfile.TemporaryDirectory(prefix='roundabout-', dir=os.environ['TMPDIR']) as name:
        root = Path(name)
        for camera in ('forward', 'rear', 'left', 'right'):
            subprocess.run(['ffmpeg', '-v', 'error', '-f', 'lavfi', '-i', 'color=c=black:s=32x24:r=20',
                            '-frames:v', str(COUNT), '-c:v', 'ffv1', '-y', str(root / ('camera_' + camera + '.mkv'))],
                           check=True)
        frames = [{'video_frame': i, 'native_frame': i+1000, 'time_s': round(i*.05, 3)} for i in range(COUNT)]
        trace = [{'video_frame': i, 'native_frame': i+1000, 'source_kind': 'synthetic_native_sample',
                  'native_road_id': 'entry' if i < 100 else ('circle' if i < 400 else 'right_exit'),
                  'native_lane_id': 'R', 'ego_x_m': i*.1, 'ego_y_m': 0.0,
                  'ego_heading_deg': 0.0 if i < 100 else (90.0 if i < 400 else -90.0)}
                 for i in range(COUNT)]
        topology = {'assignment_id': ASSIGNMENT, 'review_kind': 'synthetic_diagnostic',
                    'reviewer': 'synthetic CPU diagnostic',
                    'camera_sha256': {p.name: sha(p) for p in root.glob('camera_*.mkv')},
                    'map_topology_source': 'synthetic map fixture',
                    'right_lane_adjacency_source': 'synthetic adjacency fixture',
                    'entry_exit_route_source': 'synthetic route fixture',
                    'intention_declaration_source': 'synthetic controller route',
                    'right_lane_id': 'R', 'left_lane_id': 'L', 'roundabout_road_id': 'circle',
                    'entry_road_id': 'entry', 'right_exit_road_id': 'right_exit',
                    'intended_exit_road_id': 'right_exit'}
        fp, tp, cp = (root / n for n in ('video_frames.jsonl', 'native_lane_trace.jsonl', 'roundabout_topology.json'))
        save(fp, frames)
        save(tp, trace)
        cp.write_text(json.dumps(topology))
        right = measure(root)
        assert right['entry_video_frame'] == 100 and right['right_exit_video_frame'] == 400
        assert right['right_lane_through_movement'] and not right['circulatory_lane_change_frames']
        left = copy.deepcopy(trace)
        for row in left[100:400]:
            row['native_lane_id'] = 'L'
        save(tp, left)
        left_result = measure(root)
        assert not left_result['right_lane_through_movement'] and left_result['entry_lane_id'] == 'L'
        change = copy.deepcopy(trace)
        for row in change[200:300]:
            row['native_lane_id'] = 'L'
        save(tp, change)
        change_result = measure(root)
        assert change_result['circulatory_lane_change_frames'] == [200, 300]
        save(tp, trace)
        failures = {}
        bad = copy.deepcopy(topology)
        bad['camera_sha256']['camera_forward.mkv'] = '0'*64
        cp.write_text(json.dumps(bad))
        failures['camera_byte_binding'] = rejects(root, 'camera bytes')
        bad = copy.deepcopy(topology)
        bad['intended_exit_road_id'] = 'left_exit'
        cp.write_text(json.dumps(bad))
        failures['wrong_declared_exit'] = rejects(root, 'not the right exit')
        bad = copy.deepcopy(topology)
        bad.pop('right_lane_adjacency_source')
        cp.write_text(json.dumps(bad))
        failures['missing_adjacency_review'] = rejects(root, 'right_lane_adjacency_source')
        cp.write_text(json.dumps(topology))
        bad_trace = copy.deepcopy(trace)
        bad_trace[200]['native_frame'] = bad_trace[199]['native_frame']
        save(tp, bad_trace)
        failures['frame_join'] = rejects(root, 'frame/provenance')
        bad_trace = copy.deepcopy(trace)
        bad_trace[200]['native_lane_id'] = 'unknown'
        save(tp, bad_trace)
        failures['unknown_lane'] = rejects(root, 'reviewed adjacency')
        bad_trace = copy.deepcopy(trace)
        bad_trace[200]['source_kind'] = 'original_native_pose'
        save(tp, bad_trace)
        failures['false_native_provenance'] = rejects(root, 'frame/provenance')
        save(tp, trace)
        fp.unlink()
        failures['missing_frame_source'] = rejects(root, 'video_frames.jsonl')
        print(json.dumps({'format': 'roundabout-lane-cpu-proof', 'assignment_id': ASSIGNMENT,
                          'assignment_sha256': sha(source_assignment), 'passed': True,
                          'right_lane': right['right_lane_through_movement'],
                          'left_lane': left_result['right_lane_through_movement'],
                          'lane_change_frames': change_result['circulatory_lane_change_frames'],
                          'negative_rejections': failures, 'synthetic_only': True,
                          'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
