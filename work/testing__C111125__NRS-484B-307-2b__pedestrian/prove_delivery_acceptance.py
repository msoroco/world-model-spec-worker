"""Independently audit selected diagnostic sources and reject source tampering.

This CPU proof tests the delivery audit path. It never accepts a synthetic site
as a reviewed Native location or declares physical or legal completion.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

from saved_compatibility_audit import audit

ROOT = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    parser.add_argument('--mode', choices=('positive', 'negative'), required=True)
    parser.add_argument('--scratch', type=Path, required=True)
    args = parser.parse_args()
    repo = ROOT.parents[1]
    if repo / '.runtime-work' not in args.attempt.resolve().parents or repo / '.runtime-work' not in args.scratch.resolve().parents:
        raise ValueError('CPU fixture and scratch must stay under .runtime-work')
    if ROOT not in args.receipt.resolve().parents:
        raise ValueError('selected receipt belongs to another assignment')
    suffix = args.case.removeprefix(ROOT.name + '__')
    if ROOT.name + '__' + suffix != args.case or not (ROOT / 'cases' / suffix).is_dir():
        raise ValueError('foreign exact case')
    if args.mode == 'positive':
        measured = audit(args.attempt, args.receipt)
        if measured['case_id'] != args.case or measured['frames_joined'] < 3 or measured['original_cameras'] != 4:
            raise ValueError('independent source audit incomplete')
        physical = ROOT / 'cases' / suffix
        statuses = [json.loads((physical / ('physical-' + kind + '.json')).read_text())['physical_checks']['maneuver']['status']
                    for kind in ('complete_motion', 'incomplete_motion', 'missing_evidence')]
        if statuses != ['met', 'not_met', 'unverified']:
            raise ValueError('physical classifier fixture coverage missing')
        print(json.dumps({'case_id': args.case, 'diagnostic_source_audit_passed': True,
                          'original_cameras_decoded': 4,
                          'physical_classifier_outcomes': statuses,
                          'reviewed_native_site_accepted': False,
                          'physical_acceptance_claimed': False,
                          'legal_acceptance_claimed': False}))
    else:
        target = args.scratch / (suffix + '-delivery-negative')
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(args.attempt, target)
        frames = target / 'frames.json'
        value = json.loads(frames.read_text())
        value[0]['pedestrian_xy'] = [999, 999]
        frames.write_text(json.dumps(value) + '\n')
        audit(target, args.receipt)
        raise ValueError('tampered diagnostic source was accepted')


if __name__ == '__main__':
    main()
