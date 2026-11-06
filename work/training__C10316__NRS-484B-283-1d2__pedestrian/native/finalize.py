"""Source-bound countdown timing report; no legal verdict or acceptance claim."""
import argparse
import json
from pathlib import Path

from measure_countdown import measure, sha


def countdown_clearance(folder):
    folder = Path(folder)
    return measure(folder / 'countdown_samples.jsonl', folder / 'countdown-context.json')


def report(folder, case_id):
    folder = Path(folder)
    value = countdown_clearance(folder)
    sources = {name: sha(folder / name) for name in ('countdown_samples.jsonl', 'countdown-context.json')}
    return {'format': 'worker-analysis-report-v1', 'case_id': case_id,
            'measurements': {'flashing_countdown_clearance': {
                'method': 'countdown_clearance', 'value': value, 'sources': sources}},
            'scope': 'synthetic_or_native_source_timing_without_exception_or_legal_verdict'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case-id', required=True)
    args = parser.parse_args()
    data = report(args.attempt, args.case_id)
    args.output.write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps({'case_id': args.case_id, 'measurement':
                      data['measurements']['flashing_countdown_clearance']['value']['clearance_relative_to_displayed_zero'],
                      'legal_verdict_claimed': False}))


if __name__ == '__main__':
    main()
