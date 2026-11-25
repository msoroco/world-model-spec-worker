"""Selected C111304 measurements from sealed original Native source packets.

These are physical/context observations for later independent legal review.
No numerical threshold or willful/wanton verdict is assigned here.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from encounter import CASES
from saved_audit import finalize_saved_measurements


def _read(attempt: Path, name: str) -> tuple[dict, str]:
    path = attempt / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    raw = path.read_bytes()
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError('Source JSON decode failed: ' + name) from exc
    if not isinstance(value, dict):
        raise ValueError('Source object required: ' + name)
    return value, hashlib.sha256(raw).hexdigest()


def _source(attempt: Path, name: str) -> str:
    path = attempt / name
    if not path.is_file() or path.is_symlink():
        raise ValueError('Missing required source: ' + name)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure_access(site: dict, review: dict, source_hash: str,
                   *, allow_diagnostic: bool = False) -> dict:
    reviewed = (review.get('source_kind') == 'reviewed_original' and
                review.get('reviewed_original_source') is True and
                bool(review.get('reviewer')) and bool(review.get('source_citation')))
    diagnostic = allow_diagnostic and review.get('source_kind') == 'synthetic_fixture'
    if (site.get('public_access_basis') not in ('highway', 'public_access_premises') or
            review.get('public_access_basis') != site['public_access_basis'] or
            review.get('source_sha256') != source_hash or
            not (reviewed or diagnostic)):
        raise ValueError('original public-access source join failed')
    return {'public_access_basis': site['public_access_basis'],
            'site_id': site.get('site_id'), 'reviewer': review.get('reviewer'),
            'source_citation': review.get('source_citation'),
            'source_kind': review.get('source_kind')}


def measure_driver(saved: dict, receipt: dict) -> dict:
    return {'original_frames': saved['measurements']['frame_count'],
            'ego_speed_mps_history': saved['measurements']['ego_speed_mps_history'],
            'ego_target_speed_mps': receipt['ego_target_speed_mps'],
            'original_controls_sha256': receipt['original_packets_sha256']}


def measure_person(saved: dict, receipt: dict) -> dict:
    return {'occupant_vehicle_join': True,
            'minimum_center_distance_m': saved['measurements']['min_ego_occupant_center_distance_m'],
            'crossing_speed_mps_history': saved['measurements']['crossing_speed_mps_history'],
            'crossing_release_s': receipt['crossing_release_s']}


def measure_property(saved: dict, receipt: dict) -> dict:
    return {'minimum_center_distance_m': saved['measurements']['min_ego_property_center_distance_m'],
            'original_history_sha256': receipt['original_history_sha256']}


def analyze(attempt: Path, *, allow_diagnostic: bool = False) -> dict:
    receipt, receipt_hash = _read(attempt, 'native-receipt.json')
    site, site_hash = _read(attempt, 'site.json')
    review, review_hash = _read(attempt, 'access-review.json')
    camera_plan, _ = _read(attempt, 'camera-plan.json')
    access_hash = _source(attempt, 'access-source.txt')
    if site_hash != receipt.get('site_sha256') or site.get('public_access_review_sha256') != review_hash:
        raise ValueError('site or public-access review source hash mismatch')
    canonical_plan = json.dumps(camera_plan, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()
    if hashlib.sha256(canonical_plan).hexdigest() != receipt.get('camera_plan_sha256'):
        raise ValueError('camera plan source hash mismatch')
    case = next((case for case in CASES if receipt.get('case_id', '').endswith('__' + case.case_id)), None)
    if case is None or receipt.get('case_id') != 'testing__C111304__NRS-484B-653-1a__motor_vehicle_driver__' + case.case_id:
        raise ValueError('foreign exact case')
    if site.get('public_access_basis') != case.public_access_basis:
        raise ValueError('case and site public-access basis mismatch')
    saved = finalize_saved_measurements(attempt, case)
    shared = {'native-receipt.json': receipt_hash,
              'original-history.jsonl': _source(attempt, 'original-history.jsonl'),
              'original-packets.jsonl': _source(attempt, 'original-packets.jsonl'),
              'original-cameras.jsonl': _source(attempt, 'original-cameras.jsonl')}
    rows = (
        ('access_context', 'measure_access', measure_access(site, review, access_hash,
                                                          allow_diagnostic=allow_diagnostic),
         {'site.json': site_hash, 'access-review.json': review_hash,
          'access-source.txt': access_hash}),
        ('driver_control_history', 'measure_driver', measure_driver(saved, receipt), shared),
        ('person_encounter', 'measure_person', measure_person(saved, receipt), shared),
        ('property_encounter', 'measure_property', measure_property(saved, receipt), shared),
    )
    return {'case_id': receipt['case_id'], 'native_receipt_sha256': receipt_hash,
            'measurements': {name: {'method': method, 'value': value, 'sources': sources}
                             for name, method, value, sources in rows},
            'physical_completion': False, 'legal_judgment': None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError('analysis output already exists')
    diagnostic = False
    provenance = args.attempt / 'acquisition-provenance.json'
    if provenance.is_file() and not provenance.is_symlink():
        source = json.loads(provenance.read_text(encoding='utf-8'))
        diagnostic = source.get('provenance_kind') == 'synthetic_fixture' and source.get('diagnostic_fixture') is True
    args.output.write_text(json.dumps(analyze(args.attempt, allow_diagnostic=diagnostic),
                                          sort_keys=True, indent=2) + '\n',
                           encoding='utf-8')


if __name__ == '__main__':
    main()
