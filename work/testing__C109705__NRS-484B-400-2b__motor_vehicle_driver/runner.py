"""Portable return-package preflight for C109705 departure cases.

Native execution is dispatched from each selected exact-case construction.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def check():
    config = json.loads((HERE / 'config.json').read_text())
    plan_raw = (HERE / 'case-plan.json').read_bytes()
    if hashlib.sha256(plan_raw).hexdigest() != config['plan_sha256']:
        raise ValueError('Exact package plan changed')
    plan = json.loads(plan_raw)
    cases = {item['case_id'] for item in plan['cases']}
    if set(config['supported_case_ids']) != cases or config['selected_case_id'] not in cases:
        raise ValueError('Package does not cover the exact four cases')
    if config['rate_hz'] != 20 or config['duration_s'] != 45:
        raise ValueError('Original Native time profile changed')
    return {'assignment_id': config['assignment_id'], 'case_count': len(cases),
            'selected_case_id': config['selected_case_id']}


if __name__ == '__main__':
    print(json.dumps(check(), sort_keys=True))
