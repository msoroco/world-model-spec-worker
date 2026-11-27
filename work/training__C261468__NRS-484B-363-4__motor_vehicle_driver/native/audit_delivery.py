"""Independent CPU diagnostic audit; original acceptance remains operator owned."""
import argparse
import hashlib
import json
from pathlib import Path


def require(value, message):
    if not value:
        raise ValueError(message)


def read(path):
    return json.loads(path.read_text())


def run(case, attempt):
    attempt = Path(attempt)
    require((attempt / 'pass_trace.jsonl').is_file(), 'Missing required source: pass_trace.jsonl')
    for name in ('trace.jsonl', 'video_frames.jsonl', 'school_zone_context.json',
                 'context-survey.json', 'result.json', 'compatibility.json'):
        require((attempt / name).is_file(), 'Missing required source: ' + name)
    result = read(attempt / 'result.json')
    require(result['case_id'] == case, 'Wrong exact case result')
    require(result['provenance_kind'] == 'synthetic_fixture' and result['diagnostic_fixture'],
            'CPU proof must remain diagnostic')
    require(not result['physical_acceptance_claimed'] and not result['legal_verdict_claimed'],
            'Diagnostic result asserted original acceptance')
    trace = [json.loads(line) for line in (attempt / 'trace.jsonl').read_text().splitlines()]
    frames = [json.loads(line) for line in (attempt / 'video_frames.jsonl').read_text().splitlines()]
    passed = [json.loads(line) for line in (attempt / 'pass_trace.jsonl').read_text().splitlines()]
    require(len(trace) == len(frames) == len(passed) == 600, 'Full 600-frame pass record required')
    require(all(t['frame'] == f['carla_frame'] == p['native_frame'] and
                abs(t['time_s'] - f['time_s']) < 1e-6 and p['video_frame'] == i
                for i, (t, f, p) in enumerate(zip(trace, frames, passed))),
            'Original frame/time join differs')
    require(all(p['ego_route_direction_id'] == p['other_route_direction_id'] for p in passed),
            'Same-direction participants absent')
    require(all('ego_station_m' in p and 'other_station_m' in p for p in passed),
            'Participant motion absent')
    cameras = ('overview', 'approach', 'reference_corner', 'driver_reference')
    for i, name in enumerate(cameras):
        video = attempt / (name + '.mkv')
        receipt = read(attempt / ('source-' + str(i) + '.json'))
        require(video.is_file() and receipt['passed'] and receipt['frames'] == 600 and
                receipt['video_sha256'] == hashlib.sha256(video.read_bytes()).hexdigest() and
                receipt['rgb_sequence_sha256'], 'Full decoded source pixels missing: ' + name)
    require(result['physical_checks']['maneuver']['status'] in ('met', 'not_met', 'unverified') and
            result['physical_checks']['maneuver']['method'], 'Physical completion not independently reviewed')
    return {'case_id': case, 'diagnostic_only': True, 'original_acceptance_claimed': False,
            'joined_frames': 600, 'source_views': list(cameras), 'source_pixel_decode': True,
            'participants': ['ego', 'other_same_direction_vehicle'],
            'physical_status': result['physical_checks']['maneuver']['status']}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.case, args.attempt), sort_keys=True))
