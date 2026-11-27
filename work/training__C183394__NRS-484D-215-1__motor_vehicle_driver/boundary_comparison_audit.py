"""Independent recorded-source audit for the three 500-foot setup probes.

A passing audit verifies comparable sources and ordered measured starts. It does
not establish an exact statutory boundary frame or a legal lighting outcome.
"""
import argparse
import json
from math import hypot
from pathlib import Path
import sys

from comparison_audit import FIXED_CONFIG, require_delivery, sha
sys.path.insert(0, str(Path(__file__).resolve().parent / 'native'))
from saved_beam import load_rows, measure_saved, source


ORDER = ('distance_below_500ft', 'distance_at_500ft', 'distance_above_500ft')
PLANNED_FT = (499, 500, 501)
FIXED_SOURCE = ('road.xodr', 'road-position-source.json',
                'lighting-trigger-source.json', 'eye-region-source.json')


def check_triplet(attempts):
    roots = [Path(a).resolve() for a in attempts]
    if len(roots) != 3:
        raise ValueError('Three original boundary attempts required')
    measurements = [measure_saved(root) for root in roots]
    ids = [item['case_id'] for item in measurements]
    if [case.rsplit('__', 1)[-1] for case in ids] != list(ORDER):
        raise ValueError('Exact 499/500/501-foot case order differs')
    prefix = ids[0].rsplit('__', 1)[0]
    if any(case.rsplit('__', 1)[0] != prefix for case in ids):
        raise ValueError('Boundary probes changed assignment')
    if any(item['source_sha256'][name] != measurements[0]['source_sha256'][name]
           for item in measurements[1:] for name in FIXED_SOURCE):
        raise ValueError('Boundary fixed road/trigger/eye source differs')
    configs = [json.loads(source(root, 'config.json').read_text()) for root in roots]
    if any(config.get('beam_mode') != 'dim_within_500' or
           any(config.get(key) != configs[0].get(key) for key in FIXED_CONFIG)
           for config in configs):
        raise ValueError('Boundary probe fixed configuration differs')
    rows = [load_rows(source(root, 'beam-rows.jsonl')) for root in roots]
    if any(len(trace) != 600 for trace in rows):
        raise ValueError('Boundary probe frame count differs')
    starts = [hypot(trace[0]['ego_x_m']-trace[0]['oncoming_x_m'],
                    trace[0]['ego_y_m']-trace[0]['oncoming_y_m'])/.3048
              for trace in rows]
    if not starts[0] < starts[1] < starts[2]:
        raise ValueError('Measured starting range order differs')
    if not starts[0] < 500 < starts[2]:
        raise ValueError('Measured starts do not bracket 500 feet')
    if any(abs(actual-planned) > 1 for actual,planned in zip(starts,PLANNED_FT)):
        raise ValueError('Physical setup differs from authored foot targets')
    return {'comparison_id': prefix+'__distance_500ft_boundary_comparison',
            'case_ids': ids, 'planned_start_distance_ft': list(PLANNED_FT),
            'measured_start_distance_ft': starts,
            'original_500ft_boundary_sample_confirmed': False,
            'physical_glare_conclusion': None, 'legal_verdict_claimed': False}


def audit_triplet(attempts, audits, output):
    value = check_triplet(attempts)
    receipts = [require_delivery(path, audit, case)
                for path,audit,case in zip(attempts,audits,value['case_ids'])]
    recording_ids = [item['recording_id'] for item in receipts]
    if len(set(recording_ids)) != 3:
        raise ValueError('Boundary probes require three distinct original recordings')
    target = Path(output).resolve()
    if target.exists():
        raise ValueError('Retain prior boundary comparison audit')
    target.parent.mkdir(parents=True, exist_ok=True)
    value.update(format='worker-comparison-audit',passed=True,
                 recording_ids=recording_ids,
                 delivery_audit_sha256=[sha(path) for path in audits])
    target.write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
    return value


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for suffix in ('below', 'at', 'above'):
        parser.add_argument('--attempt-'+suffix, required=True)
        parser.add_argument('--delivery-'+suffix, required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    attempts = [getattr(args,'attempt_'+suffix) for suffix in ('below','at','above')]
    audits = [getattr(args,'delivery_'+suffix) for suffix in ('below','at','above')]
    print(json.dumps(audit_triplet(attempts,audits,args.output),indent=2))
