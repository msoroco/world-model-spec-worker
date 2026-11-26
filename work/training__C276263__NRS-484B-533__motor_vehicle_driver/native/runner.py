"""Exact primary C276263 CPU draft; original three-duty telemetry is required."""
import argparse
import json
from pathlib import Path
from grade import check as grade_check
from measure import SOURCES, measure
from capture import check as capture_check, execute as capture_execute

PREFIX = 'training__C276263__NRS-484B-533__motor_vehicle_driver__'


def check():
    config = json.loads(Path(__file__).with_name('config.json').read_text())
    if (config['case_id'] not in {PREFIX + case for case in capture_check()['cases']} or
            config['law_id'] != 'NRS-484B-533' or config['cell_id'] != 'C276263' or
            config['actor'] != 'motor_vehicle_driver' or config['rate_hz'] != 20 or
            config['duration_s'] != 30 or
            {camera['name'] for camera in config['cameras']} !=
            {'overview', 'approach', 'reference_corner', 'driver_reference'} or
            set(config['required_saved_sources']) != set(SOURCES) or
            config['requested_controls'] !=
            capture_check()['cases'][config['case_id'].removeprefix(PREFIX)]):
        raise ValueError('Exact three-duty primary configuration differs')
    capture_check()
    return {'case_id': config['case_id'], 'grade_geometry': grade_check(),
            'saved_source_path_checked': True, 'engine_instrumentation_required': True,
            'native_capture_implemented': True, 'native_executed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--process-saved')
    parser.add_argument('--source-hashes')
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    parser.add_argument('--instrument-host')
    parser.add_argument('--instrument-port', type=int)
    args = parser.parse_args()
    if sum((args.check, bool(args.process_saved), args.capture)) != 1:
        raise SystemExit('choose --check, --process-saved, or --capture')
    if args.check:
        print(json.dumps(check()))
    elif args.capture:
        if not args.output_dir:
            raise SystemExit('--output-dir required')
        case = check()['case_id'].removeprefix(PREFIX)
        print(json.dumps(capture_execute(case, args.output_dir, args.host, args.port,
                                         args.instrument_host, args.instrument_port)))
    else:
        if not args.source_hashes:
            raise SystemExit('--source-hashes required')
        check()
        hashes = json.loads(Path(args.source_hashes).read_text())
        print(json.dumps(measure(args.process_saved, hashes, diagnostic=False)))


if __name__ == '__main__':
    main()
