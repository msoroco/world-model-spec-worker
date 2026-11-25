"""Exact C230259 primary draft saved-source path; Native capture remains pending."""
import argparse
import json
from pathlib import Path
from measure_right_edge import SOURCES, measure
from capture import check as capture_check, execute as capture_execute

PREFIX = 'training__C230259__NRS-484B-777-1__cycle_or_scooter_operator__'
CASES = (PREFIX + 'reference', PREFIX + 'contrast')


def check():
    config = json.loads(Path(__file__).with_name('config.json').read_text())
    contract = json.loads(Path(__file__).with_name('measurement-contract.json').read_text())
    if (config['case_id'] not in CASES or config['law_id'] != 'NRS-484B-777-1' or
            config['cell_id'] != 'C230259' or config['actor'] != 'cycle_or_scooter_operator' or
            config['rate_hz'] != 20 or config['duration_s'] != 30 or
            {camera['name'] for camera in config['cameras']} !=
            {'overview', 'approach', 'reference_corner', 'driver_reference'} or
            set(contract['input_sources']) != set(SOURCES) or
            abs(config['requested_cycle_center_y_m'] -
                capture_check()['cases'][config['case_id'].removeprefix(PREFIX)]) > .16):
        raise ValueError('Exact saved-source configuration or contract differs')
    capture_check()
    return {'case_id': config['case_id'], 'primary_draft': True, 'saved_source_path_checked': True,
            'native_capture_implemented': True, 'native_capture_executed': False,
            'physical_acceptance_claimed': False}


def process_saved(folder, expected_hashes):
    check()
    result = measure(folder, expected_hashes, diagnostic=False)
    if result['source_kind'] != 'original_native':
        raise ValueError('Original Native source required')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--process-saved')
    parser.add_argument('--source-hashes')
    parser.add_argument('--capture', action='store_true')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if args.output_dir and not args.check and not args.process_saved:
        args.capture = True
    if sum((args.check, bool(args.process_saved), args.capture)) != 1:
        raise SystemExit('choose --check, --process-saved, or --capture')
    if args.check:
        print(json.dumps(check()))
    elif args.capture:
        if not args.output_dir:
            raise SystemExit('--output-dir required')
        case = check()['case_id'].removeprefix(PREFIX)
        config = json.loads(Path(__file__).with_name('config.json').read_text())
        capture_receipt = capture_execute(case, args.output_dir, args.host, args.port,
                                          config['requested_cycle_center_y_m'])
        print(json.dumps({'capture': capture_receipt,
                          'capture_sealed': (Path(args.output_dir) / 'capture-seal.json').is_file(),
                          'measurement_deferred_to_recorded_only_processing': True}))
    else:
        if not args.source_hashes:
            raise SystemExit('--source-hashes required')
        print(json.dumps(process_saved(args.process_saved,
              json.loads(Path(args.source_hashes).read_text())), sort_keys=True))


if __name__ == '__main__':
    main()
