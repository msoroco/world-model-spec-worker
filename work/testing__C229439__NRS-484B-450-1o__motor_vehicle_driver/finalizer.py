"""Saved-only source-bound observation finalizer for parking-device cases."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from parking import audit_saved_attempt


def finalize(attempt_path, capture_root, output_path):
    attempt = json.loads(Path(attempt_path).read_text())
    audit = audit_saved_attempt(attempt, capture_root)
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({'format': 'parking-device-observations',
                                  'case_id': attempt['case_id'],
                                  'source_audit': audit,
                                  'legal_judgment': None}, indent=2) + '\n')
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--capture-root', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    print(finalize(args.attempt, args.capture_root, args.output))


if __name__ == '__main__':
    main()
