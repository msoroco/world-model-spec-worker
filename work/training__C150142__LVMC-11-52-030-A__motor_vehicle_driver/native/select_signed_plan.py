"""Select only the signed ordinary red-curb source requirement for CPU proof."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASE = ROOT.name + '__ordinary_red_signed'


def select():
    path = ROOT / 'case-plan.json'
    plan = json.loads(path.read_text())
    row = plan['requirement_dispositions'][3]
    if row['requirement'] != 'text-3' or row['status'] not in (
            'exception_pending', 'selected_required') or CASE not in row['case_ids']:
        raise ValueError('Signed red-curb source requirement changed')
    row['status'] = 'selected_required'
    row['case_ids'] = [CASE]
    row['evidence_or_gap'] = (
        'Exact red curb whether or not accompanied by signage; signed case '
        'construction and source-based diagnostic selected. Native rendering, '
        'pixels, fallbacks, compatibility and independent audits remain pending.')
    path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
    return {'case_id': CASE, 'requirement': row['requirement'],
            'status': row['status'], 'cases_planned': len(plan['cases'])}


if __name__ == '__main__':
    print(json.dumps(select(), sort_keys=True))
