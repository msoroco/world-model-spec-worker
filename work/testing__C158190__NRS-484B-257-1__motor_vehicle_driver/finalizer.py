"""Saved-only C158190 observations from reviewed original capture sources."""

import argparse
import hashlib
import json
from pathlib import Path

from yield_context import CAMERAS, derive_context
from yield_controller import PREFIX, Stage
from yield_measurements import analyze


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def measure_speed_at_closest_view(report):
    """Return the sampled original ego speed at the closest clear sight ray."""
    return report['speed_at_closest_view_mps']


def measure_sign_governance(context):
    """Report the reviewed Native sign, retaining its source scope."""
    return {'native_yield_sign_id': context['native_yield_sign_id'],
            'approach_road_id': context['approach_road_id'],
            'approach_lane_id': context['approach_lane_id'],
            'sign_governance_source': context['sign_governance_source'],
            'source_review_sha256': context['source_review_sha256']}


def measure_stopping_reference_absence(context):
    return {'reviewed_no_stop_line': context['no_stop_line'],
            'reviewed_no_near_crosswalk': context['no_near_crosswalk'],
            'marking_inventory_source': context['marking_inventory_source'],
            'source_review_sha256': context['source_review_sha256']}


def measure_control_exceptions(context):
    return {'reviewed_no_police_control': context['police_control'] is False,
            'reviewed_no_signal_control': context['traffic_signal_control'] is False,
            'source_review_sha256': context['source_review_sha256']}


def measure_slowness_before_entry(attempt, report):
    """Compare sampled approach speed with first full-body junction contact."""
    from shapely.geometry import MultiPoint, Polygon

    intersection = Polygon(json.loads((attempt/'control_context.json').read_text())
                           ['intersection_xy_m'])
    if not intersection.is_valid or intersection.area <= 0:
        raise ValueError('Invalid sourced intersection polygon')
    history = _rows(attempt/'interaction_history.jsonl')
    entry = None
    for row in history:
        points = row.get('ego', {}).get('body_vertices_m')
        if not isinstance(points, list) or len(points) < 4:
            raise ValueError('Missing original ego body vertices')
        body = MultiPoint([(point[0], point[1]) for point in points]).convex_hull
        if body.intersects(intersection):
            entry = {'frame': row['frame'], 'time_s': row['time_s']}
            break
    samples = report['approach_speed_samples']
    nearest = report['closest_sourced_visible_sample']
    at_view = next(row for row in samples if row['frame'] == nearest['frame'])
    first = samples[0]
    before_entry = entry is not None and at_view['time_s'] < entry['time_s']
    return {'first_body_entry': entry, 'closest_view_frame': nearest['frame'],
            'closest_view_before_entry': before_entry,
            'initial_sampled_speed_mps': first['ego_speed_mps'],
            'view_sampled_speed_mps': at_view['ego_speed_mps'],
            'sampled_slowness_before_entry': before_entry and
            at_view['ego_speed_mps'] < first['ego_speed_mps'],
            'legal_adequacy_assessed': False}


def measure_through_interaction(attempt):
    """Measure original body overlap and separation across the whole ego crossing."""
    from shapely.geometry import MultiPoint, Polygon

    context = json.loads((attempt/'control_context.json').read_text())
    road = json.loads((attempt/'road_context.json').read_text())
    intersection = Polygon(context['intersection_xy_m'])
    if not intersection.is_valid or intersection.area <= 0:
        raise ValueError('Invalid sourced intersection polygon')
    frames = _rows(attempt/'video_frames.jsonl')
    history = _rows(attempt/'interaction_history.jsonl')
    if len(frames) != len(history) or not history:
        raise ValueError('Original interaction and camera frame counts differ')
    through_road_ids = {158194, road['through_highway_id'], 158196}
    observed, previous_frame, previous_time = [], -1, float('-inf')
    for frame, row in zip(frames, history):
        fid, time_s = row['frame'], row['time_s']
        if (fid != frame['carla_frame'] or time_s != frame['time_s']
                or fid <= previous_frame or time_s <= previous_time):
            raise ValueError('Original interaction/camera frame join differs')
        previous_frame, previous_time = fid, time_s
        def body(state):
            points = state.get('body_vertices_m')
            if not isinstance(points, list) or len(points) < 4:
                raise ValueError('Missing original participant body vertices')
            vertices = [(float(p[0]), float(p[1])) for p in points]
            if not all(__import__('math').isfinite(v) for point in vertices for v in point):
                raise ValueError('Nonfinite original participant body')
            shape = MultiPoint(vertices).convex_hull
            if shape.is_empty or shape.area <= 0:
                raise ValueError('Degenerate original participant body')
            return shape
        ego = body(row['ego'])
        through_state = row.get('through')
        through = None if through_state is None else body(through_state)
        if through is not None and (through_state.get('road_id') not in through_road_ids
                                    or through_state.get('lane_id') != -1):
            raise ValueError('Through actor lacks sourced through-highway route')
        observed.append((fid, time_s, ego, through))
    crossing = [i for i, (_, _, ego, _) in enumerate(observed)
                if ego.intersects(intersection)]
    if not crossing:
        return {'ego_first_body_entry_frame': None,
                'ego_last_body_overlap_frame': None,
                'ego_first_full_exit_frame': None,
                'crossing_frame_count': 0, 'through_present_frame_count': 0,
                'through_intersection_entry_frame': None,
                'through_shared_intersection_frames': [],
                'body_contact_frames': [], 'minimum_body_gap_m': None,
                'immediate_hazard_judgment': 'unresolved'}
    first, last = crossing[0], crossing[-1]
    if crossing != list(range(first, last+1)):
        raise ValueError('Original ego body leaves and reenters intersection')
    inside = observed[first:last+1]
    contact = [fid for fid, _, ego, through in inside
               if through is not None and ego.intersects(through)]
    shared = [fid for fid, _, _, through in inside
              if through is not None and through.intersects(intersection)]
    gaps = [ego.distance(through) for _, _, ego, through in inside if through is not None]
    through_entries = [fid for fid, _, _, through in observed
                       if through is not None and through.intersects(intersection)]
    return {'ego_first_body_entry_frame': observed[first][0],
            'ego_last_body_overlap_frame': observed[last][0],
            'ego_first_full_exit_frame': observed[last+1][0] if last+1 < len(observed) else None,
            'crossing_frame_count': len(inside),
            'through_present_frame_count': len(gaps),
            'through_intersection_entry_frame': through_entries[0] if through_entries else None,
            'through_shared_intersection_frames': shared,
            'body_contact_frames': contact,
            'minimum_body_gap_m': min(gaps) if gaps else None,
            'immediate_hazard_judgment': 'unresolved'}


def measure_yield_relation(interaction, slowness):
    """Retain observed timing and gap without imposing a legal cutoff."""
    return {'sampled_slowness_before_entry': slowness['sampled_slowness_before_entry'],
            'ego_first_body_entry_frame': interaction['ego_first_body_entry_frame'],
            'through_intersection_entry_frame': interaction['through_intersection_entry_frame'],
            'through_shared_intersection_frames': interaction['through_shared_intersection_frames'],
            'body_contact_frames': interaction['body_contact_frames'],
            'minimum_body_gap_m': interaction['minimum_body_gap_m'],
            'yield_judgment': 'unresolved', 'legal_adequacy_assessed': False}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists() or (attempt / 'channels').exists():
        raise ValueError('Retain prior C158190 finalization; choose a fresh attempt')
    required = ('config.json', 'road.xodr', 'road_context.json',
                'control_inventory.jsonl', 'approach_history.jsonl',
                'interaction_history.jsonl', 'control_context.json',
                'visibility_rays.jsonl', 'visibility_samples.json',
                'video_frames.jsonl', 'trace.jsonl', 'capture/evidence.jsonl',
                'capture/native_map_facts.json', 'rendered_marking_review.json', *CAMERAS)
    for name in required:
        if not (attempt / name).is_file():
            raise ValueError('Missing required source: ' + name)
    config = json.loads((attempt / 'config.json').read_text())
    case_id = config.get('selected_case_id')
    stage = Stage(case_id)
    if not case_id.startswith(PREFIX):
        raise ValueError('Wrong exact C158190 case')
    context = derive_context(attempt)
    report = analyze(attempt, reviewed_context=context)
    history = _rows(attempt / 'approach_history.jsonl')
    rays = _rows(attempt / 'visibility_rays.jsonl')
    by_frame = {row['frame']: row for row in rays}
    if len(history) != len(rays) or len(by_frame) != len(rays):
        raise ValueError('Approach and original sight rays differ')
    channels = attempt / 'channels'
    channels.mkdir()
    values = {'ego_approach_speed': [row['ego_speed_mps'] for row in history],
              'through_highway_sight_clear': [int(by_frame[row['frame']]['clear'])
                                              for row in history]}
    for name, numbers in values.items():
        with (channels / (name + '.jsonl')).open('x') as stream:
            for row, number in zip(history, numbers):
                stream.write(json.dumps({'original_frame': row['frame'],
                                         'time_s': row['time_s'], 'value': number},
                                        allow_nan=False) + '\n')
    site_review = {'yield_site_review': {
        'authored_site_sha256': context['authored_site_sha256'],
        'source_review_sha256': context['source_review_sha256'],
        'native_yield_sign_id': context['native_yield_sign_id'],
        'native_map_id': context['native_map_id'],
        'review_scope': 'original camera frames named in rendered_marking_review.json',
        'physical_acceptance': False}}
    (channels / 'yield_site_review.json').write_text(json.dumps(site_review, indent=2) + '\n')
    measured = measure_speed_at_closest_view(report)
    requested = (stage.approach_speed_mps if case_id.endswith('__yield_nearest_view_no_slow')
                 else stage.clear_speed_mps if case_id.endswith('__yield_nearest_view_clear')
                 else stage.view_speed_mps)
    target = {'target': 'sampled_ego_speed_at_closest_sourced_through_road_view_mps',
              'requested': requested, 'measured': measured,
              'method': 'original ego velocity at closest sampled clear through-road ray',
              'tolerance': 1.0, 'matched': abs(requested - measured) <= 1.0,
              'physical_cause_confirmed': False,
              'cause_evidence': ['approach_history.jsonl', 'visibility_rays.jsonl',
                                 'video_frames.jsonl', 'rendered_marking_review.json']}
    evidence = [{'name': name, 'unit': ('m/s' if name == 'ego_approach_speed' else 'count'),
                 'reference': 'channels/' + name + '.jsonl'} for name in values]
    evidence.append({'name': 'yield_site_review', 'unit': 'structured record',
                     'reference': 'channels/yield_site_review.json'})
    result = {'case_id': case_id,
              'measured_values': {'speed_at_closest_view_mps': measured,
                                  'closest_sourced_visible_sample': report['closest_sourced_visible_sample'],
                                  'minimum_observed_approach_speed_mps': report['minimum_observed_approach_speed_mps']},
              'target_checks': [target],
              'setup_confirmed': False, 'behavior_attempted': False,
              'maneuver_completed': False,
              'termination_reason': 'saved source analysis; independent physical audit pending',
              'physical_failure_flags': ['actual sign face, full marking absence, human view, immediate hazard and yielding remain physical/legal review'],
              'trace_reference': 'trace.jsonl',
              'video_references': list(CAMERAS),
              'video_frame_map_reference': 'video_frames.jsonl',
              'recording_description': config['recording_description'],
              'recording_evidence': evidence,
              'source_evidence_hashes': {**report['sources'],
                                         'road.xodr': _sha(attempt/'road.xodr'),
                                         'control_inventory.jsonl': _sha(attempt/'control_inventory.jsonl'),
                                         'interaction_history.jsonl': _sha(attempt/'interaction_history.jsonl'),
                                         'control_context.json': _sha(attempt/'control_context.json'),
                                         'rendered_marking_review.json': _sha(attempt/'rendered_marking_review.json')},
              'capture_evidence_sha256': _sha(attempt/'capture/evidence.jsonl'),
              'realized_observables': {}}
    try:
        from worker_exchange.native_output import physical_result, write_result
    except ModuleNotFoundError:
        import sys
        sys.path.insert(0, str(Path(__file__).resolve().parents[2] /
                               'runtime/scenario_pipeline'))
        from worker_exchange.native_output import physical_result, write_result
    result = physical_result(attempt, result)
    context_sources = {name: _sha(attempt/name) for name in
                       ('road.xodr', 'road_context.json', 'control_inventory.jsonl',
                        'capture/native_map_facts.json', 'rendered_marking_review.json',
                        'video_frames.jsonl', *CAMERAS)}
    interaction = measure_through_interaction(attempt)
    slowness = measure_slowness_before_entry(attempt, report)
    interaction_sources = {name: _sha(attempt/name) for name in
                           ('interaction_history.jsonl', 'control_context.json',
                            'road_context.json', 'video_frames.jsonl')}
    analysis = {'format': 'worker-c158190-yield-analysis', 'case_id': case_id,
                'measurements': {'speed_at_closest_view_mps': {
                    'value': measured, 'method': 'measure_speed_at_closest_view',
                    'sources': result['source_evidence_hashes']},
                    'sign_governance': {'value': measure_sign_governance(context),
                                        'method': 'measure_sign_governance',
                                        'sources': context_sources},
                    'stopping_reference_absence': {
                        'value': measure_stopping_reference_absence(context),
                        'method': 'measure_stopping_reference_absence',
                        'sources': context_sources},
                    'control_exceptions': {'value': measure_control_exceptions(context),
                                           'method': 'measure_control_exceptions',
                                           'sources': context_sources},
                    'slowness_before_entry': {
                        'value': slowness,
                        'method': 'measure_slowness_before_entry',
                        'sources': {name: _sha(attempt/name) for name in
                                    ('interaction_history.jsonl', 'control_context.json',
                                     'approach_history.jsonl', 'visibility_samples.json',
                                     'visibility_rays.jsonl', 'video_frames.jsonl',
                                     'road_context.json')}},
                    'through_interaction': {
                        'value': interaction, 'method': 'measure_through_interaction',
                        'sources': interaction_sources},
                    'yield_relation': {
                        'value': measure_yield_relation(interaction, slowness),
                        'method': 'measure_yield_relation',
                        'sources': {name: _sha(attempt/name) for name in
                                    ('interaction_history.jsonl', 'control_context.json',
                                     'road_context.json', 'video_frames.jsonl',
                                     'approach_history.jsonl', 'visibility_samples.json',
                                     'visibility_rays.jsonl')}}},
                'legal_conclusion': 'unresolved', 'source_report': report,
                'source_review_sha256': context['source_review_sha256']}
    write_result(attempt, result)
    output.write_text(json.dumps(analysis, indent=2, allow_nan=False) + '\n')
    return analysis


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    finalize(Path(args.attempt), Path(args.output))


if __name__ == '__main__':
    main()
