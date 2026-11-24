"""Check the six planned contrasts against saved original observations.

This is a construction and comparison check, not a statutory verdict. A case
passes only when its declared difference and the fixed context were observed.
"""
from __future__ import annotations

from typing import Any

SUFFIXES = (
    'private_bypass', 'public_bypass', 'ordinary_crossing',
    'no_approach_red', 'destination_red', 'other_purpose',
)
PREFIX = 'testing__C108447__NRS-484B-307-8e__motor_vehicle_driver__'


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def audit_case(observation: dict[str, Any], trace: dict[str, Any], case: dict[str, Any]) -> dict[str, Any]:
    case_id = case.get('case_id')
    require(isinstance(case_id, str) and observation.get('case_id') == case_id,
            'exact case and observation identity required')
    suffix = next((name for name in SUFFIXES if case_id == PREFIX + name), None)
    require(suffix is not None, 'planned exact case suffix required')
    require(trace.get('actor_class') == 'vehicle' and trace.get('actor_source'),
            'fixed original vehicle source required')
    statuses = observation.get('traversed_property_statuses')
    require(isinstance(statuses, list), 'observed property inventory required')
    expected_statuses = [] if suffix == 'ordinary_crossing' else [
        'public' if suffix == 'public_bypass' else 'private'
    ]
    require(statuses == expected_statuses,
            f'{suffix} observed property traversal differs from plan')

    entry = trace.get('destination_entry_frame')
    approach = trace.get('approach_signal_history') or [trace['approach_signal']]
    movement = [row for row in approach if row['frame'] <= entry]
    require(movement and all(row.get('facing_ego') is True for row in movement),
            'fixed approach signal orientation required through entry')
    if suffix == 'no_approach_red':
        require(all(row.get('state') in ('green', 'yellow', 'dark') for row in movement),
                'non-red approach signal required through entry')
    else:
        require(observation.get('approach_red_alone_facing_ego') is True,
                'steady red alone approach required through entry')

    destination = trace.get('destination_signal', {})
    require(destination.get('facing_ego') is False,
            'fixed destination signal orientation required at entry')
    if suffix == 'destination_red':
        require(destination.get('state') in ('red_alone', 'red_combined'),
                'red destination traffic required at entry')
    else:
        require(observation.get('destination_traffic_not_facing_red') is True,
                'non-red destination traffic required at entry')

    expected_purpose = 'other' if suffix == 'other_purpose' else 'avoid_red'
    require(trace.get('purpose', {}).get('source') and trace['purpose'].get('value') == expected_purpose,
            f'{suffix} separately sourced purpose differs from plan')
    return {'format': 'property-case-observation-audit-v1',
            'case_id': case_id, 'planned_case': suffix,
            'observed_property_statuses': statuses,
            'approach_state_window': [movement[0]['frame'], movement[-1]['frame']],
            'destination_state_at_entry': destination['state'],
            'purpose_value': expected_purpose, 'physical_acceptance_claimed': False,
            'legal_judgment': None}
