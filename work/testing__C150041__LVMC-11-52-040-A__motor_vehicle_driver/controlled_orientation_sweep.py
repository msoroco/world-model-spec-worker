"""Build source-gated engineering orientation probes without legal labels."""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
from pathlib import Path

from parking_measurement import inside, measure_sequence, unit, vector
from parking_pose import body
from parking_site_acquisition import validate as validate_site
from parking_scene import build as build_scene


ANGLE_REQUESTS = tuple(range(0, 91, 10))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def target(context, angle_deg, *, activity='park', segment_index=0,
           edge_offset_m=2.5, length_m=4.5, width_m=2.0):
    """Require a reviewed road and return one requested full-body pose."""
    if activity not in ('park', 'stand'):
        raise ValueError('sweep activity must be park or stand')
    if angle_deg not in ANGLE_REQUESTS:
        raise ValueError('angle must be a frozen engineering sweep point')
    if not isinstance(segment_index, int) or segment_index < 0:
        raise ValueError('road edge segment index invalid')
    edge = context['road_edge_xy_m']
    if segment_index + 1 >= len(edge):
        raise ValueError('road edge segment missing')
    start, end = edge[segment_index:segment_index + 2]
    tangent = unit(vector(start, end))
    lawful = unit(context['lawful_travel_xy'])
    if abs(sum(tangent[i] * lawful[i] for i in (0, 1))) < .9:
        raise ValueError('lawful direction conflicts with roadway edge')
    if not math.isfinite(edge_offset_m) or edge_offset_m <= 0:
        raise ValueError('edge offset must be positive')
    anchor = tuple((start[i] + end[i]) / 2 for i in (0, 1))
    normals = ((-tangent[1], tangent[0]), (tangent[1], -tangent[0]))
    choices = [tuple(anchor[i] + edge_offset_m * normal[i] for i in (0, 1))
               for normal in normals]
    choices = [center for center in choices if inside(center, context['roadway_polygon_xy_m'])]
    if len(choices) != 1:
        raise ValueError('reviewed road does not identify one inward side')
    center = choices[0]
    inward = unit(vector(anchor, center))
    radians = math.radians(angle_deg)
    forward = unit(tuple(math.cos(radians) * lawful[i] +
                         math.sin(radians) * inward[i] for i in (0, 1)))
    corners = body(center, forward, length_m=length_m, width_m=width_m)
    if not all(inside(point, context['roadway_polygon_xy_m']) for point in corners):
        raise ValueError('sweep full-body footprint leaves reviewed roadway')
    return {'activity_request': activity, 'orientation_request_deg': angle_deg,
            'heading_request': 'lawful', 'target_center_xy_m': center,
            'target_forward_xy': forward, 'target_body_vertices_xy_m': corners,
            'source_packet_sha256': context['reviewed_packet_sha256'],
            'lawful_direction_source': context['lawful_direction_source'],
            'physical_realization_claimed': False, 'legal_judgment': 'unresolved'}


def build(packet, source_root, output, *, activity='park'):
    packet = Path(packet)
    context = validate_site(packet, source_root=source_root, require_reviewed=True)
    rows = []
    for rank, angle in enumerate(ANGLE_REQUESTS):
        suffix = f'orientation_sweep-{rank:04d}'
        scene = build_scene(packet, source_root, suffix) if activity == 'park' else None
        pose = target(context, angle, activity=activity)
        if scene is not None:
            scene['sweep_id'] = 'parallel_orientation_source_gated'
            scene['selection_rank'] = rank
            scene['engineering_angle_request_deg'] = angle
            scene['legal_judgment'] = 'unresolved'
        rows.append({'angle_deg': angle, 'pose': pose, 'scene': scene})
    result = {'format': 'c150041-controlled-orientation-sweep-v1',
              'activity': activity, 'site_packet': str(packet),
              'site_packet_sha256': sha(packet), 'source_reviewed': True,
              'engineering_angles_deg': list(ANGLE_REQUESTS), 'constructions': rows,
              'legal_judgment': 'unresolved', 'physical_realization_claimed': False,
              'limitations': ['Original Native motion and pixels are unverified.',
                              'Engineering angles are not statutory thresholds.']}
    Path(output).write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    return result


def measure_original(packet, source_root, history_path, expected_sha256):
    """Measure retained original body samples against the same reviewed road."""
    context = validate_site(packet, source_root=source_root, require_reviewed=True)
    history_path = Path(history_path)
    if sha(history_path) != expected_sha256:
        raise ValueError('original sweep body history hash changed')
    frames = [json.loads(line) for line in history_path.read_text().splitlines()
              if line.strip()]
    measured = measure_sequence(frames, context)
    return {'format': 'c150041-orientation-measurement-v1',
            'site_packet_sha256': sha(packet),
            'original_history_sha256': expected_sha256,
            'observations': measured['frames'],
            'legal_judgment': 'unresolved',
            'physical_acceptance_claimed': False}


def expand_canonical_plan(proposal):
    """Use the pinned sweep expander for the ten engineering request points."""
    from scenario_pipeline.batch_pipeline.sweeps import expand_sweeps
    result = copy.deepcopy(proposal)
    if len(result.get('sweep_specs', [])) != 1:
        raise ValueError('one exact parallel-orientation sweep required')
    spec = result['sweep_specs'][0]
    if spec.get('status') != 'incomplete' or len(spec.get('axes', [])) != 1:
        raise ValueError('unexpected existing sweep plan')
    spec['status'] = 'complete'
    spec['sweep_id'] = 'testing__C150041__LVMC-11-52-040-A__motor_vehicle_driver__orientation_sweep'
    spec.pop('missing_inputs', None)
    spec['rationale'] = ('Fixed 0..90 degree engineering requests on one source-reviewed '
                         'roadway; actual Native pose and legal judgment remain unresolved.')
    spec['variable_assignments']['orientation_request_deg'] = {
        'kind': 'controller', 'value': 0,
        'note': 'Engineering request only; original body angle is measured separately'}
    expand_sweeps(result)
    expanded = [case for case in result['cases']
                if case.get('target_type') == 'judgment_sweep']
    if len(expanded) != len(ANGLE_REQUESTS):
        raise ValueError('canonical sweep point count differs')
    if {case['sweep_point']['orientation_request_deg'] for case in expanded} != set(ANGLE_REQUESTS):
        raise ValueError('canonical sweep points differ')
    result['source_review_required'] = True
    result['delivery_status'] = 'source_gated_cpu_plan'
    result['physical_realization_claimed'] = False
    result['legal_judgment'] = 'unresolved'
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--packet', required=True)
    parser.add_argument('--source-root', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--activity', choices=('park', 'stand'), default='park')
    args = parser.parse_args()
    build(args.packet, args.source_root, args.output, activity=args.activity)


if __name__ == '__main__':
    main()
