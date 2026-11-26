"""Bind current source-built exact constructions to the CPU diagnostic plan."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def update():
    draft = json.loads((ROOT / 'draft-roadway-manifest.json').read_text())
    diagnostic = json.loads((ROOT / 'diagnostic-manifest.json').read_text())
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    for entry in draft['cases']:
        case_id = entry['case_id']
        selected = next(row for row in diagnostic['cases'] if row['case_id'] == case_id)
        planned = next(row for row in plan['cases'] if row['case_id'] == case_id)
        selected['construction_sha256'] = entry['construction_sha256']
        planned['construction_sha256'] = entry['construction_sha256']
    (ROOT / 'diagnostic-manifest.json').write_text(json.dumps(diagnostic, indent=2) + '\n')
    (ROOT / 'case-plan.json').write_text(json.dumps(plan, indent=2) + '\n')


if __name__ == '__main__':
    update()
