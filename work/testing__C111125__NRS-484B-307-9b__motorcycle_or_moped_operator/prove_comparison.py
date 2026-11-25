"""Re-derive comparison facts from sealed saved attempts before auditing a pair."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from comparison_audit import audit_pair
from delivery_audit import audit_saved
from signal_exception import measure_attempt, verify_site


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def summary(root):
    root = Path(root).resolve()
    site_path, manifest_path = root / 'native-site.json', root / 'saved-manifest.json'
    site = json.loads(site_path.read_text(encoding='utf-8'))
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    verify_site(site, root)
    audit_saved(root, manifest)
    if site.get('case_id') != manifest['case_id']:
        raise ValueError('site and saved case identity differ')
    facts = measure_attempt(site, root, manifest['sources']['original_events'])
    rows = json.loads((root / manifest['sources']['original_events']['path']).read_text(encoding='utf-8'))
    regions = {user.get('region') for row in rows for user in row['other_users']}
    region = ('adjacent_crosswalk' if 'adjacent_crosswalk' in regions else
              'intersection' if 'intersection' in regions else 'clear')
    refs = site['original_sources']
    camera = manifest['camera_views']
    camera_profile = [(name, camera[name]['width'], camera[name]['height'], camera[name]['fps'])
                      for name in ('overview', 'approach', 'reference_corner', 'driver_reference')]
    camera_digest = hashlib.sha256(json.dumps(camera_profile, separators=(',', ':')).encode()).hexdigest()
    return {
        'case_suffix': manifest['case_id'].rsplit('__', 1)[1],
        'map_sha256': refs[site['map_ref']]['sha256'],
        'route_sha256': refs[site['route_ref']]['sha256'],
        'signal_sha256': refs[site['signal_ref']]['sha256'],
        'stop_sha256': refs[site['stop_ref']]['sha256'],
        'crosswalk_sha256': refs[site['crosswalk_ref']]['sha256'],
        'camera_profile_sha256': camera_digest,
        'duration_frames': manifest['duration_frames'],
        'official_head_id': site['official_head_id'],
        'ego_approach_id': site['ego_approach_id'],
        'actor_type_id': site['ego_blueprint_id'],
        'initial_composite_phase': facts['initial_composite_phase'],
        'entry_frame': facts['entry_frame'],
        'stopped_frame': facts['stopped_frame'],
        'full_cycles_after_stop': facts['full_cycles_after_stop'],
        'unchanged_signal_cause': facts['unchanged_signal_cause'],
        'other_user_region': region,
        'legal_permission_verdict': None, 'right_of_way_verdict': None,
        'original_sources': facts['original_sources'],
        'saved_manifest_sha256': sha(manifest_path),
        'native_site_sha256': sha(site_path),
        'original_events_sha256': manifest['sources']['original_events']['sha256'],
    }


def prove(comparison, left_root, right_root):
    left, right = summary(left_root), summary(right_root)
    result = audit_pair(comparison, left, right)
    return {'format': 'c111125-9b-source-comparison-proof',
            'comparison_id': comparison, 'passed': True,
            'left_case_suffix': left['case_suffix'], 'right_case_suffix': right['case_suffix'],
            'left_saved_manifest_sha256': left['saved_manifest_sha256'],
            'right_saved_manifest_sha256': right['saved_manifest_sha256'],
            'left_original_events_sha256': left['original_events_sha256'],
            'right_original_events_sha256': right['original_events_sha256'],
            'fixed_conditions_checked': result['fixed_conditions_checked'],
            'measured_difference': result['measured_difference'],
            'legal_verdict': None, 'physical_acceptance': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--comparison', required=True)
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    receipt = prove(args.comparison, args.left, args.right)
    if args.output.exists():
        raise ValueError('comparison output already exists')
    args.output.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
