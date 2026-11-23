"""Saved-only C229398 projection analysis from reviewed original source rows.

The diagnostic path is explicit and never claims original Native observation.
"""
import argparse
import hashlib
import json
from pathlib import Path

from projection_measure import measure, point, FEET_PER_METER
from source_footprints import build

VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')
FRAMES = 600


def required(root, name):
    path = Path(root) / name
    if not path.is_file():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()
            if line.strip()]


def measure_text_0(measurement):
    return measurement['maximum_projection_perpendicular_to_curb_ft']


def measure_scope_0(measurement):
    return {'vehicle_load_trailer_maximum_ft':
            measurement['maximum_projection_perpendicular_to_curb_ft'],
            'frames': measurement['frames']}


def finalize(attempt, output):
    attempt, output = Path(attempt), Path(output)
    if output.exists() or (attempt / 'result.json').exists() or (attempt / 'channels').exists():
        raise ValueError('Use a fresh saved attempt')
    config = json.loads(required(attempt, 'config.json').read_text())
    construction = json.loads(required(attempt, 'construction.json').read_text())
    if (config.get('case_id') != construction.get('case_id')
            or config.get('selected_case_id') != config.get('case_id')
            or config.get('duration_s') != 30 or config.get('rate_hz') != 20
            or config.get('target_projection_ft') not in (14, 15, 16)):
        raise ValueError('Exact C229398 saved case differs')
    marker = json.loads(required(attempt, 'acquisition-provenance.json').read_text())
    synthetic = marker.get('provenance_kind') == 'synthetic_fixture'
    if synthetic != (marker.get('diagnostic_fixture') is True):
        raise ValueError('Diagnostic provenance flag differs')
    if not synthetic and marker.get('provenance_kind') != 'native':
        raise ValueError('Original Native provenance required')
    raw = required(attempt, 'native-raw-actors.jsonl')
    curb = required(attempt, 'reviewed-curb.json')
    frame_map = rows(required(attempt, 'video_frames.jsonl'))
    trace = rows(required(attempt, 'trace.jsonl'))
    actor_rows = rows(raw)
    if len(frame_map) != FRAMES or len(trace) != FRAMES or len(actor_rows) != FRAMES:
        raise ValueError('Incomplete 600-frame original source interval')
    for index, (mapping, motion, actor) in enumerate(zip(frame_map, trace, actor_rows)):
        if (mapping.get('video_frame') != index
                or motion.get('frame') != mapping.get('carla_frame')
                or actor.get('frame') != index
                or actor.get('native_frame') != mapping.get('carla_frame')
                or abs(motion.get('time_s', -1) - mapping.get('time_s', -2)) > 1e-6
                or abs(actor.get('time_s', -1) - mapping.get('time_s', -2)) > 1e-6):
            raise ValueError('Original source frame/timestamp join differs')
    for view in VIEWS:
        required(attempt, view + '.mkv')
    footprints = attempt / 'derived-source-footprints.jsonl'
    build(raw, curb, footprints, allow_synthetic=synthetic)
    measurement = measure(curb, footprints, allow_synthetic=synthetic)
    curb_data = json.loads(curb.read_text())
    origin = point(curb_data['origin_xy_m'])
    normal = point(curb_data['street_normal_xy'])
    footprint_rows = rows(footprints)
    per_frame = []
    for row in footprint_rows:
        vertices = [point(vertex) for item in row['participants'].values()
                    if item is not None for vertex in item['vertices_xy_m']]
        farthest_m = max((x - origin[0]) * normal[0] +
                         (y - origin[1]) * normal[1] for x, y in vertices)
        per_frame.append(max(0.0, farthest_m) * FEET_PER_METER)
    if abs(max(per_frame) - measure_text_0(measurement)) > 1e-7:
        raise ValueError('Derived channel and full-part maximum differ')
    channel_dir = attempt / 'channels'
    channel_dir.mkdir()
    channel = channel_dir / 'maximum_projection_perpendicular_to_curb.jsonl'
    channel.write_text(''.join(json.dumps({'time_s': frame['time_s'], 'value': value},
                                          allow_nan=False) + '\n'
                               for frame, value in zip(frame_map, per_frame)))
    actual = measure_text_0(measurement)
    expected = config['target_projection_ft']
    source_hashes = {'native-raw-actors.jsonl': sha(raw),
                     'reviewed-curb.json': sha(curb),
                     curb_data['source_file']: sha(attempt / curb_data['source_file'])}
    report = {'format': 'c229398-saved-projection-analysis-v1',
              'case_id': config['case_id'],
              'measurements': {
                  'text_0_projection': {'method': 'measure_text_0',
                                        'value': actual,
                                        'sources': source_hashes},
                  'reviewed_scope_0_projection': {'method': 'measure_scope_0',
                                                  'value': measure_scope_0(measurement),
                                                  'sources': source_hashes}},
              'physical_acceptance_claimed': False,
              'legal_verdict_claimed': False}
    result = {
        'case_id': config['case_id'],
        'measured_values': {'maximum_projection_perpendicular_to_curb_ft': actual},
        'target_checks': [{'target': 'maximum_projection_perpendicular_to_curb_ft',
                           'requested': expected, 'measured': actual,
                           'method': 'source-bound full-part curb-normal maximum',
                           'tolerance': 0.5, 'matched': abs(actual-expected) <= 0.5,
                           'physical_cause_confirmed': False,
                           'cause_evidence': sorted(source_hashes)}],
        'setup_confirmed': False, 'behavior_attempted': False,
        'maneuver_completed': False,
        'termination_reason': '600 saved frames analyzed; physical review pending',
        'physical_failure_flags': ['curb identity, actor attachment and camera framing require Native review'],
        'trace_reference': 'trace.jsonl',
        'video_references': [view + '.mkv' for view in VIEWS],
        'video_frame_map_reference': 'video_frames.jsonl',
        'recording_description': construction['recording_description'],
        'recording_evidence': [
            {'name': 'maximum_projection_perpendicular_to_curb', 'unit': 'ft',
             'reference': 'channels/' + channel.name},
            {'name': 'reviewed_curb', 'unit': 'structured',
             'reference': 'reviewed-curb.json'}],
        'realized_observables': {'full_part_projection': {
            'value': actual, 'unit': 'ft',
            'method': 'maximum of 600 source-derived vehicle/load/trailer footprints',
            'time_window': 'full 30-second saved interval',
            'statistic': 'maximum', 'reference': 'derived-source-footprints.jsonl'}},
        'provenance_kind': 'synthetic_local_diagnostic' if synthetic else 'source_review_unverified',
        'accepted': False, 'legal_verdict_claimed': False,
    }
    from worker_exchange.native_output import validate_result
    validate_result(result)
    output.write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
    (attempt / 'result.json').write_text(json.dumps(result, indent=2,
                                                    allow_nan=False) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(json.dumps(finalize(args.attempt, args.output), sort_keys=True))
