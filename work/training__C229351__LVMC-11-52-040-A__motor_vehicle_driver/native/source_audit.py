"""Source joins and controlled comparisons for roadway standing and parking.

These checks establish provenance and measured differences only. They do not
decide statutory compliance, activity purpose, or Chapter exceptions.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

from selected_plan import CASES, compare as compare_requests, request


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_jsonl(path):
    rows = [json.loads(line) for line in Path(path).read_text().splitlines() if line]
    require(len(rows) >= 2, 'at least two original Native frames required')
    return rows


def finite_number(value):
    return type(value) in (int, float) and math.isfinite(value)


def unit(value):
    require(isinstance(value, list) and len(value) == 2 and all(finite_number(x) for x in value),
            'invalid original direction vector')
    norm = math.hypot(*value)
    require(norm > 0, 'zero original direction vector')
    return [value[0] / norm, value[1] / norm]


def angle(a, b, unsigned=False):
    dot = max(-1, min(1, a[0] * b[0] + a[1] * b[1]))
    return math.degrees(math.acos(abs(dot) if unsigned else dot))


def extract(case_id, native_path, frames_path, geometry_path, survey_path, allow_fixture=False):
    """Bind pose and geometry to complete matching original frame identities."""
    require(case_id in CASES, 'unknown exact case')
    native_path, frames_path = Path(native_path), Path(frames_path)
    geometry_path, survey_path = Path(geometry_path), Path(survey_path)
    survey = json.loads(survey_path.read_text())
    planned = request(case_id, survey, allow_fixture=allow_fixture)
    geometry = json.loads(geometry_path.read_text())
    expected_geometry = 'synthetic_cpu_road_geometry' if allow_fixture else 'original_native_road_geometry'
    require(geometry.get('source_kind') == expected_geometry,
            'original Native road geometry required' if not allow_fixture else 'synthetic CPU road geometry required')
    require(geometry.get('survey_sha256') == digest(survey_path),
            'road geometry survey hash mismatch')
    for key, expected in (('roadway_boundary_source_id', planned['fixed_roadway_source']),
                          ('lawful_traffic_source_id', planned['fixed_lawful_direction_source'])):
        require(geometry.get(key) == expected, 'road geometry source mismatch: ' + key)
    require(geometry.get('roadway_class') == 'roadway' and geometry.get('road_edge_identified') is True,
            'original roadway edge not established')
    require(geometry.get('edge_tangent_xy') == survey['edge_tangent_xy'] and
            geometry.get('lawful_traffic_direction_xy') == survey['lawful_direction_xy'],
            'original geometry direction mismatch')
    native, frames = read_jsonl(native_path), read_jsonl(frames_path)
    require(len(native) == len(frames), 'Native and camera frame counts differ')
    poses = []
    previous_frame, previous_time = -1, -math.inf
    for sample, image in zip(native, frames):
        expected_sample = 'synthetic_cpu_fixture' if allow_fixture else 'original_native'
        require(sample.get('source_kind') == expected_sample and sample.get('case_id') == case_id,
                'source case identity required')
        frame, time = sample.get('native_frame'), sample.get('time_s')
        require(type(frame) is int and frame > previous_frame and finite_number(time) and
                time > previous_time, 'Native frame/time order invalid')
        require(image.get('native_frame') == frame and image.get('time_s') == time and
                image.get('all_four_cameras_joined') is True,
                'four-camera and Native frame join failed')
        xy, yaw, speed = sample.get('ego_center_xy_m'), sample.get('ego_front_yaw_deg'), sample.get('ego_speed_mps')
        require(isinstance(xy, list) and len(xy) == 2 and all(finite_number(x) for x in xy) and
                finite_number(yaw) and finite_number(speed) and speed >= 0,
                'incomplete original vehicle pose')
        require(sample.get('roadway_boundary_source_id') == geometry['roadway_boundary_source_id'] and
                sample.get('lawful_traffic_source_id') == geometry['lawful_traffic_source_id'],
                'original sample road source changed')
        poses.append({'frame': frame, 'time_s': time, 'center_xy': xy,
                      'heading_deg': yaw, 'speed_mps': speed})
        previous_frame, previous_time = frame, time
    return {
        'format': 'worker-saved-pose-extract', 'case_id': case_id,
        'native_trace_path': str(native_path), 'native_trace_sha256': digest(native_path),
        'video_frames_path': str(frames_path), 'video_frames_sha256': digest(frames_path),
        'geometry_path': str(geometry_path), 'geometry_sha256': digest(geometry_path),
        'survey_path': str(survey_path), 'survey_sha256': digest(survey_path),
        'requested_activity': planned['activity_requested'],
        'requested_pose': planned['rest_pose_requested'],
        'actual_activity_source_review_required': True,
        'chapter_exception_source_review_required': True,
        'frames': poses,
    }


def comparison_audit(extracts, surveys, observed):
    """Check all planned cases and pairwise controlled source conditions."""
    require(set(extracts) == set(CASES) and set(observed) == set(CASES),
            'all six exact source extracts and observations required')
    plans = {case: request(case, surveys[case]) for case in CASES}
    compare_requests(plans)
    baseline = next(iter(CASES))
    fixed = ('geometry_sha256', 'survey_sha256')
    for case in CASES:
        item, measurement = extracts[case], observed[case]
        require(item.get('case_id') == case and item.get('format') == 'worker-saved-pose-extract',
                'exact saved pose extract required')
        require(item.get('requested_activity') == CASES[case]['activity'] and
                item.get('requested_pose') == CASES[case]['pose'],
                'activity or pose request changed')
        for name, field in (('native_trace_path', 'native_trace_sha256'),
                            ('video_frames_path', 'video_frames_sha256'),
                            ('survey_path', 'survey_sha256')):
            require(item.get(name) and digest(item[name]) == item.get(field),
                    'comparison original source hash changed: ' + name)
        require(measurement.get('format') == 'worker-roadside-pose-observations' and
                measurement.get('native_trace_sha256') == item.get('native_trace_sha256') and
                len(measurement.get('observations', [])) == len(item.get('frames', [])),
                'measured observations not bound to source frames')
        geometry_path = Path(item['geometry_path'])
        require(digest(geometry_path) == item['geometry_sha256'] and
                measurement.get('geometry_source_sha256') == item['geometry_sha256'],
                'measured geometry not bound to original source')
        geometry = json.loads(geometry_path.read_text())
        edge, lawful = unit(geometry['edge_tangent_xy']), unit(geometry['lawful_traffic_direction_xy'])
        for source, row in zip(item['frames'], measurement['observations']):
            heading = math.radians(source['heading_deg'])
            vector = [math.cos(heading), math.sin(heading)]
            expected = {'edge_parallel_angle_deg': angle(vector, edge, True),
                        'lawful_traffic_heading_angle_deg': angle(vector, lawful),
                        'speed_mps': source['speed_mps']}
            require(row.get('frame') == source['frame'] and row.get('time_s') == source['time_s'],
                    'measured frame identity changed')
            for key, value in expected.items():
                require(finite_number(row.get(key)) and math.isclose(row[key], value, abs_tol=1e-6),
                        'measured source value changed: ' + key)
        for key in fixed:
            require(item.get(key) == extracts[baseline].get(key),
                    'comparison fixed source changed: ' + key)
    pairs = []
    for activity in ('parking', 'standing'):
        base = next(c for c, s in CASES.items() if s == {'activity': activity, 'pose': 'parallel_lawful', 'requested_yaw_offset_deg': 0.0})
        angled = next(c for c, s in CASES.items() if s['activity'] == activity and s['pose'] == 'angled_traffic_side')
        reverse = next(c for c, s in CASES.items() if s['activity'] == activity and s['pose'] == 'parallel_against_traffic')
        pairs.extend([('edge_angle', base, angled), ('travel_direction', base, reverse)])
    for pose in ('parallel_lawful', 'angled_traffic_side', 'parallel_against_traffic'):
        park = next(c for c, s in CASES.items() if s['activity'] == 'parking' and s['pose'] == pose)
        stand = next(c for c, s in CASES.items() if s['activity'] == 'standing' and s['pose'] == pose)
        pairs.append(('activity', park, stand))
    reports = []
    for kind, first, second in pairs:
        a = observed[first]['observations'][-1]
        b = observed[second]['observations'][-1]
        for field in ('edge_parallel_angle_deg', 'lawful_traffic_heading_angle_deg', 'speed_mps'):
            require(finite_number(a.get(field)) and finite_number(b.get(field)),
                    'missing measured comparison field: ' + field)
        reports.append({'kind': kind, 'case_ids': [first, second],
                        'requested_difference': 'activity' if kind == 'activity' else 'resting_yaw',
                        'measured_edge_angle_deg': [a['edge_parallel_angle_deg'], b['edge_parallel_angle_deg']],
                        'measured_lawful_heading_deg': [a['lawful_traffic_heading_angle_deg'], b['lawful_traffic_heading_angle_deg']],
                        'measured_speed_mps': [a['speed_mps'], b['speed_mps']],
                        'actual_activity_review_required': True})
    return {'format': 'worker-roadside-comparison-audit', 'case_ids': list(CASES),
            'source_bound': True, 'fixed_source_fields': list(fixed),
            'comparisons': reports,
            'physical_completion': 'unverified', 'legal_result': None}


def road_edge_context(geometry_path, allow_fixture=False):
    path = Path(geometry_path)
    geometry = json.loads(path.read_text())
    expected = 'synthetic_cpu_road_geometry' if allow_fixture else 'original_native_road_geometry'
    require(geometry.get('source_kind') == expected and
            geometry.get('roadway_class') == 'roadway' and geometry.get('road_edge_identified') is True,
            'original roadway edge not established')
    return {'format': 'worker-road-edge-context', 'source_path': str(path),
            'source_sha256': digest(path), 'roadway_class': 'roadway',
            'road_edge_identified': True,
            'edge_tangent_xy': geometry['edge_tangent_xy'],
            'lawful_traffic_direction_xy': geometry['lawful_traffic_direction_xy']}


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--native', required=True)
    parser.add_argument('--frames', required=True)
    parser.add_argument('--geometry', required=True)
    parser.add_argument('--survey', required=True)
    parser.add_argument('--pose-output', required=True)
    parser.add_argument('--context-output', required=True)
    args = parser.parse_args()
    pose = extract(args.case, args.native, args.frames, args.geometry, args.survey)
    context = road_edge_context(args.geometry)
    Path(args.pose_output).write_text(json.dumps(pose, indent=2, sort_keys=True) + '\n')
    Path(args.context_output).write_text(json.dumps(context, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
