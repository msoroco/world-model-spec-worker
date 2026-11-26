"""Exercise seven independent comparison audits on marked diagnostic sources."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from comparison_audit import audit
from native_packet import AID
from truck_following import audit_original_frames

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def run():
    plan = json.loads((HERE / 'case-plan.json').read_text(encoding='utf-8'))
    reports = {}
    for case in plan['cases']:
        case_id = case['case_id']
        name = case_id.removeprefix(AID + '__')
        source = HERE / 'diagnostics' / name / 'original-truck-history.jsonl'
        frames = [json.loads(line) for line in source.read_text(encoding='utf-8').splitlines()]
        result = audit_original_frames({'source_kind': 'sealed_native_original_frames',
            'case_id': case_id, 'frames': frames}, case_id=case_id)
        result['original_source_sha256'] = sha(source)
        reports[case_id] = result
    output = []
    for comparison in plan['comparisons']:
        name = comparison['comparison_id']
        members = [reports[case_id] for case_id in comparison['case_ids']]
        positive = audit(name, members)
        positive_path = HERE / ('comparison-' + name + '-receipt.json')
        positive_path.write_text(json.dumps(positive, indent=2) + '\n', encoding='utf-8')
        negative = [dict(row) for row in members]
        negative[1]['original_source_sha256'] = ''
        try:
            audit(name, negative)
        except ValueError as error:
            if 'source seal required' not in str(error):
                raise
            negative_error = str(error)
        else:
            raise ValueError('missing source was accepted: ' + name)
        drift = [dict(row) for row in members]
        first_fixed = positive['checks'][0]['fixed_fields_checked'][0]
        drift[1][first_fixed] = 'unrelated drift'
        try:
            audit(name, drift)
        except ValueError as error:
            if 'fixed condition drift' not in str(error):
                raise
            drift_error = str(error)
        else:
            raise ValueError('fixed-condition drift was accepted: ' + name)
        log = HERE / ('comparison-' + name + '-proof.log')
        log.write_text('diagnostic protocol positive: source-bound comparison passed\n'
                       'negative missing source: ' + negative_error + '\n'
                       'negative fixed drift: ' + drift_error + '\n', encoding='utf-8')
        output.append({'comparison_id': name, 'script': 'comparison_audit.py',
            'script_sha256': sha(HERE / 'comparison_audit.py'),
            'test_log': log.name, 'test_log_sha256': sha(log),
            'receipt': positive_path.name, 'receipt_sha256': sha(positive_path),
            'diagnostic_fixture': True, 'legal_judgment': 'unresolved'})
        print(name + ': independent positive and negative audits passed', flush=True)
    return output


if __name__ == '__main__':
    run()
