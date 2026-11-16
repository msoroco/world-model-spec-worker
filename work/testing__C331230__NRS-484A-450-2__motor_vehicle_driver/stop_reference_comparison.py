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
    lines = source.findall(".//object[@name='StopLine']")
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


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--line', type=Path, required=True)
    parser.add_argument('--view', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    receipt = compare(args.line, args.view)
    args.output.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'comparison_id': receipt['comparison_id'],
                      'diagnostic_comparison_passed': receipt['diagnostic_comparison_passed']}))
