"""Audit original red-curb attempts and controlled original-attempt pairs."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import subprocess

from comparison_audit import ALLOWED, FIELDS, ROOT
from physical_completion import evaluate


VIEWS = {
    'overview': (1920, 1080),
    'approach': (1280, 720),
    'reference_corner': (1280, 720),
    'driver_reference': (1280, 720),
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def read_rows(path):
    return [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines()]


def original_source(attempt, case_id):
    attempt = Path(attempt)
    config = read_json(attempt / 'config.json')
    context_path = attempt / 'red-curb-context.json'
    events_path = attempt / 'original-red-curb-events.jsonl'
    context = read_json(context_path)
    provenance = read_json(attempt / 'acquisition-provenance.json')
    if config['case']['case_id'] != case_id or context['case_id'] != case_id:
        raise ValueError('exact original case identity mismatch')
    packet_sha = context.get('reviewed_packet_sha256')
    if (context.get('source_kind') != 'original_native' or
            provenance.get('source_kind') != 'original_native' or
            provenance.get('diagnostic_fixture') is not False or
            not packet_sha or provenance.get('reviewed_packet_sha256') != packet_sha):
        raise ValueError('reviewed original Native source custody missing')
    scene = context['scene']
    if not scene['red_curb_paint'] or not scene['municipal_jurisdiction']:
        raise ValueError('governed red curb or jurisdiction missing')
    events = read_rows(events_path)
    if len(events) < 2 or any(row.get('original_frame') is None for row in events):
        raise ValueError('original red-curb event history incomplete')
    times = [row['original_time_s'] for row in events]
    if any(type(t) not in (int, float) or not math.isfinite(t) for t in times):
        raise ValueError('original event time missing')
    if any(b <= a for a, b in zip(times, times[1:])):
        raise ValueError('original event time not increasing')
    values = {key: scene[key] for key in FIELDS if key != 'duration_s'}
    values['duration_s'] = times[-1] - times[0]
    source = {
        'case_id': case_id,
        'context_sha256': digest(context_path),
        'events_sha256': digest(events_path),
        'reviewed_packet_sha256': packet_sha,
        'curb_segment_id': scene['curb_segment_id'],
        'parking_route_xy': scene['parking_route_xy'],
    }
    return values, source


def source_audit(attempt, case_id):
    attempt = Path(attempt)
    _, source = original_source(attempt, case_id)
    traces = read_rows(attempt / 'trace.jsonl')
    mappings = read_rows(attempt / 'camera-frame-map.jsonl')
    frames = read_rows(attempt / 'video_frames.jsonl')
    if len(traces) < 900 or len(traces) != len(mappings) or len(traces) != len(frames):
        raise ValueError('original 20 Hz trace/camera history incomplete')
    first = traces[0]['frame']
    first_time = mappings[0]['time_s']
    for index, (trace, mapping, frame) in enumerate(zip(traces, mappings, frames)):
        if trace.get('frame') != first + index:
            raise ValueError('original trace frame continuity missing')
        if mapping.get('native_frame') != trace['frame'] or mapping.get('frame_index') != index:
            raise ValueError('original trace/camera frame join mismatch')
        if (abs(mapping['time_s'] - first_time - index / 20) > .002 or
                abs(trace['time_s'] - traces[0]['time_s'] - index / 20) > .002):
            raise ValueError('original camera cadence mismatch')
        if set(mapping['camera_frames']) != set(VIEWS) or any(
                value != trace['frame'] for value in mapping['camera_frames'].values()):
            raise ValueError('four original camera frames do not join')
        if frame.get('native_frame') != trace['frame']:
            raise ValueError('original video frame identity mismatch')
    videos = {}
    for view, dimensions in VIEWS.items():
        path = attempt / (view + '.mkv')
        probe = subprocess.run(
            ['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-count_frames',
             '-show_entries', 'stream=width,height,nb_read_frames', '-of', 'json', str(path)],
            capture_output=True, text=True, check=True)
        stream = json.loads(probe.stdout)['streams'][0]
        if (stream['width'], stream['height'], int(stream['nb_read_frames'])) != (*dimensions, len(traces)):
            raise ValueError('original video dimension/frame count mismatch: ' + view)
        decode = subprocess.run(
            ['ffmpeg', '-v', 'error', '-xerror', '-i', str(path), '-f', 'null', '-'],
            capture_output=True, text=True)
        if decode.returncode or decode.stderr.strip():
            raise ValueError('original video decode failed: ' + view)
        videos[view] = digest(path)
    return {
        'case_id': case_id,
        'source': source,
        'original_frame_count': len(traces),
        'original_video_sha256': videos,
        'physical_completion': evaluate(traces, case_id),
        'legal_judgment': None,
        'original_audit': True,
    }


def comparison_audit(name, left_attempt, right_attempt):
    plan = read_json(ROOT / 'case-plan.json')
    pair = next((item for item in plan['comparisons'] if item['comparison_id'] == name), None)
    if pair is None or name not in ALLOWED:
        raise ValueError('unknown exact comparison')
    left_id, right_id = pair['case_ids']
    left, left_source = original_source(left_attempt, left_id)
    right, right_source = original_source(right_attempt, right_id)
    if (left_source['curb_segment_id'] != right_source['curb_segment_id'] or
            left_source['parking_route_xy'] != right_source['parking_route_xy']):
        raise ValueError('original curb segment or route changed')
    differences = [key for key in FIELDS if left[key] != right[key]]
    if not differences or not set(differences) <= set(ALLOWED[name]):
        raise ValueError('original pair has absent or uncontrolled source difference')
    return {
        'comparison_id': name,
        'case_ids': pair['case_ids'],
        'deliberate_source_fields': differences,
        'sources': [left_source, right_source],
        'physical_acceptance': False,
        'legal_judgment': None,
        'original_pair_audit': True,
    }


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest='action', required=True)
    single = sub.add_parser('source')
    single.add_argument('--attempt', required=True)
    single.add_argument('--case', required=True)
    single.add_argument('--output', required=True)
    pair = sub.add_parser('comparison')
    pair.add_argument('--comparison', required=True)
    pair.add_argument('--left', required=True)
    pair.add_argument('--right', required=True)
    pair.add_argument('--output', required=True)
    args = parser.parse_args()
    result = (source_audit(args.attempt, args.case) if args.action == 'source' else
              comparison_audit(args.comparison, args.left, args.right))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print(json.dumps({'output': str(output), 'sha256': digest(output)}, sort_keys=True))


if __name__ == '__main__':
    main()
