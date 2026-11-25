"""Original-source finalization for the directed-officer comparison case."""
import argparse
import json
from pathlib import Path

import base_finalize

CASE = base_finalize.AID + '__officer_directed'


def source_joined_same_direction_abreast_and_order(measured):
    return base_finalize.source_joined_same_direction_abreast_and_order(measured)


def check_context(source_dir, case_id, diagnostic):
    if case_id != CASE:
        raise ValueError('Exact directed-officer case required')
    context = json.loads((Path(source_dir) / 'emergency_context.json').read_text())
    if context.get('case_id') != CASE or context.get('officer_directed_otherwise') is not True:
        raise ValueError('Reviewed officer direction absent from exact source context')
    if not diagnostic:
        if context.get('review_kind') != 'original_source_review':
            raise ValueError('Original officer direction review required')
        sources = context.get('officer_instruction_sources')
        keys = ('officer_instruction_source', 'officer_identity_source',
                'officer_instruction_text', 'officer_instruction_recipient',
                'officer_instruction_timing_source', 'officer_instruction_reviewer')
        if not isinstance(sources, dict):
            raise ValueError('Original officer instruction sources missing')
        for key in keys:
            value = sources.get(key)
            if not isinstance(value, str) or not value or value.startswith('synthetic-fixture:'):
                raise ValueError('Original officer instruction source missing: ' + key)
    return context


def finalize(source_dir, case_id, output, *, diagnostic=False):
    check_context(source_dir, case_id, diagnostic)
    base_finalize.CASES += (CASE,)
    try:
        return base_finalize.finalize(source_dir, case_id, output,
                                      diagnostic=diagnostic)
    finally:
        base_finalize.CASES = base_finalize.CASES[:-1]


def finalize_attempt(attempt, output):
    cfg = json.loads((Path(attempt) / 'config.json').read_text())
    check_context(attempt, cfg.get('case_id'),
                  diagnostic=json.loads((Path(attempt) / 'emergency_context.json').read_text()).get('review_kind') == 'synthetic_diagnostic')
    base_finalize.CASES += (CASE,)
    try:
        return base_finalize.finalize_attempt(attempt, output)
    finally:
        base_finalize.CASES = base_finalize.CASES[:-1]


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path)
    parser.add_argument('--source-dir', type=Path)
    parser.add_argument('--case')
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    if args.attempt:
        print(json.dumps(finalize_attempt(args.attempt, args.output), sort_keys=True))
    else:
        if not args.source_dir or not args.case:
            parser.error('--source-dir and --case are required without --attempt')
        print(json.dumps(finalize(args.source_dir, args.case, args.output,
                                  diagnostic=args.diagnostic), sort_keys=True))
