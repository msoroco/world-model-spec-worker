"""Analyze retained C183370 variant sources without interpreting the statute."""
import argparse
import json
from math import isfinite
from pathlib import Path

from shapely.geometry import MultiPoint, Point, Polygon

from analyze import read_jsonl, sha, verify_media
from variant_recording_contract import ASSIGNMENT, description


def analyze_rows(frames, actors, readback, *, diagnostic=False):
    if len(frames) < 600 or len(frames) != len(actors):
        raise ValueError('Variant capture needs at least 600 joined frames')
    plan = readback['plan']
    polygon = Polygon(plan['repair_polygon_xy_m'])
    if not polygon.is_valid or polygon.area <= 0:
        raise ValueError('Surveyed variant pavement polygon invalid')
    actor_id = readback['control_actor_id']
    actor_type = readback['control_type_id']
    warning = readback.get('governing_warning_control')
    fixed = readback.get('fixed_flagger')
    if not diagnostic and plan['control_kind'] != 'warning_person':
        survey_flagger = plan.get('fixed_flagger')
        if (not isinstance(fixed, dict) or
                not isinstance(survey_flagger, dict) or
                fixed.get('actor_id') == actor_id or
                fixed.get('actor_id') != survey_flagger.get('actor_id') or
                fixed.get('type_id') != survey_flagger.get('type_id')):
            raise ValueError('Distinct original fixed-cell flagger is required')
    if not diagnostic and plan['control_kind'] == 'employee_exception':
        if (not isinstance(warning, dict) or
                warning.get('actor_id') == actor_id or
                warning.get('actor_id') != plan['governing_warning_control']['actor_id'] or
                warning.get('type_id') != plan['governing_warning_control']['type_id']):
            raise ValueError('Distinct original governing warning control is required')
    contact = []
    source_frames = []
    times = []
    for index, (frame, actor) in enumerate(zip(frames, actors)):
        if (frame['video_frame'] != index or actor['video_frame'] != index or
                actor['frame'] != frame['carla_frame'] or
                frame['native_frame'] != frame['carla_frame'] or
                actor.get('time_s') != frame['time_s']):
            raise ValueError('Variant actor/video frame join differs')
        native_frame, time = frame['carla_frame'], frame['time_s']
        if type(native_frame) is not int or type(time) not in (int, float) or not isfinite(time):
            raise ValueError('Variant frame/time identity invalid')
        if source_frames and (native_frame != source_frames[-1] + 1 or
                              abs(time - times[-1] - .05) > .001):
            raise ValueError('Variant 20 Hz frame/time continuity failed')
        source_frames.append(native_frame)
        times.append(time)
        expected_kind = ('synthetic_diagnostic_actor_and_map_readback' if diagnostic
                         else 'original_carla_actor_and_map_readback')
        if actor.get('source_kind') != expected_kind:
            raise ValueError('Variant actor provenance differs from acquisition mode')
        if (actor.get('control_actor_id') != actor_id or
                actor.get('control_type_id') != actor_type):
            raise ValueError('Original variant control actor identity differs')
        position = actor['control_xyz_m']
        if len(position) != 3 or not all(type(v) in (int, float) and isfinite(v) for v in position):
            raise ValueError('Original variant control position invalid')
        if Point(position[:2]).distance(polygon) > 15:
            raise ValueError('Original control actor left surveyed pavement vicinity')
        if fixed is not None and not diagnostic:
            observed_flagger = actor.get('fixed_flagger')
            if (not isinstance(observed_flagger, dict) or
                    observed_flagger.get('actor_id') != fixed['actor_id'] or
                    observed_flagger.get('type_id') != fixed['type_id']):
                raise ValueError('Original fixed flagger actor identity differs')
            flagger_xyz = observed_flagger.get('xyz_m')
            if (not isinstance(flagger_xyz, list) or len(flagger_xyz) != 3 or
                    not all(type(v) in (int, float) and isfinite(v)
                            for v in flagger_xyz) or
                    Point(flagger_xyz[:2]).distance(polygon) > 15):
                raise ValueError('Original fixed flagger left surveyed pavement vicinity')
        if warning is not None and not diagnostic:
            observed_warning = actor.get('governing_warning_control')
            if (not isinstance(observed_warning, dict) or
                    observed_warning.get('actor_id') != warning['actor_id'] or
                    observed_warning.get('type_id') != warning['type_id']):
                raise ValueError('Original governing warning actor identity differs')
            warning_xyz = observed_warning.get('xyz_m')
            if (not isinstance(warning_xyz, list) or len(warning_xyz) != 3 or
                    not all(type(v) in (int, float) and isfinite(v)
                            for v in warning_xyz) or
                    Point(warning_xyz[:2]).distance(polygon) > 15):
                raise ValueError('Original governing warning actor left surveyed pavement vicinity')
        vertices = actor['ego_body_vertices_xyz_m']
        if len(vertices) != 8 or any(len(v) != 3 or not all(
                type(c) in (int, float) and isfinite(c) for c in v) for v in vertices):
            raise ValueError('Original variant body vertices invalid')
        body = MultiPoint([(v[0], v[1]) for v in vertices]).convex_hull
        if body.area <= 0:
            raise ValueError('Original variant body footprint invalid')
        if body.intersects(polygon):
            contact.append(index)
    elapsed = times[-1] - times[0] + .05
    if elapsed < 30 - .001:
        raise ValueError('Variant source duration is shorter than 30 seconds')
    return {'source_frames': len(frames), 'source_elapsed_s': elapsed,
            'source_first_frame': source_frames[0],
            'source_last_frame': source_frames[-1],
            'pavement_footprint_contact_frames': contact,
            'pavement_footprint_contact_observed': bool(contact),
            'control_actor_near_pavement_frames': len(frames),
            'control_content_verified': False,
            'newly_repaired_pavement_verified': False,
            'paving_employee_exception_verified': False,
            'physical_completion_claimed': False,
            'legal_acceptance_claimed': False}


def analyze(attempt):
    attempt = Path(attempt)
    receipt = json.loads((attempt / 'capture-receipt.json').read_text())
    marker = json.loads((attempt / 'acquisition-provenance.json').read_text())
    diagnostic = (marker.get('provenance_kind') == 'synthetic_fixture' and
                  marker.get('diagnostic_fixture') is True)
    expected_kind = ('synthetic_diagnostic_capture' if diagnostic
                     else 'original_carla_capture')
    if receipt.get('source_kind') != expected_kind:
        raise ValueError('Variant receipt provenance differs from acquisition mode')
    if not diagnostic and (marker.get('provenance_kind') != 'native' or
                           marker.get('diagnostic_fixture') is not False):
        raise ValueError('Original Native provenance required')
    readback = json.loads((attempt / 'live-readback.json').read_text())
    config = json.loads((attempt / 'config.json').read_text())
    frames = read_jsonl(attempt / 'video_frames.jsonl')
    actors = read_jsonl(attempt / 'native-actors.jsonl')
    trace = read_jsonl(attempt / 'trace.jsonl')
    if (receipt.get('source_frames') != len(frames) or len(trace) != len(frames) or
            config.get('case_id') != ASSIGNMENT + '__' + receipt.get('control_kind', '') + '_' + receipt.get('case', '') or
            config.get('recording_description') != description(len(frames)) or
            receipt.get('control_kind') != readback['plan'].get('control_kind') or
            receipt.get('case') not in readback['plan']['cases']):
        raise ValueError('Variant source/config identity differs')
    expected_speed_provenance = ('synthetic_native_sample' if diagnostic
                                 else 'original_carla_velocity')
    if any(row.get('frame') != frame['carla_frame'] or
           row.get('time_s') != frame['time_s'] or
           row.get('position_m') != actor.get('ego_position_xyz_m', [])[:2] or
           row.get('speed_mps') != actor.get('ego_speed_mps') or
           row.get('speed_provenance') != expected_speed_provenance
           for row, actor, frame in zip(trace, actors, frames)):
        raise ValueError('Variant trace differs from actor/frame sources or acquisition mode')
    observations = analyze_rows(frames, actors, readback, diagnostic=diagnostic)
    requested = readback['plan']['cases'][receipt['case']]['requested_pavement_crossing']
    observations['requested_footprint_contact_matched'] = (
        observations['pavement_footprint_contact_observed'] == requested)
    media = verify_media(attempt, len(frames))
    source_hashes = {name: sha(attempt / name) for name in
                     ('capture-receipt.json', 'live-readback.json', 'video_frames.jsonl',
                      'native-actors.jsonl', 'road.xodr', 'trace.jsonl',
                      'acquisition-provenance.json', 'config.json')}
    result = {'format': ('c183370-variant-diagnostic-analysis-v1' if diagnostic
                         else 'c183370-variant-original-analysis-v1'),
              'source_kind': expected_kind, 'case': receipt['case'],
              'control_kind': receipt['control_kind'],
              'source_hashes': source_hashes, 'camera_sources': media,
              'observations': observations}
    output = attempt / 'source-analysis.json'
    if output.exists():
        raise ValueError('Preserve prior variant source analysis; use a fresh attempt')
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    analyze(args.attempt)


if __name__ == '__main__':
    main()
