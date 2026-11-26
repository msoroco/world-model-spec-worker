"""Bind exact original comparison commands and selected diagnostic audit."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    source = HERE / 'compare_saved.py'
    rows = []
    for comparison in plan['comparisons']:
        cid = comparison['comparison_id']
        rows.append({'comparison_id': cid, 'case_ids': comparison['case_ids'],
                     'script': source.name, 'script_sha256': sha(source),
                     'command': (f'.venv-cpu/bin/python work/{HERE.name}/compare_saved.py'
                                 f' --index $ORIGINAL_AUDIT_INDEX --expected-comparison-id {cid}'
                                 ' --output $COMPARISON_AUDIT'),
                     'source_gate': 'Closed original Native and independent delivery audits for all members required.'})
    report = {'format': 'c179789-original-comparison-audit-plan-v1',
              'assignment_id': HERE.name, 'comparisons': rows,
              'diagnostic_selected_audit_report': 'selected-audit.json',
              'diagnostic_selected_audit_sha256': sha(HERE / 'selected-audit.json'),
              'original_source_verified': False}
    (HERE / 'comparison-audit-plan.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    build()
