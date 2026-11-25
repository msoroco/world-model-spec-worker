"""Compare two source-verified saved crest attempts without a legal verdict."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from comparison_audit import COMPARISONS, audit
from saved_crest import measure, source_inventory


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def packet(attempt, audit_path, assignment, case, *, diagnostic=False):
    attempt = Path(attempt).resolve()
    manifest = attempt / ('original-hashes.json' if diagnostic else 'source-hashes.json')
    if manifest.is_symlink() or not manifest.is_file():
        raise ValueError('original source hash manifest missing')
    if diagnostic:
        provenance = attempt / 'acquisition-provenance.json'
        if not provenance.is_file() or json.loads(provenance.read_text()).get('diagnostic_fixture') is not True:
            raise ValueError('short comparison requires explicit diagnostic provenance')
        expected_frames = json.loads((attempt / 'capture/manifest.json').read_text())['frames']
    else:
        expected_frames = 900
        seal = attempt / 'capture-seal.json'
        if not seal.is_file() or not (attempt / 'native-exit.json').is_file():
            raise ValueError('production comparison requires original Native seal and exit')
        sealed = json.loads(seal.read_text())
        if any(sha(attempt / name) != checksum for name, checksum in sealed['sources'].items()):
            raise ValueError('Native seal source changed')
    hashes = json.loads(manifest.read_text())
    source_inventory(hashes, case, expected_frames)
    observation = measure(attempt, hashes, case_id=case,
                          assignment_id=assignment, expected_frames=expected_frames)
    independent = json.loads(Path(audit_path).read_text())
    if (independent.get('case_id') != case or
            independent.get('source_manifest_sha256') != sha(manifest) or
            independent.get('source_join_passed') is not True or
            independent.get('verified_frames') != expected_frames):
        raise ValueError('independent delivery audit does not bind saved attempt')
    context = json.loads((attempt / 'lane-context.json').read_text())
    profile = json.loads((attempt / 'road-profile.json').read_text())
    frames = rows(attempt / 'frames.jsonl')
    mapping = rows(attempt / 'video_frames.jsonl')
    one_way = context.get('one_way_authority') or {}
    return {
        'case_id': case, 'source_ref': sha(manifest),
        'law_id': 'NRS-484B-213-2a', 'actor': 'motor_vehicle_driver',
        'map_source': profile['map_opendrive_sha256'],
        'camera_profile': [(name, 1920 if name == 'overview' else 1280,
                            1080 if name == 'overview' else 720, 20)
                           for name in ('overview', 'approach', 'reference_corner', 'driver_reference')],
        'duration_frames': expected_frames,
        'crest_grade_sha256': digest(profile['grade_proxy']),
        'ego_route_sha256': digest([row['ego_body_corners_signed_m'] for row in frames]),
        'other_route_sha256': digest([(row.get('opposing_route_index'),
                                      row.get('opposing_body_vertices_m')) for row in frames]),
        'other_timing_sha256': digest([row['time_s'] for row in mapping]),
        'lane_allocation': context['lane_allocation'],
        'ego_left_side_observed': bool(observation['ego_body_left_side_frames']),
        'sampled_grade_blocks_proxy_ray': profile['grade_proxy']['sampled_grade_blocks_proxy_ray'],
        'one_way_authority_source_ref': one_way.get('source_ref'),
        'one_way_authority_sha256': one_way.get('sha256'),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--assignment', required=True)
    parser.add_argument('--comparison', choices=COMPARISONS, required=True)
    parser.add_argument('--first', required=True)
    parser.add_argument('--first-audit', required=True)
    parser.add_argument('--second', required=True)
    parser.add_argument('--second-audit', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    suffixes = COMPARISONS[args.comparison]['suffixes']
    first = packet(args.first, args.first_audit, args.assignment,
                   args.assignment + '__' + suffixes[0], diagnostic=args.diagnostic)
    second = packet(args.second, args.second_audit, args.assignment,
                    args.assignment + '__' + suffixes[1], diagnostic=args.diagnostic)
    result = audit(args.comparison, first, second, args.assignment)
    result.update(format='c104084-saved-comparison-audit-v1', diagnostic_fixture=args.diagnostic,
                  first_source_ref=first['source_ref'], second_source_ref=second['source_ref'],
                  physical_acceptance_claimed=False, legal_verdict_claimed=False)
    output = Path(args.output)
    if output.exists():
        raise ValueError('retain prior saved comparison audit')
    output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
