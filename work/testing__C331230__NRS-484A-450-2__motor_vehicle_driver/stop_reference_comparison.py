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

CAMERAS = ('overview.mkv', 'approach.mkv', 'reference_corner.mkv', 'driver_reference.mkv')
FIXED = ('native_map_id', 'intersection_id', 'approach_road_id',
         'approach_lane_id', 'native_stop_sign_id', 'intersection_polygon_xy_m',
         'approach_forward_xy', 'near_side_crosswalk_exists')


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


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--line', type=Path)
    parser.add_argument('--view', type=Path)
    parser.add_argument('--crosswalk', type=Path)
    parser.add_argument('--both', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.crosswalk and args.both and not (args.line or args.view):
        receipt = compare_crosswalk_priority(args.crosswalk, args.both)
        receipt['comparison_id'] = 'crosswalk_vs_crosswalk_and_line'
    elif args.line and args.view and not (args.crosswalk or args.both):
        receipt = compare(args.line, args.view)
    else:
        parser.error('Supply --line and --view, or --crosswalk and --both')
    args.output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'comparison_id': receipt['comparison_id'],
                      'diagnostic_comparison_passed': receipt['diagnostic_comparison_passed']}))
