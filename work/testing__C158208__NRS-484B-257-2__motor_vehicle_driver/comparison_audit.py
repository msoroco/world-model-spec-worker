"""Independent source isolation and original-metric audit for yield comparisons."""
from __future__ import annotations

import json
from pathlib import Path

from delivery_audit import audit as delivery_audit


FIXED = ('map_opendrive', 'jurisdiction', 'intersection_geometry',
         'non_through_classification', 'all_entrance_controls', 'ego_yield_sign',
         'stop_reference', 'ego_route', 'ego_vehicle', 'other_route',
         'other_obligation', 'through_vehicle_exemption', 'sightlines',
         'officer_control', 'signal_control')


def _load(attempt, case):
    path = Path(attempt)
    custody = delivery_audit(path, case)
    site = json.loads((path / 'original-attempt/site-packet.json').read_text())
    rows = [json.loads(line) for line in
            (path / 'original-attempt/history.jsonl').read_text().splitlines() if line.strip()]
    states = [row['native_state'] for row in rows]
    entry = next((i for i, state in enumerate(states)
                  if state['ego_leading_station_m'] >= site['intersection_entry_station_m']), None)
    reference = [i for i, state in enumerate(states)
                 if state.get('traffic_reference_event') is True]
    if entry is None or len(reference) != 1:
        raise ValueError('original comparison event absent')
    return {'custody': custody, 'site': site, 'rows': rows, 'states': states,
            'entry': entry, 'reference': reference[0]}


def audit(left_attempt, right_attempt, comparison_id, left_case, right_case):
    if comparison_id not in ('occupied_vs_approaching', 'approach_station_sweep',
                             'response_vs_uninterrupted'):
        raise ValueError('unknown selected yield comparison')
    left = _load(left_attempt, left_case)
    right = _load(right_attempt, right_case)
    if left['custody']['diagnostic_fixture'] != right['custody']['diagnostic_fixture']:
        raise ValueError('comparison mixes original and synthetic provenance')
    for name in FIXED:
        if left['site']['sources'][name]['sha256'] != right['site']['sources'][name]['sha256']:
            raise ValueError('fixed reviewed source changed: ' + name)
    if left['site']['stop_reference_station_m'] != right['site']['stop_reference_station_m'] or \
            left['site']['intersection_entry_station_m'] != right['site']['intersection_entry_station_m'] or \
            left['site']['entrances'] != right['site']['entrances']:
        raise ValueError('fixed yield infrastructure changed')
    if left['custody']['original_source_sha256']['history.jsonl'] == \
            right['custody']['original_source_sha256']['history.jsonl']:
        raise ValueError('comparison reuses identical original history')
    ls = left['states']
    rs = right['states']
    if comparison_id == 'occupied_vs_approaching':
        delta = ls[left['entry']]['other_phase'] == 'within' and \
                rs[right['entry']]['other_phase'] == 'approaching' and \
                ls[left['reference']]['other_center_station_m'] != \
                rs[right['reference']]['other_center_station_m']
        held = True
    elif comparison_id == 'approach_station_sweep':
        delta = ls[left['reference']]['other_center_station_m'] != \
                rs[right['reference']]['other_center_station_m']
        held = ls[left['entry']]['other_phase'] == rs[right['entry']]['other_phase'] == 'approaching'
    else:
        delta = min(s['ego_speed_mps'] for s in ls) != min(s['ego_speed_mps'] for s in rs)
        held = ls[left['reference']]['other_center_station_m'] == \
               rs[right['reference']]['other_center_station_m'] and \
               ls[left['entry']]['other_phase'] == rs[right['entry']]['other_phase']
    if not delta or not held:
        raise ValueError('selected comparison delta or held condition not observed')
    diagnostic = left['custody']['diagnostic_fixture']
    return {'comparison_id': comparison_id, 'case_ids': [left_case, right_case],
            'fixed_source_sha256': {name: left['site']['sources'][name]['sha256']
                                    for name in FIXED},
            'left_history_sha256': left['custody']['original_source_sha256']['history.jsonl'],
            'right_history_sha256': right['custody']['original_source_sha256']['history.jsonl'],
            'diagnostic_fixture': diagnostic,
            'joint_phase_station_change': comparison_id == 'occupied_vs_approaching',
            'requested_difference_shape_observed': True,
            'requested_difference_physically_confirmed': not diagnostic,
            'legal_judgment': 'unresolved',
            'physical_acceptance_claimed': False}
