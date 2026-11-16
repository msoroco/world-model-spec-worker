"""Independent source comparison for the two no-crosswalk stopping references.

This checks the diagnostic fixed conditions and deliberate reference change.
It makes no claim about a physically erected sign or legally sufficient view.
"""
import hashlib
import json
import math
import xml.etree.ElementTree as ET
from pathlib import Path

from stop_reference_measurements import analyze
from delivery_audit import audit as audit_delivery

CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')
FIXED = ('native_map_id', 'intersection_id', 'approach_road_id',
         'approach_lane_id', 'native_stop_sign_id', 'intersection_polygon_xy_m',
         'approach_forward_xy', 'near_side_crosswalk_exists')

# Each pair names a declared physical change. Separate Native recordings need
# not have identical encoded pixels, frame numbers, or braking trajectories.
RECORDED_PAIRS = {
    'halt_position': ('marked_crosswalk_stop_before', 'marked_crosswalk_stop_inside',
                      {'full_halt_location'}),
    'crosswalk_origin': ('marked_crosswalk_stop_before', 'unmarked_crosswalk_stop_before',
                         {'crosswalk_origin'}),
    'reference_precedence': ('marked_crosswalk_stop_before', 'crosswalk_and_stop_line',
                             {'stop_line_exists'}),
    'stop_line_hierarchy': ('marked_crosswalk_stop_before', 'no_crosswalk_marked_stop_line',
                            {'near_side_crosswalk_exists', 'crosswalk_origin', 'stop_line_exists'}),
    'sight_point_hierarchy': ('marked_crosswalk_stop_before', 'no_crosswalk_no_line_first_view',
                              {'near_side_crosswalk_exists', 'crosswalk_origin'}),
    'stop_line_vs_first_view': ('no_crosswalk_marked_stop_line', 'no_crosswalk_no_line_first_view',
                                {'stop_line_exists'}),
}


def compare_recorded(comparison_id, left_root, right_root, diagnostic=False,
                     left_pixel_review=None, right_pixel_review=None):
    """Audit each saved attempt, then test shared context and declared branch change.

    Native mode delegates the independent pixel, lifecycle and physical checks
    to delivery_audit. Diagnostic mode proves only the software comparison path.
    """
    if comparison_id not in RECORDED_PAIRS:
        raise ValueError('Unknown exact comparison')
    left_suffix, right_suffix, differences = RECORDED_PAIRS[comparison_id]
    roots = [Path(left_root).resolve(), Path(right_root).resolve()]
    receipts = []
    for suffix, root, review in zip((left_suffix, right_suffix), roots,
                                    (left_pixel_review, right_pixel_review)):
        case_id = 'testing__C331230__NRS-484A-450-2__motor_vehicle_driver__' + suffix
        receipts.append(audit_delivery(case_id, root, diagnostic=diagnostic,
                                       pixel_review=review))
    contexts = [json.loads((root / 'approach_context.json').read_text()) for root in roots]
    shared = ('native_map_id', 'intersection_id', 'approach_road_id',
              'approach_lane_id', 'native_stop_sign_id',
              'intersection_polygon_xy_m', 'approach_forward_xy')
    for key in shared:
        if key not in contexts[0] or contexts[0][key] != contexts[1].get(key):
            raise ValueError('Fixed source condition differs: ' + key)
    for key in ('near_side_crosswalk_exists', 'crosswalk_origin', 'stop_line_exists'):
        if key not in differences and contexts[0].get(key) != contexts[1].get(key):
            raise ValueError('Undeclared source condition differs: ' + key)
    if comparison_id == 'halt_position':
        if (contexts[0].get('near_side_crosswalk_exists') is not True or
                contexts[0].get('crosswalk_origin') != 'marked'):
            raise ValueError('Halt comparison lost marked crossing')
    elif comparison_id == 'crosswalk_origin':
        if [c.get('crosswalk_origin') for c in contexts] != ['marked', 'sidewalk_connection']:
            raise ValueError('Declared crosswalk origin change absent')
        if contexts[0].get('crosswalk_polygon_xy_m') != contexts[1].get('crosswalk_polygon_xy_m'):
            raise ValueError('Fixed crosswalk geometry differs')
    elif comparison_id == 'reference_precedence':
        if [c.get('stop_line_exists') for c in contexts] != [False, True]:
            raise ValueError('Declared additional stop line absent')
        if contexts[0].get('crosswalk_polygon_xy_m') != contexts[1].get('crosswalk_polygon_xy_m'):
            raise ValueError('Fixed crosswalk geometry differs')
    elif comparison_id == 'stop_line_hierarchy':
        if [(c.get('near_side_crosswalk_exists'), c.get('stop_line_exists')) for c in contexts] != [(True, False), (False, True)]:
            raise ValueError('Declared crosswalk versus line change absent')
    elif comparison_id == 'sight_point_hierarchy':
        if [(c.get('near_side_crosswalk_exists'), c.get('stop_line_exists')) for c in contexts] != [(True, False), (False, False)]:
            raise ValueError('Declared crosswalk versus view change absent')
    else:
        if [(c.get('near_side_crosswalk_exists'), c.get('stop_line_exists')) for c in contexts] != [(False, True), (False, False)]:
            raise ValueError('Declared line versus view change absent')
    # The saved attempt retains a site packet, not an OpenDRIVE export. The
    # source-bound capture context must agree with that exact selected packet.
    for root, context in zip(roots, contexts):
        config = json.loads((root / 'config.json').read_text())
        packet = config.get('site_packet', {})
        site_path = root / packet.get('path', '')
        if not site_path.is_file() or digest(site_path) != packet.get('sha256'):
            raise ValueError('Saved site packet missing or stale')
        site = json.loads(site_path.read_text())
        for key in ('intersection_id', 'approach_road_id', 'approach_lane_id',
                    'near_side_crosswalk_exists', 'crosswalk_origin',
                    'crosswalk_polygon_xy_m', 'intersection_polygon_xy_m',
                    'stop_line_exists'):
            if key in site and site[key] != context.get(key):
                raise ValueError('Saved site/context differs: ' + key)
    reports = [json.loads((root / 'analysis-report.json').read_text()) for root in roots]
    selected = []
    for report in reports:
        values = [measurement['value'] for measurement in report['measurements'].values()
                  if isinstance(measurement.get('value'), dict) and 'selected_reference' in measurement['value']]
        if len(values) != 1:
            raise ValueError('Selected reference measurement missing or ambiguous')
        selected.append(values[0])
    expected = {
        'halt_position': ('near_side_crosswalk', 'near_side_crosswalk'),
        'crosswalk_origin': ('near_side_crosswalk', 'near_side_crosswalk'),
        'reference_precedence': ('near_side_crosswalk', 'near_side_crosswalk'),
        'stop_line_hierarchy': ('near_side_crosswalk', 'marked_stop_line'),
        'sight_point_hierarchy': ('near_side_crosswalk', 'first_observed_view'),
        'stop_line_vs_first_view': ('marked_stop_line', 'first_observed_view'),
    }[comparison_id]
    if tuple(value['selected_reference'] for value in selected) != expected:
        raise ValueError('Measured stopping-reference selection differs')
    histories = [[json.loads(line) for line in (root / 'stop_history.jsonl').read_text().splitlines()
                  if line.strip()] for root in roots]
    halts = [next((row for row in history if row.get('ego_speed_mps') == 0), None)
             for history in histories]
    if not all(halts):
        raise ValueError('Original complete-body halt missing')
    centers = []
    for halt in halts:
        vertices = halt.get('ego_body_vertices_xy_m')
        if not isinstance(vertices, list) or len(vertices) != 4:
            raise ValueError('Original complete-body geometry missing at halt')
        centers.append((sum(float(v[0]) for v in vertices) / 4,
                        sum(float(v[1]) for v in vertices) / 4))
    halt_separation_m = math.dist(*centers)
    if comparison_id == 'halt_position':
        before = selected[0].get('halt_before_crosswalk_and_junction_observed')
        after = selected[1].get('halt_before_crosswalk_and_junction_observed')
        if before is not True or after is not False or halt_separation_m < .5:
            raise ValueError('Declared halt-order difference absent')
    elif halt_separation_m > .5:
        raise ValueError('Fixed complete-body halt location differs by more than 0.5 m')
    return {'format': 'worker-c331230-recorded-comparison',
            'comparison_id': comparison_id,
            'case_ids': [receipt['case_id'] for receipt in receipts],
            'source_sha256': [{name: digest(root / name) for name in
                               ('approach_context.json', 'site.json', 'stop_history.jsonl',
                                'analysis-report.json', 'capture/evidence.jsonl')}
                              for root in roots],
            'selected_references': list(expected),
            'first_halt_center_xy_m': centers,
            'halt_center_separation_m': halt_separation_m,
            'fixed_halt_tolerance_m': None if comparison_id == 'halt_position' else .5,
            'fixed_conditions_checked': list(shared),
            'declared_differences': sorted(differences),
            'diagnostic_only': diagnostic,
            'software_checks_passed': True,
            'physical_completion_verified': all(r['physical_completion_verified'] for r in receipts),
            'actual_pixels_verified': all(r['actual_pixels_verified'] for r in receipts),
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _painted(root):
    road = Path(root) / 'road.xodr'
    if not road.is_file():
        raise ValueError('Missing source OpenDRIVE map')
    source = ET.parse(road).getroot()
    crosswalks = source.findall(".//object[@type='crosswalk']")
    lines = [obj for obj in source.findall('.//object')
             if obj.get('name') == 'StopLine' or obj.get('type') == 'StopLine']
    return lines, crosswalks, digest(road)


def compare(line_root, view_root):
    line_root, view_root = Path(line_root), Path(view_root)
    contexts = [json.loads((root / 'approach_context.json').read_text())
                for root in (line_root, view_root)]
    line_ctx, view_ctx = contexts
    for key in FIXED:
        if line_ctx.get(key) != view_ctx.get(key):
            raise ValueError('Fixed source condition differs: ' + key)
    if line_ctx['near_side_crosswalk_exists'] is not False:
        raise ValueError('No-crosswalk comparison requires sourced absence')
    if line_ctx.get('stop_line_exists') is not True or view_ctx.get('stop_line_exists') is not False:
        raise ValueError('Deliberate stop-line presence difference missing')
    line_objects, line_crosswalks, line_map = _painted(line_root)
    view_objects, view_crosswalks, view_map = _painted(view_root)
    if len(line_objects) != 1 or view_objects or line_crosswalks or view_crosswalks:
        raise ValueError('OpenDRIVE marking inventory differs from selected reference')
    obj = line_objects[0]
    if (not math.isclose(float(obj.attrib['s']), line_ctx['stop_line_segment_xy_m'][0][0], abs_tol=1e-6) or
        not math.isclose(float(obj.attrib['length']),
                         abs(line_ctx['stop_line_segment_xy_m'][1][1] - line_ctx['stop_line_segment_xy_m'][0][1]), abs_tol=1e-6)):
        raise ValueError('Source StopLine object and measured segment differ')
    fixed_sources = ('stop_history.jsonl', 'video_frames.jsonl', *CAMERAS)
    for name in fixed_sources:
        if digest(line_root / name) != digest(view_root / name):
            raise ValueError('Fixed source differs: ' + name)
    line, view = analyze(line_root), analyze(view_root)
    if (line['selected_reference'] != 'marked_stop_line' or
        view['selected_reference'] != 'first_observed_view' or
        not line['halt_before_reference_and_junction_observed'] or
        not view['halt_before_reference_and_junction_observed']):
        raise ValueError('Selected reference observations do not support comparison')
    if line['first_full_halt'] != view['first_full_halt'] or line['first_intersection_entry'] != view['first_intersection_entry']:
        raise ValueError('Fixed halt or junction entry differs')
    return {'format': 'worker-stop-reference-comparison',
            'comparison_id': 'stop_line_vs_first_view',
            'fixed_source_sha256': {name: digest(line_root / name) for name in fixed_sources},
            'map_sha256': {'marked_line': line_map, 'first_view': view_map},
            'marked_line_reference': line['first_reference'],
            'first_observed_view': view['first_observed_view'],
            'same_halt': line['first_full_halt'],
            'same_junction_entry': line['first_intersection_entry'],
            'diagnostic_comparison_passed': True,
            'physical_acceptance_claimed': False,
            'legal_acceptance_claimed': False}


def compare_crosswalk_priority(crosswalk_root, both_root):
    """Check that adding a downstream line leaves the crosswalk reference fixed."""
    crosswalk_root, both_root = Path(crosswalk_root), Path(both_root)
    contexts = [json.loads((root / 'approach_context.json').read_text())
                for root in (crosswalk_root, both_root)]
    before, both = contexts
    fixed = ('native_map_id', 'intersection_id', 'approach_road_id',
             'approach_lane_id', 'native_stop_sign_id', 'crosswalk_polygon_xy_m',
             'intersection_polygon_xy_m', 'approach_forward_xy')
    for key in fixed:
        if before.get(key) != both.get(key):
            raise ValueError('Fixed source condition differs: ' + key)
    if before.get('stop_line_exists') is not False or both.get('stop_line_exists') is not True:
        raise ValueError('Deliberate stop-line presence difference missing')
    before_lines, before_crosswalks, before_map = _painted(crosswalk_root)
    both_lines, both_crosswalks, both_map = _painted(both_root)
    if before_lines or len(before_crosswalks) != 1 or len(both_lines) != 1 or len(both_crosswalks) != 1:
        raise ValueError('OpenDRIVE reference inventory differs')
    if float(both_lines[0].attrib['s']) <= float(both_crosswalks[0].attrib['s']):
        raise ValueError('Marked line is not downstream of crosswalk')
    sources = ('stop_history.jsonl', 'video_frames.jsonl', *CAMERAS)
    for name in sources:
        if digest(crosswalk_root / name) != digest(both_root / name):
            raise ValueError('Fixed source differs: ' + name)
    reports = [json.loads((root / 'analysis-report.json').read_text()) for root in (crosswalk_root, both_root)]
    values = [r['measurements']['crosswalk_halt_observation']['value'] for r in reports]
    for value in values:
        if value['selected_reference'] != 'near_side_crosswalk' or not value['halt_before_crosswalk_and_junction_observed']:
            raise ValueError('Crosswalk selection or halt ordering failed')
    for key in ('first_full_halt', 'first_crosswalk_entry', 'first_intersection_entry'):
        if values[0][key] != values[1][key]:
            raise ValueError('Fixed event differs: ' + key)
    if values[1].get('stop_line_present_but_lower_priority') is not True:
        raise ValueError('Downstream line precedence was not recorded')
    return {'format': 'worker-crosswalk-priority-comparison',
            'fixed_source_sha256': {name: digest(crosswalk_root / name) for name in sources},
            'map_sha256': {'crosswalk_only': before_map, 'crosswalk_and_line': both_map},
            'selected_reference': 'near_side_crosswalk',
            'diagnostic_comparison_passed': True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def compare_marked_unmarked(marked_root, unmarked_root):
    """Check the exact origin change while holding signed approach and motion fixed."""
    marked_root, unmarked_root = Path(marked_root), Path(unmarked_root)
    marked = json.loads((marked_root / 'approach_context.json').read_text())
    unmarked = json.loads((unmarked_root / 'approach_context.json').read_text())
    fixed = ('native_map_id', 'intersection_id', 'approach_road_id',
             'approach_lane_id', 'native_stop_sign_id', 'crosswalk_polygon_xy_m',
             'intersection_polygon_xy_m', 'approach_forward_xy', 'stop_line_exists')
    for key in fixed:
        if marked.get(key) != unmarked.get(key):
            raise ValueError('Fixed source condition differs: ' + key)
    if (marked.get('crosswalk_origin'), unmarked.get('crosswalk_origin')) != ('marked', 'sidewalk_connection'):
        raise ValueError('Deliberate marked versus sidewalk origin differs')
    marked_lines, marked_crosswalks, marked_map = _painted(marked_root)
    unmarked_lines, unmarked_crosswalks, unmarked_map = _painted(unmarked_root)
    if marked_lines or unmarked_lines or len(marked_crosswalks) != 1 or unmarked_crosswalks:
        raise ValueError('Marked versus unmarked OpenDRIVE inventory differs')
    road = ET.parse(unmarked_root / 'road.xodr').getroot()
    if len(road.findall(".//lane[@type='sidewalk']")) < 2:
        raise ValueError('Opposed sidewalk lane sources missing')
    sources = ('stop_history.jsonl', 'video_frames.jsonl', *CAMERAS)
    for name in sources:
        if digest(marked_root / name) != digest(unmarked_root / name):
            raise ValueError('Fixed source differs: ' + name)
    values = [json.loads((root / 'analysis-report.json').read_text())['measurements']['crosswalk_halt_observation']['value']
              for root in (marked_root, unmarked_root)]
    if values[0] != values[1] or values[0]['selected_reference'] != 'near_side_crosswalk' or not values[0]['halt_before_crosswalk_and_junction_observed']:
        raise ValueError('Fixed halt and crosswalk ordering differ')
    return {'format': 'worker-marked-unmarked-comparison',
            'fixed_source_sha256': {name: digest(marked_root / name) for name in sources},
            'map_sha256': {'marked': marked_map, 'unmarked': unmarked_map},
            'diagnostic_comparison_passed': True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def compare_halt_position(before_root, inside_root):
    """Hold the signed crossing and body path fixed while changing halt timing."""
    before_root, inside_root = Path(before_root), Path(inside_root)
    contexts = [json.loads((root / 'approach_context.json').read_text())
                for root in (before_root, inside_root)]
    fixed = ('native_map_id', 'intersection_id', 'approach_road_id',
             'approach_lane_id', 'native_stop_sign_id', 'crosswalk_polygon_xy_m',
             'intersection_polygon_xy_m', 'approach_forward_xy',
             'near_side_crosswalk_exists', 'crosswalk_origin', 'stop_line_exists')
    for key in fixed:
        if contexts[0].get(key) != contexts[1].get(key):
            raise ValueError('Fixed source condition differs: ' + key)
    if (contexts[0]['near_side_crosswalk_exists'] is not True or
            contexts[0]['crosswalk_origin'] != 'marked' or
            contexts[0]['stop_line_exists'] is not False):
        raise ValueError('Halt-position comparison requires the marked crossing')
    fixed_sources = ('road.xodr', 'video_frames.jsonl', *CAMERAS)
    for name in fixed_sources:
        if digest(before_root / name) != digest(inside_root / name):
            raise ValueError('Fixed source differs: ' + name)
    histories = [[json.loads(line) for line in (root / 'stop_history.jsonl').read_text().splitlines()]
                 for root in (before_root, inside_root)]
    if len(histories[0]) != len(histories[1]) or not histories[0]:
        raise ValueError('Original halt histories have different frame counts')
    for a, b in zip(*histories):
        if {k: v for k, v in a.items() if k != 'ego_speed_mps'} != {
                k: v for k, v in b.items() if k != 'ego_speed_mps'}:
            raise ValueError('Fixed body path or frame join differs')
    crossing_x = min(x for x, _ in contexts[0]['crosswalk_polygon_xy_m'])
    entry = next((row['frame'] for row in histories[0]
                  if max(x for x, _ in row['ego_body_vertices_xy_m']) >= crossing_x), None)
    halts = [next((row['frame'] for row in rows if row['ego_speed_mps'] == 0), None)
             for rows in histories]
    if entry is None or halts[0] is None or halts[1] is None or not (halts[0] < entry <= halts[1]):
        raise ValueError('Deliberate before versus inside halt timing missing')
    return {'format': 'worker-halt-position-comparison',
            'comparison_id': 'halt_position', 'crosswalk_entry_frame': entry,
            'before_halt_frame': halts[0], 'inside_halt_frame': halts[1],
            'fixed_source_sha256': {name: digest(before_root / name) for name in fixed_sources},
            'diagnostic_comparison_passed': True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def compare_crosswalk_to_line(crosswalk_root, line_root):
    """Check selected-reference hierarchy with signed halt behavior fixed."""
    crosswalk_root, line_root = Path(crosswalk_root), Path(line_root)
    contexts = [json.loads((root / 'approach_context.json').read_text())
                for root in (crosswalk_root, line_root)]
    cross, line = contexts
    fixed = ('native_map_id', 'intersection_id', 'approach_road_id',
             'approach_lane_id', 'native_stop_sign_id',
             'intersection_polygon_xy_m', 'approach_forward_xy')
    for key in fixed:
        if cross.get(key) != line.get(key):
            raise ValueError('Fixed source condition differs: ' + key)
    if ((cross.get('near_side_crosswalk_exists'), cross.get('stop_line_exists')) != (True, False)
            or (line.get('near_side_crosswalk_exists'), line.get('stop_line_exists')) != (False, True)):
        raise ValueError('Deliberate crosswalk versus marked-line source change missing')
    cross_lines, cross_walks, cross_map = _painted(crosswalk_root)
    line_lines, line_walks, line_map = _painted(line_root)
    if cross_lines or len(cross_walks) != 1 or len(line_lines) != 1 or line_walks:
        raise ValueError('OpenDRIVE reference inventory differs')
    fixed_sources = ('video_frames.jsonl', *CAMERAS)
    for name in fixed_sources:
        if digest(crosswalk_root / name) != digest(line_root / name):
            raise ValueError('Fixed source differs: ' + name)
    histories = [[json.loads(row) for row in (root / 'stop_history.jsonl').read_text().splitlines()]
                 for root in (crosswalk_root, line_root)]
    if len(histories[0]) != len(histories[1]) or not histories[0]:
        raise ValueError('Original halt histories have different frame counts')
    for a, b in zip(*histories):
        for key in ('frame', 'time_s', 'road_id', 'lane_id', 'stop_sign_id', 'ego_speed_mps'):
            if a.get(key) != b.get(key):
                raise ValueError('Fixed signed halt behavior differs: ' + key)
    halts = [[row for row in rows if row['ego_speed_mps'] == 0] for rows in histories]
    if not halts[0] or not halts[1] or halts[0][0]['ego_body_vertices_xy_m'] != halts[1][0]['ego_body_vertices_xy_m']:
        raise ValueError('Fixed complete-body halt location differs')
    reports = [json.loads((root / 'analysis-report.json').read_text())['measurements']
               for root in (crosswalk_root, line_root)]
    cross_value = reports[0]['crosswalk_halt_observation']['value']
    line_value = reports[1]['stop_line_halt_observation']['value']
    if (cross_value['selected_reference'] != 'near_side_crosswalk' or
            line_value['selected_reference'] != 'marked_stop_line' or
            not cross_value['halt_before_crosswalk_and_junction_observed'] or
            not line_value['halt_before_reference_and_junction_observed']):
        raise ValueError('Selected stopping-reference observations differ')
    return {'format': 'worker-crosswalk-line-hierarchy-comparison',
            'comparison_id': 'stop_line_hierarchy',
            'fixed_source_sha256': {name: digest(crosswalk_root / name) for name in fixed_sources},
            'map_sha256': {'crosswalk': cross_map, 'line': line_map},
            'first_full_halt_frame': halts[0][0]['frame'],
            'selected_references': ['near_side_crosswalk', 'marked_stop_line'],
            'diagnostic_comparison_passed': True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def compare_crosswalk_to_view(crosswalk_root, view_root):
    """Check the final reference branch using original sight and halt sources."""
    crosswalk_root, view_root = Path(crosswalk_root), Path(view_root)
    cross, view = [json.loads((root / 'approach_context.json').read_text())
                   for root in (crosswalk_root, view_root)]
    fixed = ('native_map_id', 'intersection_id', 'approach_road_id',
             'approach_lane_id', 'native_stop_sign_id',
             'intersection_polygon_xy_m', 'approach_forward_xy')
    for key in fixed:
        if cross.get(key) != view.get(key):
            raise ValueError('Fixed source condition differs: ' + key)
    if ((cross.get('near_side_crosswalk_exists'), cross.get('stop_line_exists')) != (True, False)
            or (view.get('near_side_crosswalk_exists'), view.get('stop_line_exists')) != (False, False)):
        raise ValueError('Deliberate crosswalk versus first-view source change missing')
    cross_lines, cross_walks, cross_map = _painted(crosswalk_root)
    view_lines, view_walks, view_map = _painted(view_root)
    if cross_lines or len(cross_walks) != 1 or view_lines or view_walks:
        raise ValueError('OpenDRIVE crosswalk/view inventory differs')
    fixed_sources = ('video_frames.jsonl', *CAMERAS)
    for name in fixed_sources:
        if digest(crosswalk_root / name) != digest(view_root / name):
            raise ValueError('Fixed source differs: ' + name)
    histories = [[json.loads(row) for row in (root / 'stop_history.jsonl').read_text().splitlines()]
                 for root in (crosswalk_root, view_root)]
    if len(histories[0]) != len(histories[1]) or not histories[0]:
        raise ValueError('Original halt histories have different frame counts')
    for a, b in zip(*histories):
        for key in ('frame', 'time_s', 'road_id', 'lane_id', 'stop_sign_id', 'ego_speed_mps'):
            if a.get(key) != b.get(key):
                raise ValueError('Fixed signed halt behavior differs: ' + key)
    halts = [[row for row in rows if row['ego_speed_mps'] == 0] for rows in histories]
    if not halts[0] or not halts[1] or halts[0][0]['ego_body_vertices_xy_m'] != halts[1][0]['ego_body_vertices_xy_m']:
        raise ValueError('Fixed complete-body halt location differs')
    cross_report = json.loads((crosswalk_root / 'analysis-report.json').read_text())
    cross_value = cross_report['measurements']['crosswalk_halt_observation']['value']
    view_value = analyze(view_root)
    if (cross_value['selected_reference'] != 'near_side_crosswalk' or
            view_value['selected_reference'] != 'first_observed_view' or
            not cross_value['halt_before_crosswalk_and_junction_observed'] or
            not view_value['halt_before_reference_and_junction_observed'] or
            not view_value['first_observed_view']):
        raise ValueError('Selected crosswalk or first-view observation differs')
    return {'format': 'worker-crosswalk-first-view-hierarchy-comparison',
            'comparison_id': 'sight_point_hierarchy',
            'fixed_source_sha256': {name: digest(crosswalk_root / name) for name in fixed_sources},
            'map_sha256': {'crosswalk': cross_map, 'first_view': view_map},
            'sight_source_sha256': digest(view_root / 'sight_history.jsonl'),
            'first_full_halt_frame': halts[0][0]['frame'],
            'first_observed_view': view_value['first_observed_view'],
            'diagnostic_comparison_passed': True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--line', type=Path)
    parser.add_argument('--view', type=Path)
    parser.add_argument('--crosswalk', type=Path)
    parser.add_argument('--both', type=Path)
    parser.add_argument('--marked', type=Path)
    parser.add_argument('--unmarked', type=Path)
    parser.add_argument('--before', type=Path)
    parser.add_argument('--inside', type=Path)
    parser.add_argument('--line-only', type=Path)
    parser.add_argument('--first-view', type=Path)
    parser.add_argument('--recorded-comparison', choices=sorted(RECORDED_PAIRS))
    parser.add_argument('--left', type=Path)
    parser.add_argument('--right', type=Path)
    parser.add_argument('--diagnostic', action='store_true')
    parser.add_argument('--left-pixel-review', type=Path)
    parser.add_argument('--right-pixel-review', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.recorded_comparison and args.left and args.right and not any(
            (args.crosswalk, args.first_view, args.line, args.view, args.both,
             args.marked, args.unmarked, args.before, args.inside, args.line_only)):
        receipt = compare_recorded(args.recorded_comparison, args.left, args.right,
                                   diagnostic=args.diagnostic,
                                   left_pixel_review=args.left_pixel_review,
                                   right_pixel_review=args.right_pixel_review)
    elif args.crosswalk and args.first_view and not (args.line or args.view or args.both or args.marked or args.unmarked or args.before or args.inside or args.line_only):
        receipt = compare_crosswalk_to_view(args.crosswalk, args.first_view)
    elif args.crosswalk and args.line_only and not (args.line or args.view or args.both or args.marked or args.unmarked or args.before or args.inside or args.first_view):
        receipt = compare_crosswalk_to_line(args.crosswalk, args.line_only)
    elif args.before and args.inside and not (args.line or args.view or args.crosswalk or args.both or args.marked or args.unmarked or args.line_only or args.first_view):
        receipt = compare_halt_position(args.before, args.inside)
    elif args.marked and args.unmarked and not (args.line or args.view or args.crosswalk or args.both or args.before or args.inside or args.line_only or args.first_view):
        receipt = compare_marked_unmarked(args.marked, args.unmarked)
        receipt['comparison_id'] = 'marked_vs_unmarked_crosswalk'
    elif args.crosswalk and args.both and not (args.line or args.view or args.marked or args.unmarked or args.before or args.inside or args.line_only or args.first_view):
        receipt = compare_crosswalk_priority(args.crosswalk, args.both)
        receipt['comparison_id'] = 'crosswalk_vs_crosswalk_and_line'
    elif args.line and args.view and not (args.crosswalk or args.both or args.marked or args.unmarked or args.before or args.inside or args.line_only or args.first_view):
        receipt = compare(args.line, args.view)
    else:
        parser.error('Supply one complete comparison pair')
    args.output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'comparison_id': receipt['comparison_id'],
                      'software_checks_passed': receipt.get('software_checks_passed',
                                                            receipt.get('diagnostic_comparison_passed'))}))
