"""Audit exact elevator comparisons from two sealed original attempts.

The comparison checks the frozen pair and controlled conditions. It does not
convert the measured five-foot geometry into a legal finding.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

from parking import CASES, audit_comparison
from reviewed_site import verify
from saved_finalizer import finalize


HERE = Path(__file__).resolve().parent
DIFFERENCE_KEY = {
    'commanded activity': 'observed_activity',
    'commanded body-to-fixture side gap': 'min_side_gap_m',
    'side of fixture': 'observed_region',
    'sourced reason for necessary stop': 'exception_source_sha256',
}
EXCEPTION_KEY = {
    'lawful_traffic_conflict': 'traffic_conflict_source_sha256',
    'police_direction': 'police_direction_source_sha256',
    'traffic_device_direction': 'traffic_device_source_sha256',
}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _record(attempt: Path, packet: dict, site_sha: str, saved: dict) -> dict:
    attempt = Path(attempt)
    context_path = attempt / 'comparison-context.json'
    seal = json.loads((attempt / 'capture-seal.json').read_text())
    context_sha = _sha(context_path)
    if (seal['sources'].get('comparison-context.json') != context_sha or
            saved['original_acquisition_hashes'].get('comparison-context.json') != context_sha):
        raise ValueError('comparison original context is not sealed')
    context = json.loads(context_path.read_text())
    case_id = saved['case_id']
    prefix = packet['assignment_id'] + '__'
    if not case_id.startswith(prefix):
        raise ValueError('comparison case assignment differs')
    case = next((item for item in CASES if item.id == case_id[len(prefix):]), None)
    if case is None:
        raise ValueError('comparison case absent')
    expected_exception = packet['site'].get(EXCEPTION_KEY[case.exception]) if case.exception != 'none' else None
    if (context.get('format') != 'sidewalk-elevator-original-comparison-context' or
            context.get('case_id') != case_id or
            context.get('site_packet_sha256') != site_sha or
            context.get('history_sha256') != saved['original_acquisition_hashes'].get('history.jsonl') or
            context.get('ego_blueprint_sha256') != packet['site']['ego_blueprint_sha256'] or
            context.get('route_sha256') != packet['site']['one_way_direction_sha256'] or
            context.get('exception_source_sha256') != expected_exception or
            not context.get('weather_sha256')):
        raise ValueError('comparison original context source differs')
    curb = context.get('curb_gap_target_m')
    if type(curb) not in (int, float) or not math.isfinite(curb) or curb < 0:
        raise ValueError('comparison curb target missing')
    site = packet['site']
    return {'case_id': case_id, 'frame_count': saved['frame_count'],
            'original_history_sha256': saved['original_acquisition_hashes']['history.jsonl'],
            'source_identity': {
                'map_sha256': site['map_sha256'],
                'fixture_identity_sha256': site['fixture_identity_sha256'],
                'fixture_geometry_sha256': site['fixture_geometry_sha256'],
                'camera_plan_sha256': site['camera_plan_sha256'],
                'municipal_jurisdiction_sha256': site['municipal_jurisdiction_sha256']},
            'camera_plan_sha256': site['camera_plan_sha256'],
            'ego_blueprint_sha256': context['ego_blueprint_sha256'],
            'weather_sha256': context['weather_sha256'],
            'route_sha256': context['route_sha256'],
            'curb_gap_target_m': curb,
            'observed_activity': saved['observed_activities'],
            'min_side_gap_m': saved['min_side_gap_m'],
            'observed_region': saved['observed_regions'],
            'exception_source_sha256': context['exception_source_sha256'],
            'comparison_context_sha256': context_sha}


def compare(comparison_id: str, left: Path, right: Path,
            site_packet: Path, source_root: Path, *,
            diagnostic_fixture: bool = False, decoder=None) -> dict:
    packet = verify(site_packet, source_root)
    plan = json.loads((HERE / 'case-plan.json').read_text())
    spec = next((row for row in plan['comparisons']
                 if row['comparison_id'] == comparison_id), None)
    if spec is None or len(spec['case_ids']) != 2 or len(spec['deliberate_differences']) != 1:
        raise ValueError('frozen comparison specification absent')
    difference = spec['deliberate_differences'][0]
    key = DIFFERENCE_KEY.get(difference)
    if key is None:
        raise ValueError('frozen comparison difference unsupported')
    site_sha = _sha(Path(site_packet))
    left_saved = finalize(left, site_packet, source_root,
                          diagnostic_fixture=diagnostic_fixture, decoder=decoder)
    right_saved = finalize(right, site_packet, source_root,
                           diagnostic_fixture=diagnostic_fixture, decoder=decoder)
    if [left_saved['case_id'], right_saved['case_id']] != spec['case_ids']:
        raise ValueError('frozen comparison exact pair differs')
    first = _record(left, packet, site_sha, left_saved)
    second = _record(right, packet, site_sha, right_saved)
    audit_comparison(first, second, key)
    return {'format': 'sidewalk-elevator-comparison-audit',
            'comparison_id': comparison_id, 'case_ids': spec['case_ids'],
            'site_packet_sha256': site_sha, 'deliberate_difference': difference,
            'observed_difference_key': key,
            'original_history_sha256': [first['original_history_sha256'],
                                        second['original_history_sha256']],
            'comparison_context_sha256': [first['comparison_context_sha256'],
                                          second['comparison_context_sha256']],
            'fixed_conditions_checked': spec['fixed_conditions'],
            'legal_judgment': None, 'physical_acceptance_claimed': False}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison-id', required=True)
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    parser.add_argument('--site-packet', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('comparison audit output already exists')
    result = compare(args.comparison_id, args.left, args.right,
                     args.site_packet, args.source_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
