"""Selected Native runner; saved analysis is a separate recorded-only operation."""
import argparse
import json
from pathlib import Path

from capture import check as capture_check, execute as capture_execute
from left_lane_measure import measure, sha

PREFIX = 'training__C230259__NRS-484B-208-1__motor_vehicle_driver__'


def check():
    config = json.loads(Path(__file__).with_name('config.json').read_text())
    if (config['case_id'] not in (PREFIX + 'reference', PREFIX + 'contrast') or
            config['cell_id'] != 'C230259' or config['law_id'] != 'NRS-484B-208-1' or
            config['actor'] != 'motor_vehicle_driver' or config['rate_hz'] != 20 or
            config['duration_s'] != 30 or len(config['cameras']) != 4):
        raise ValueError('Exact selected construction differs')
    capture_check()
    return {'case_id': config['case_id'], 'candidate_id': config['candidate_id'],
            'native_capture_implemented': True, 'native_capture_executed': False}


def process_saved(folder):
    root = Path(folder)
    return measure(root / 'native-actors.jsonl', root / 'native-road-context.json', {
        name: sha(root / name) for name in ('native-actors.jsonl', 'native-road-context.json')})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--process-saved')
    parser.add_argument('--output-dir')
    parser.add_argument('--host', default='127.0.0.1')
    parser.add_argument('--port', type=int, default=2000)
    args = parser.parse_args()
    if sum((args.check, bool(args.process_saved), bool(args.output_dir))) != 1:
        raise SystemExit('Choose exactly one check, saved analysis or capture')
    if args.check:
        print(json.dumps(check()))
    elif args.process_saved:
        print(json.dumps(process_saved(args.process_saved)))
    else:
        case = check()['case_id'].removeprefix(PREFIX)
        receipt = capture_execute(case, args.output_dir, args.host, args.port)
        print(json.dumps({'capture': receipt,
            'capture_sealed': (Path(args.output_dir) / 'capture-seal.json').is_file(),
            'saved_processing_deferred': True}))


if __name__ == '__main__':
    main()
