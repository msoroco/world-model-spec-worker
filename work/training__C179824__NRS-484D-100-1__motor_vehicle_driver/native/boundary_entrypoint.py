"""Exact-case Native entrypoint for a source-bound civil/visibility request.

An original attempt requires a dated Nevada sun-event packet. The packet is
only a clock request; later independent review must bind the original samples.
"""
import argparse
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path

from civil_visibility_runner import check as acquisition_check, execute


def require(value, message):
    if not value:
        raise ValueError(message)


def checked_request(config):
    case_id = config.get('case_id')
    require(case_id == config.get('selected_case_id') == config.get('case', {}).get('case_id'),
            'exact boundary case identity missing')
    request = config.get('boundary_request', {})
    distance = request.get('target_distance_ft')
    require(distance in (999, 1000, 1001), 'distance request must be a 1,000-foot neighbor')
    branch = request.get('civil_branch')
    minute = request.get('civil_offset_min')
    require((branch is None and minute is None) or
            (branch in ('sunset', 'sunrise') and minute in (29, 30, 31)),
            'civil boundary request invalid')
    proof = acquisition_check(distance)
    return {'passed': True, 'case_id': case_id, 'request': request,
            'native_acquisition': proof, 'original_capture_attested': False}


def source_clock(packet, branch, minute):
    require(isinstance(packet, dict) and packet.get('source_kind') == 'dated_sun_event_source' and
            packet.get('state') == 'Nevada' and packet.get('location') and
            packet.get('applicable_sunset') and packet.get('following_sunrise'),
            'dated Nevada sun-event source missing')
    sunset = datetime.fromisoformat(packet['applicable_sunset'])
    sunrise = datetime.fromisoformat(packet['following_sunrise'])
    require(sunset.tzinfo is not None and sunrise.tzinfo is not None and sunset < sunrise,
            'offset-aware ordered sun events required')
    if branch is None:
        return sunset + timedelta(hours=1)
    return (sunset + timedelta(minutes=minute) if branch == 'sunset' else
            sunrise - timedelta(minutes=minute))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--sun-event-source')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    config = json.loads((Path(__file__).parent/'config.json').read_text())
    proof = checked_request(config)
    if args.check:
        require(not args.output_dir and not args.sun_event_source,
                'offline check cannot write a Native attempt')
        print(json.dumps(proof, sort_keys=True))
        return
    source_path = args.sun_event_source or os.environ.get('C179824_SUN_EVENT_SOURCE')
    require(args.output_dir and source_path,
            'original output and dated sun-event source required')
    event_path = Path(source_path)
    raw = event_path.read_bytes()
    event = json.loads(raw)
    request = config['boundary_request']
    start = source_clock(event, request['civil_branch'], request['civil_offset_min'])
    result = execute(args.output_dir, args.host, args.port, config['weather_name'],
                     request['target_distance_ft'], start.isoformat(),
                     config['lamp_setting_on'], config['target_speed_mps'])
    output = Path(args.output_dir)
    (output/'sun-event-source.json').write_bytes(raw)
    (output/'sun-event-request.json').write_text(json.dumps({
        'source_kind': 'dated_sun_event_source_request',
        'source_sha256': hashlib.sha256(raw).hexdigest(),
        'source_path': 'sun-event-source.json',
        'case_id': config['case_id'],
        'request': request,
        'civil_start_iso': start.isoformat(),
        'independent_review_required': True}, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
