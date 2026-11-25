"""Read the latest saved-only processing result without requesting Native replay."""
import argparse
import json
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--saved-output', required=True)
    args = parser.parse_args()
    versions = sorted(Path(args.saved_output).glob('v[0-9][0-9][0-9][0-9]'))
    if not versions:
        raise ValueError('No saved processing version')
    latest = versions[-1]
    feedback = latest / 'feedback.json'
    if feedback.is_file():
        result = json.loads(feedback.read_text())
        if result.get('native_replay_requested') is not False:
            raise ValueError('Saved feedback requested Native replay')
        if result.get('case_id', args.case) != args.case:
            raise ValueError('Saved feedback belongs to another case')
        print(json.dumps({'case_id': args.case, 'saved_version': latest.name,
                          'feedback': result}, sort_keys=True))
        return
    processing = latest / 'processing.json'
    if not processing.is_file():
        raise ValueError('Saved processing has neither receipt nor feedback')
    result = json.loads(processing.read_text())
    if result.get('case_id') != args.case or result.get('recorded_only') is not True:
        raise ValueError('Saved processing receipt mismatch')
    print(json.dumps({'case_id': args.case, 'saved_version': latest.name,
                      'passed': result.get('passed'),
                      'missing_evidence': result.get('missing_evidence')}, sort_keys=True))


if __name__ == '__main__':
    main()
