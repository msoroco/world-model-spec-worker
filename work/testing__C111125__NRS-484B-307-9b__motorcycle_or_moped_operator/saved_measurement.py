"""Saved-only join of an independent acquisition audit and signal measurement.

This accepts source-bound engineering observations, not physical or legal
acceptance. A separate media decode and pixel review remain required.
"""
from __future__ import annotations

import json
from pathlib import Path

from delivery_audit import audit_saved
from signal_exception import SourceError, measure_attempt, require, sealed, verify_site

ASSIGNMENT_ID = 'testing__C111125__NRS-484B-307-9b__motorcycle_or_moped_operator'
SUFFIXES = ('two_cycles_clear', 'one_cycle_entry', 'rolling_entry',
            'no_causal_record', 'pedestrian_crosswalk', 'lawful_traffic')
SITE_REFS = {'map': 'map_ref', 'route': 'route_ref', 'signal': 'signal_ref',
             'stop_reference': 'stop_ref', 'crosswalk': 'crosswalk_ref'}


def process_saved(site, root, manifest, output_path):
    verify_site(site, root)
    require(manifest.get('assignment_id') == ASSIGNMENT_ID, 'assignment mismatch')
    case_id = manifest.get('case_id')
    require(case_id in (ASSIGNMENT_ID + '__' + s for s in SUFFIXES), 'unknown exact case')
    for target, key in SITE_REFS.items():
        require(manifest.get('sources', {}).get(target) == site['original_sources'][site[key]],
                'site/acquisition source mismatch: ' + target)
    cause_key = site.get('cause_source_ref')
    if cause_key is not None:
        require(manifest['sources'].get('cause') == site['original_sources'][cause_key],
                'cause source mismatch')
    acquisition = audit_saved(root, manifest)
    event_ref = manifest['sources']['original_events']
    measurement = measure_attempt(site, root, event_ref)
    rows = json.loads(sealed(event_ref, root).read_text(encoding='utf-8'))
    regions = sorted({user['region'] for row in rows for user in row.get('other_users', [])
                      if user.get('region') in ('adjacent_crosswalk', 'intersection')})
    if 'adjacent_crosswalk' in regions:
        region = 'adjacent_crosswalk'
    elif 'intersection' in regions:
        region = 'intersection'
    else:
        region = 'clear'
    result = {
        'assignment_id': ASSIGNMENT_ID, 'case_id': case_id,
        'case_suffix': case_id.removeprefix(ASSIGNMENT_ID + '__'),
        'source_audit': acquisition, 'measurement': measurement,
        'other_user_region': region, 'participant_regions_observed': regions,
        'lawful_participant_status': 'unresolved',
        'physical_acceptance': False, 'legal_verdict': None,
    }
    output = Path(output_path)
    require(output.parent.resolve() == Path(root).resolve(), 'saved output must share attempt root')
    output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    return result
