"""Exact-case Native entrypoint for a source-bound travel-to-park attempt."""
import argparse
from datetime import datetime, timedelta
import hashlib
import json
import os
from pathlib import Path

from parked_runner import check as acquisition_check, execute


def require(value, message):
    if not value:
        raise ValueError(message)


def checked_request(config):
    case_id = config.get('case_id')
    require(case_id == config.get('selected_case_id') == config.get('case', {}).get('case_id'),
            'exact parked case identity missing')
    request = config.get('parked_request', {})
    require(request.get('lamp_setting_on') in (True, False) and
            type(request.get('lamp_setting_on')) is bool and
            request.get('target_distance_ft') == 1000,
            'parked lamp and 1,000-foot request missing')
    return {'passed': True, 'case_id': case_id, 'request': request,
            'native_acquisition': acquisition_check(1000),
            'original_capture_attested': False,
            'parked_exception_resolved': False}


def source_clock(packet):
    require(packet.get('source_kind') == 'dated_sun_event_source' and
            packet.get('state') == 'Nevada' and packet.get('location') and
            packet.get('applicable_sunset') and packet.get('following_sunrise'),
            'dated Nevada sun-event source missing')
    sunset = datetime.fromisoformat(packet['applicable_sunset'])
    sunrise = datetime.fromisoformat(packet['following_sunrise'])
    require(sunset.tzinfo is not None and sunrise.tzinfo is not None and sunset < sunrise,
            'offset-aware ordered sun events required')
    start = sunset + timedelta(hours=1)
    require(start < sunrise, 'parked nighttime request outside sourced night')
    return start


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
    raw = Path(source_path).read_bytes()
    start = source_clock(json.loads(raw))
    request = config['parked_request']
    result = execute(args.output_dir, args.host, args.port, config['weather_name'],
                     request['target_distance_ft'], start.isoformat(),
                     request['lamp_setting_on'], config['target_speed_mps'])
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
