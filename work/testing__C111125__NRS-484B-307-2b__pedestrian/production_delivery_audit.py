"""Fail-closed local audit of an original pedestrian Native attempt.

This verifies saved source bindings and protocol observations. Human pixel and
legal review remain separate from this CPU receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import audit
from reviewed_site_preflight import review


ASSIGNMENT = 'testing__C111125__NRS-484B-307-2b__pedestrian'


def verify(case_id: str, attempt: Path) -> dict:
    attempt = Path(attempt).resolve(strict=True)
    if not case_id.startswith(ASSIGNMENT + '__'):
        raise ValueError('wrong exact pedestrian assignment')
    receipt = json.loads((attempt / 'capture-receipt.json').read_text())
    if receipt.get('case_id') != case_id or receipt.get('frame_count') != 900:
        raise ValueError('original 900-frame exact capture missing')
    site_path = attempt / 'site-source.json'
    site_ref = {'path': site_path.name,
                'sha256': hashlib.sha256(site_path.read_bytes()).hexdigest()}
    preflight = review(site_path, case_id)
    measured = audit(attempt, site_ref, case_id.removeprefix(ASSIGNMENT + '__'),
                     require_reviewed=True)
    if measured['frame_count'] != 900 or measured['decoded_images'] != 3600:
        raise ValueError('original camera coverage incomplete')
    if preflight['physical_acceptance'] or measured['physical_acceptance']:
        raise ValueError('software protocol asserted physical acceptance')
    return {'format': 'worker-pedestrian-production-source-audit',
            'case_id': case_id, 'site_preflight': preflight,
            'saved_protocol': measured, 'physical_acceptance': False,
            'legal_verdict': None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.case, args.attempt), sort_keys=True))


if __name__ == '__main__':
    main()
