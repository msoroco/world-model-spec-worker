"""Run the independent original attempt audit for one exact case."""
import argparse
import json
from pathlib import Path

from delivery_audit import audit_attempt


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--attempt', type=Path, required=True)
    p.add_argument('--case-id', required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError('retain prior original audit')
    a.output.write_text(json.dumps(audit_attempt(a.attempt, a.case_id), indent=2) + '\n')


if __name__ == '__main__':
    main()
