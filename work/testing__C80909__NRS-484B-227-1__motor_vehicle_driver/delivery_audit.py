"""Independent original-source audit for one C80909 divided-road recording.

Diagnostic fixtures exercise the software path only. A Native acceptance also
requires an independent review of original pixels and site authority documents.
"""

import argparse
import hashlib
import json
import math
from pathlib import Path

from shapely.geometry import MultiPoint, Polygon
from worker_exchange.media import audit as audit_video
from worker_exchange.measurement_contract import verify_report


ROOT = Path(__file__).resolve().parent
PREFIX = 'testing__C80909__NRS-484B-227-1__motor_vehicle_driver__'
SUFFIXES = {'left_through_opening', 'left_across_blocked_divider',
            'left_at_established_crossover', 'left_right_roadway_continuation'}
CAMERAS = {'overview': (1920, 1080), 'approach': (1280, 720),
           'reference_corner': (1280, 720), 'driver_reference': (1280, 720)}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing original source: ' + path.name)
    return json.loads(path.read_text())


def rows(path):
    path = Path(path)
    if not path.is_file():
        raise ValueError('Missing original source: ' + path.name)
    value = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    if not value:
        raise ValueError('Empty original source: ' + path.name)
    return value


def body(points):
    if not isinstance(points, list) or len(points) < 4:
        raise ValueError('Missing complete original actor body')
    polygon = MultiPoint(points).convex_hull
    if polygon.area <= 0:
        raise ValueError('Degenerate original actor body')
    return polygon


def audit(attempt, case_id, *, diagnostic_fixture=False):
    attempt = Path(attempt)
    suffix = case_id.removeprefix(PREFIX)
    if not case_id.startswith(PREFIX) or suffix not in SUFFIXES:
        raise ValueError('Wrong exact C80909 case')
    config = read(attempt / 'config.json')
    construction = read(attempt / 'construction.json')
    if (config.get('selected_case_id') != case_id or construction.get('case_id') != case_id
            or config.get('cell_id') != 'C80909' or config.get('law_id') != 'NRS-484B-227-1'
            or config.get('actor') != 'motor_vehicle_driver' or config.get('rate_hz') != 20):
        raise ValueError('Exact construction or capture identity changed')
    frame_map = rows(attempt / 'video_frames.jsonl')
    movement = rows(attempt / 'movement_history.jsonl')
    trace = rows(attempt / 'trace.jsonl')
    evidence = rows(attempt / 'capture/evidence.jsonl')
    count = len(frame_map)
    if count < 4 or len(movement) != count or len(trace) != count or len(evidence) != count:
        raise ValueError('Original actor, trace and camera histories differ')
    for index, (frame, motion, tick, item) in enumerate(zip(frame_map, movement, trace, evidence)):
        fid = frame.get('carla_frame')
        time = frame.get('time_s')
        if (frame.get('video_frame') != index or type(fid) is not int
                or type(time) not in (int, float) or not math.isfinite(time)
                or motion.get('frame') != fid or tick.get('frame') != fid
                or item.get('original_frame') != fid
                or any(abs(source.get('time_s', float('inf')) - time) > 1e-4
                       for source in (motion, tick))):
            raise ValueError('Original Native frame/time join changed')
        if index and (fid != frame_map[index - 1]['carla_frame'] + 1
                      or abs(time - frame_map[index - 1]['time_s'] - .05) > 1e-3):
            raise ValueError('Original 20 Hz frame sequence changed')
        body(motion.get('ego_body_vertices_xy_m'))
        body(motion.get('other_body_vertices_xy_m'))
    context = read(attempt / 'divider_context.json')
    opening = Polygon(context['opening_xy_m'])
    divider = Polygon(context['dividing_space_xy_m'])
    right = Polygon(context['right_hand_roadway_xy_m'])
    destination = Polygon(context['destination_roadway_xy_m'])
    if not all(p.is_valid and p.area > 0 for p in (opening, divider, right, destination)):
        raise ValueError('Original roadway geometry invalid')
    if not divider.covers(opening):
        raise ValueError('Original opening leaves divider')
    site = read(attempt / 'site_source_receipt.json')
    barrier = read(attempt / 'barrier_receipt.json')
    if site.get('case_id') != case_id or site.get('native_map_name') != context['native_map_id']:
        raise ValueError('Site source belongs to another case or map')
    if not site.get('source_refs') or not Polygon(barrier['opening_xy_m']).equals(opening):
        raise ValueError('Opening lacks source-bound site/barrier proof')
    for ref in site['source_refs']:
        path = (attempt / ref['path']).resolve()
        if not path.is_relative_to(attempt.resolve()) or sha(path) != ref['sha256']:
            raise ValueError('Original site source changed')
    if suffix == 'left_at_established_crossover' and site.get('authority_source_ref') not in site['source_refs']:
        raise ValueError('Crossover lacks separate authority document')
    sections = [Polygon(points) for points in barrier['barrier_footprints_xy_m']]
    offsets = barrier.get('section_axis_offsets_m', [])
    if (len(sections) != 2 or len(offsets) != 2 or offsets[0] * offsets[1] >= 0
            or any(not p.is_valid or p.intersects(opening) for p in sections)):
        raise ValueError('Two separated original barrier sections required')
    ego = [body(row['ego_body_vertices_xy_m']) for row in movement]
    blocked = divider.difference(opening)
    observed = {
        'starts_on_right_hand_roadway': right.intersects(ego[0]),
        'ends_on_destination_roadway': destination.intersects(ego[-1]),
        'opening_traversed_observed': any(opening.intersects(p) for p in ego),
        'any_body_overlap_outside_opening': any(blocked.intersects(p) for p in ego),
    }
    heading = [row['ego_forward_xy'] for row in (movement[0], movement[-1])]
    for vector in heading:
        if len(vector) != 2 or not all(math.isfinite(v) for v in vector):
            raise ValueError('Missing original ego heading')
    first, last = heading
    observed['observed_turn_angle_degrees'] = math.degrees(math.atan2(
        first[0] * last[1] - first[1] * last[0],
        first[0] * last[0] + first[1] * last[1]))
    report = read(attempt / 'analysis-report.json')
    contract = read(ROOT / ('measurement-contract.json' if suffix == 'left_through_opening'
                            else f'cases/{suffix}/measurement-contract.json'))
    verified = verify_report(contract, report, attempt)
    for key, value in observed.items():
        if key in report['measurements']:
            measured = report['measurements'][key]['value']
            if measured != value and not (isinstance(value, float) and math.isclose(measured, value, abs_tol=1e-6)):
                raise ValueError('Selected measurement differs from independent source: ' + key)
    result = read(attempt / 'result.json')
    if result.get('case_id') != case_id or result.get('measured_values', {}).get('sample_count') != count:
        raise ValueError('Sealed result differs from original source count')
    for key, value in observed.items():
        measured = result['measured_values'].get(key)
        if measured != value and not (isinstance(value, float) and math.isclose(measured, value, abs_tol=1e-6)):
            raise ValueError('Sealed result differs from independent original source: ' + key)
    decoded = {}
    for name, dimensions in CAMERAS.items():
        path = attempt / (name + '.mkv')
        receipt = audit_video(path, count, mapping_sha256=sha(attempt / 'video_frames.jsonl'))
        if receipt.get('dimensions') != list(dimensions):
            raise ValueError('Original camera dimensions changed: ' + name)
        decoded[name] = sha(path)
    if not diagnostic_fixture:
        if result.get('provenance_kind') != 'native' or result.get('diagnostic_fixture') is True:
            raise ValueError('Native acquisition required for physical acceptance')
        review = read(attempt / 'independent-pixel-site-review.json')
        if (review.get('case_id') != case_id or review.get('reviewer') in (None, '', 'synthetic')
                or review.get('original_frame_count') != count
                or review.get('original_camera_sha256') != decoded
                or review.get('site_and_authority_sources_reviewed') is not True
                or review.get('maneuver_visible') is not True):
            raise ValueError('Independent original-pixel and site review incomplete')
        if result.get('physical_checks', {}).get('maneuver', {}).get('status') != 'met':
            raise ValueError('Original physical maneuver did not complete')
    return {'format': 'worker-c80909-independent-source-audit', 'case_id': case_id,
            'original_frames': count, 'original_camera_sha256': decoded,
            'original_movement_sha256': sha(attempt / 'movement_history.jsonl'),
            'verified_measurements': sorted(verified), 'independently_recomputed': observed,
            'software_audit_passed': True, 'physical_acceptance_claimed': not diagnostic_fixture,
            'legal_conclusion': 'unresolved'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--diagnostic-fixture', action='store_true')
    args = parser.parse_args()
    print(json.dumps(audit(args.attempt, args.case,
                           diagnostic_fixture=args.diagnostic_fixture), indent=2))


if __name__ == '__main__':
    main()
