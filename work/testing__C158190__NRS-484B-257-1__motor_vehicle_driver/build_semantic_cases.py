"""Validate the complete canonical C158190 semantic proposal and source bundles.

The historical four-case builder was retired after all fourteen exact cases were
added to proposals/cases.json. This command does not rewrite that proposal.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from worker_exchange.semantic_delivery import validate


def main():
    assignment = json.loads((REPO / 'inputs' / ROOT.name / 'assignment.json').read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    entries = []
    for name in ('execution-manifest.json', 'through-speed-compatibility-manifest.json',
                 'sign-angle-compatibility-manifest.json',
                 'view-location-compatibility-manifest.json'):
        entries.extend(json.loads((ROOT / name).read_text())['cases'])
    planned = {case['case_id'] for case in plan['cases']}
    if len(entries) != 14 or {entry['case_id'] for entry in entries} != planned:
        raise ValueError('Fourteen exact case source bundles must cover the case plan')
    result = validate(ROOT, assignment, {'cases': entries})
    if result['selected_cases'] != 14:
        raise ValueError('Canonical semantic case coverage changed')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
