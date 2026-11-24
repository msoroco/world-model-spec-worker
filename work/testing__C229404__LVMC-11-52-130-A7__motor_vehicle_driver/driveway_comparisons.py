"""Independent source-bound audits of the eleven planned driveway contrasts.

Inputs are saved original observation packets. A diagnostic fixture or an
authored target value cannot establish a measured contrast or legal result.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from driveway_measurements import measure

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.name
VARIABLES = ('driveway_kind', 'activity', 'position_target',
             'driver_relationship', 'necessity_or_postal_context')
DIFFERENCE = {
    'five-foot spatial boundary': ('position_target',),
    'frontage versus nearby boundary': ('position_target',),
    'owner exception': ('driver_relationship',),
    'parking-only private exception': ('activity',),
    'family exception': ('driver_relationship',),
    'invitee exception': ('driver_relationship',),
    'official postal business': ('necessity_or_postal_context',),
    'necessary traffic conflict, same stop activity': ('necessity_or_postal_context',),
    'device direction, same stand activity': ('necessity_or_postal_context',),
    'police direction, same park activity': ('necessity_or_postal_context',),
    'necessary legal compliance, same park activity': ('necessity_or_postal_context',),
}
FIXED = ('map_sha256', 'driveway_mouth_sha256', 'driveway_frontage_sha256',
         'vehicle_body_spec_sha256', 'camera_profile_sha256',
         'capture_rate_hz', 'responsible_person_id', 'jurisdiction_id')


def _require(ok, message):
    if not ok:
        raise ValueError(message)


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _source(packet, name):
    source = packet.get('condition_sources', {}).get(name)
    _require(isinstance(source, dict) and source.get('path') and source.get('sha256'),
             'source record required for ' + name)
    path = Path(source['path'])
    _require(path.is_file() and _sha(path) == source['sha256'],
             'source bytes changed for ' + name)
    return source, path


def _verified_measurement(packet):
    paths = {}
    for name in ('context', 'trace', 'receipt', 'map'):
        ref = packet.get('source_files', {}).get(name)
        _require(isinstance(ref, dict) and ref.get('path') and ref.get('sha256'),
                 'original measurement file required: ' + name)
        path = Path(ref['path'])
        _require(path.is_file() and _sha(path) == ref['sha256'],
                 'original measurement source changed: ' + name)
        paths[name] = path
    actual = measure(packet['case_id'], paths['context'], paths['trace'],
                     paths['receipt'], paths['map'])
    _require(packet.get('measurement') == actual,
             'saved original measurement differs from source bytes')
    return actual


def audit(comparison_id: str, left: dict, right: dict, plan: dict | None = None) -> dict:
    """Check one exact pair without deciding a statutory exception or verdict."""
    if plan is None:
        plan = json.loads((HERE / 'case-plan.json').read_text())
    selected = [c for c in plan['comparisons'] if c['isolated_question'] == comparison_id]
    _require(len(selected) == 1 and comparison_id in DIFFERENCE,
             'unknown or duplicate exact comparison')
    comparison = selected[0]
    _require([left.get('case_id'), right.get('case_id')] == comparison['case_ids'],
             'exact pair and order required')
    _require(comparison['deliberate_differences'] == [comparison_id],
             'planned deliberate difference changed')
    planned = {c['case_id']: c for c in plan['cases']}
    changed = set(DIFFERENCE[comparison_id])
    for packet in (left, right):
        case_id = packet['case_id']
        _require(case_id.startswith(ASSIGNMENT + '__') and case_id in planned,
                 'case absent from exact plan')
        _require(packet.get('source_kind') == 'original_native_capture' and
                 packet.get('diagnostic_fixture') is False,
                 'original source packet required')
        actual = _verified_measurement(packet)
        _require(actual.get('case_id') == case_id and
                 actual.get('physical_acceptance') == 'unverified',
                 'exact source-bound measurement required')
        seals = actual.get('source_bindings', {})
        _require(all(isinstance(seals.get(k), str) and len(seals[k]) == 64
                     for k in ('context_sha256', 'trace_sha256', 'receipt_sha256',
                               'native_map_sha256')),
                 'map/context/trace/receipt source seals required')
        _require(packet.get('map_sha256') == seals['native_map_sha256'],
                 'map source seal differs from measurement')
        _require(packet.get('capture_rate_hz') == 20,
                 'common original 20 Hz capture protocol required')
        conditions = packet.get('observed_conditions', {})
        _require(set(conditions) == set(VARIABLES), 'five observed conditions required')
        for key in VARIABLES:
            _require(conditions[key] == planned[case_id][key],
                     'observed condition differs from exact planned contrast: ' + key)
            _, path = _source(packet, key)
            source_value = json.loads(path.read_text())
            _require(source_value == {'name': key, 'value': conditions[key],
                                      'source_kind': 'original_reviewed_record'},
                     'condition source value differs: ' + key)
        _require(actual.get('activity_window', {}).get('state') == conditions['activity'],
                 'settled original activity differs from source condition')
        _require(actual.get('driveway_kind') == conditions['driveway_kind'],
                 'measured driveway class differs from source condition')
        _require(isinstance(packet.get('observed_full_footprint_distance_m'), (int, float)) and
                 packet['observed_full_footprint_distance_m'] == actual.get('minimum_observed_full_footprint_to_mouth_m'),
                 'original full-footprint distance binding required')
        for key in FIXED:
            _require(packet.get(key) not in (None, '', []), 'fixed source condition absent: ' + key)
            if key.endswith('_sha256'):
                _source(packet, key)
    for key in FIXED:
        _require(left[key] == right[key], 'undeclared fixed condition changed: ' + key)
    for key in VARIABLES:
        if key in changed:
            _require(left['observed_conditions'][key] != right['observed_conditions'][key],
                     'declared difference not observed: ' + key)
        else:
            _require(left['observed_conditions'][key] == right['observed_conditions'][key],
                     'undeclared observed condition changed: ' + key)
            _require(left['condition_sources'][key]['sha256'] == right['condition_sources'][key]['sha256'],
                     'fixed condition source changed: ' + key)
    if comparison_id == 'five-foot spatial boundary':
        _require(left['observed_full_footprint_distance_m'] <= 1.524 and
                 right['observed_full_footprint_distance_m'] > 1.524,
                 'settled full-footprint distance does not bracket five feet')
    return {'format': 'saved-driveway-comparison-audit-v1',
            'comparison_id': comparison_id,
            'case_ids': comparison['case_ids'],
            'fixed_conditions_checked': list(FIXED) + sorted(set(VARIABLES) - changed),
            'deliberate_differences_observed': list(changed),
            'source_seals_checked': True,
            'five_feet_m_reference_only': 1.524,
            'legal_judgment': None, 'physical_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('comparison', 'left', 'right', 'output'):
        parser.add_argument('--' + name, required=True)
    args = parser.parse_args()
    left = json.loads(Path(args.left).read_text())
    right = json.loads(Path(args.right).read_text())
    result = audit(args.comparison, left, right)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
