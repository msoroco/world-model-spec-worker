"""Saved-source pedestrian measurements for diagnostic compatibility.

Synthetic fixture values exercise source joins only. They cannot establish a
Native site, physical crossing, legal permission, or delivery acceptance.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from native_crossing import measure, verify_site


def required(root, name):
    path = root / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return path


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sources(root, names):
    return {name: sha(required(root, name)) for name in names}


def measure_signal(facts):
    rows = facts['measurements']
    return {'green_alone_frames': [r['frame'] for r in rows if r['green_alone']],
            'facing_head': True,
            'first_entry_frame': facts['first_highway_entry']['frame'] if facts['first_highway_entry'] else None}


def measure_crosswalk(facts):
    entry = facts['first_highway_entry']
    return {'kind': facts['crosswalk_kind'],
            'entry_inside_crosswalk': entry['in_crosswalk'] if entry else None,
            'highway_entry_frame': entry['frame'] if entry else None}


def measure_device(facts):
    rows = facts['measurements']
    return {'indications_by_frame': [{'frame': r['frame'],
                                       'indication': r['other_device_indication'],
                                       'mode': r['other_device_mode']}
                                      for r in rows],
            'entry_indication': facts['first_highway_entry']['other_device_indication']
                                if facts['first_highway_entry'] else None}


def build_report(root):
    root = Path(root).resolve()
    for name in ('map.json', 'head.json', 'devices.json', 'site.json', 'frames.json'):
        required(root, name)
    site = json.loads((root / 'site.json').read_text())
    verify_site(site, root)
    facts = measure(site, root, {'path': 'frames.json', 'sha256': sha(root / 'frames.json')})
    config = json.loads(required(root, 'config.json').read_text())
    suffix = config['selected_case_id'].split('__')[-1]
    expected = config['case']['scenario_parameters']
    entry = facts['first_highway_entry']
    if facts['crosswalk_kind'] != expected['crosswalk_kind']:
        raise ValueError('Diagnostic crosswalk kind differs from selected case')
    if (entry is not None) != expected['pedestrian_enters_highway']:
        raise ValueError('Diagnostic highway entry differs from selected case')
    if entry and entry['in_crosswalk'] != expected['entry_inside_crosswalk']:
        raise ValueError('Diagnostic crossing boundary differs from selected case')
    if any(r['other_device_indication'] != expected['other_device_indication'] for r in facts['measurements']):
        raise ValueError('Diagnostic device state differs from selected case')
    measurements = {
        'c111125_signal': {'method': 'measure_signal', 'value': measure_signal(facts),
                           'sources': sources(root, ('site.json', 'head.json', 'frames.json'))},
    }
    if suffix in ('marked_cross', 'unmarked_cross', 'outside_cross'):
        measurements['c111125_crosswalk'] = {
            'method': 'measure_crosswalk', 'value': measure_crosswalk(facts),
            'sources': sources(root, ('site.json', 'map.json', 'frames.json'))}
    if suffix in ('other_device_stop', 'other_device_cross'):
        measurements['c111125_other_device'] = {
            'method': 'measure_device', 'value': measure_device(facts),
            'sources': sources(root, ('site.json', 'devices.json', 'frames.json'))}
    return {'format': 'worker-analysis-report', 'case_id': config['selected_case_id'],
            'analysis_complete': True, 'measurements': measurements,
            'provenance_kind': 'synthetic_fixture', 'diagnostic_fixture': True,
            'legal_verdict_claimed': False, 'physical_acceptance_claimed': False,
            'limitations': ['Diagnostic fixture only; Native site, capture and legal assessment remain unverified.']}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    report = build_report(args.attempt)
    Path(args.output).write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')


if __name__ == '__main__':
    main()
