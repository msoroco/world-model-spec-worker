"""No-countdown source-bound analysis only; saved Native delivery remains unproved."""
import argparse
import json
from pathlib import Path

from no_countdown import measure, sha


def no_countdown_entry(folder):
    folder = Path(folder)
    return measure(folder / 'no-countdown-samples.jsonl', folder / 'no-countdown-context.json')


def report(folder, case_id):
    folder = Path(folder)
    value = no_countdown_entry(folder)
    sources = {name: sha(folder / name) for name in
               ('no-countdown-samples.jsonl', 'no-countdown-context.json', 'road.xodr')}
    return {'format': 'worker-analysis-report-v1', 'case_id': case_id,
            'measurements': {'no_countdown_entry_and_clearance': {
                'method': 'no_countdown_entry', 'value': value, 'sources': sources}},
            'scope': 'synthetic timing without lawful-prior-entry or legal verdict'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--case-id', required=True)
    args = parser.parse_args()
    value = report(args.attempt, args.case_id)
    Path(args.output).write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps({'case_id': args.case_id,
                      'entry_indication': value['measurements']['no_countdown_entry_and_clearance']['value']['entry_indication'],
                      'legal_verdict_claimed': False}))


if __name__ == '__main__':
    main()
