"""Run one declared independent comparison from six original case audits."""
import argparse
import json
from pathlib import Path

from delivery_audit import audit_comparisons


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--comparison-id', required=True)
    p.add_argument('--reports', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    if a.output.exists():
        raise ValueError('retain prior original comparison audit')
    reports = json.loads(a.reports.read_text())
    matching = [r for r in audit_comparisons(reports)
                if r['comparison_id'] == a.comparison_id]
    if len(matching) != 1:
        raise ValueError('unknown exact comparison')
    a.output.write_text(json.dumps(matching[0], indent=2) + '\n')


if __name__ == '__main__':
    main()
