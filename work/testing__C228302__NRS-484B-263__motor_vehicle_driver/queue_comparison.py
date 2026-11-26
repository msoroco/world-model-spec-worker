"""Run one selected comparison from five independent original exit audits."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from delivery_audit import audit_comparisons


def run(report_map: Path, comparison_id: str, output: Path) -> dict:
    paths = json.loads(report_map.read_text(encoding='utf-8'))
    if not isinstance(paths, dict):
        raise ValueError('exact original report map required')
    reports = {case_id: json.loads(Path(path).read_text(encoding='utf-8'))
               for case_id, path in paths.items()}
    matches = [row for row in audit_comparisons(reports)
               if row['comparison_id'] == comparison_id]
    if len(matches) != 1:
        raise ValueError('selected comparison identity missing')
    if output.exists():
        raise ValueError('refusing to overwrite original comparison audit')
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(matches[0], indent=2, sort_keys=True) + '\n',
                      encoding='utf-8')
    return matches[0]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--report-map', type=Path, required=True)
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.report_map, args.comparison, args.output), sort_keys=True))
