"""Source-only conditional curb-departure analysis; saved delivery remains pending."""
import argparse
import json
from pathlib import Path

from curb import measure, sha


def curb_departure(folder):
    folder = Path(folder)
    return measure(folder / 'curb-samples.jsonl', folder / 'curb-context.json')


def report(folder, case_id):
    folder = Path(folder)
    value = curb_departure(folder)
    sources = {name: sha(folder / name) for name in
               ('curb-samples.jsonl', 'curb-context.json', 'road.xodr')}
    return {'format': 'worker-analysis-report-v1', 'case_id': case_id,
            'measurements': {'curb_departure_conditional_margin': {
                'method': 'curb_departure', 'value': value, 'sources': sources}},
            'scope': 'synthetic conditional stopping margin without actual driver capability or legal finding'}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case-id', required=True)
    args = parser.parse_args()
    value = report(args.attempt, args.case_id)
    args.output.write_text(json.dumps(value, indent=2) + '\n')
    print(json.dumps({'case_id': args.case_id,
                      'conditional_yield_relation': value['measurements']['curb_departure_conditional_margin']['value']['conditional_yield_relation'],
                      'impossibility_to_yield_proven': False, 'legal_verdict_claimed': False}))


if __name__ == '__main__':
    main()
