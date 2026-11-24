"""Materialize three exact unselected intersection/centerline CPU requests."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n')


def config(suffix):
    case = ROOT.name + '__' + suffix
    target = {
        'probe_01': ('-1', '-1'),
        'probe_02': ('1', '-1'),
        'probe_03': ('-1', '1'),
    }[suffix]
    phases = [('approach_before_zone', 0, 239, '-1'),
              ('approach_within_zone', 240, 359, target[0]),
              ('intersection_traversal', 360, 519, target[1]),
              ('departure', 520, 599, '-1')]
    return {
        'case_id': case, 'selected_case_id': case,
        'law_id': 'NRS-484B-213-2b', 'cell_id': 'C111250',
        'actor': 'motor_vehicle_driver', 'rate_hz': 20,
        'duration_s': 30, 'duration_frames': 600,
        'cameras': [{'name': name, 'fps': 20, 'width': width, 'height': height}
                    for name, width, height in
                    [('overview', 1920, 1080), ('approach', 1280, 720),
                     ('reference_corner', 1280, 720), ('driver_reference', 1280, 720)]],
        'road_directionality': 'two_way', 'one_way_highway': False,
        'railroad_crossing_claimed': False,
        'ego_lane_id': '-1', 'opposing_lane_id': '1',
        'ego_spawn': {'road_id': '1', 'lane_id': '-1', 's_m': 15},
        'control_phases': [{'name': name, 'first_frame': first, 'last_frame': last,
                            'target_lane_id': lane, 'target_speed_mps': 5.0}
                           for name, first, last, lane in phases],
        'acquire': ['original_ego_transform', 'ego_bounding_box',
                    'road_centerline_readback', 'lane_direction_readback',
                    'intersection_boundary_readback', 'four_source_camera_frames'],
        'distance_proxy': 'vehicle_front_to_intersection_entry_m',
        'distance_threshold_m': 30.48,
        'physical_verified': False, 'legal_verdict': None,
    }


def main():
    road = (HERE / 'road.xodr').read_text()
    cases = []
    for suffix in ('probe_01', 'probe_02', 'probe_03'):
        cfg = config(suffix)
        path = ROOT / 'draft-cases' / suffix / 'primary' / 'construction.json'
        bundle = {
            'format': 'worker-inline-construction', 'case_id': cfg['case_id'],
            'cell_id': 'C111250', 'law_id': 'NRS-484B-213-2b',
            'actor': 'motor_vehicle_driver', 'entrypoint': 'runner.py',
            'status': 'draft_cpu_offline_only',
            'files': [{'path': 'config.json', 'content': json.dumps(cfg, indent=2) + '\n'},
                      {'path': 'road.xodr', 'content': road},
                      {'path': 'runner.py', 'content': (HERE / 'draft_runner.py').read_text()},
                      {'path': 'tests/test_offline.py', 'content': (HERE / 'test_draft_offline.py').read_text()}],
            'recording_description': {
                'channels': [
                    {'name': 'original_centerline_and_footprint',
                     'method': 'Native transforms, body bounding box, centerline and intersection boundary readback',
                     'sampling_rate_hz': 20, 'time_window': '600 frames'},
                    {'name': 'four_source_cameras', 'method': 'synchronized source pixels',
                     'sampling_rate_hz': 20, 'time_window': '600 frames'}],
                'limitations': ['Native lane position and intersection geometry have not been observed',
                                '30.48 m threshold is an engineering proxy, not a legal conclusion']}}
        write(path, bundle)
        cases.append({'case_id': cfg['case_id'], 'kind': 'draft_not_selected',
                      'construction': str(path.relative_to(ROOT)),
                      'construction_sha256': sha(path),
                      'candidate_risk': {'status': 'physical',
                                         'reason': 'Centerline transition and full vehicle footprint require original Native evidence.'}})
    manifest = {'format': 'worker-unselected-draft-construction-manifest-v1',
                'assignment_id': ROOT.name, 'status': 'draft_cpu_offline_only',
                'cases': cases, 'original_native_observed': False, 'delivery_ready': False}
    target = ROOT / 'draft-manifest.json'
    write(target, manifest)
    print(json.dumps({'manifest_sha256': sha(target), 'cases': cases}, indent=2))


if __name__ == '__main__':
    main()
