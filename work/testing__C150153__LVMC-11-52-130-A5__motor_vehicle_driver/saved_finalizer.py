"""Finalize one sealed original elevator attempt without rewriting acquisition.

Physical observations and legal applicability still require independent review.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from independent_delivery_audit import audit
from parking import CASES, measure_original_history
from reviewed_site import verify


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def finalize(attempt: Path, site_packet: Path, source_root: Path,
             *, diagnostic_fixture: bool = False, decoder=None) -> dict:
    attempt = Path(attempt).resolve()
    packet = verify(site_packet, source_root)
    if diagnostic_fixture and decoder is None:
        raise ValueError("diagnostic decoder explicitly required")
    before = {path.name: _sha(path) for path in attempt.iterdir() if path.is_file()}
    delivery = audit(attempt, site_packet, source_root,
                     diagnostic_fixture=diagnostic_fixture, decoder=decoder)
    case_id = delivery['case_id']
    prefix = packet['assignment_id'] + '__'
    if not case_id.startswith(prefix):
        raise ValueError("saved exact case differs")
    local = case_id[len(prefix):]
    case = next((item for item in CASES if item.id == local), None)
    if case is None:
        raise ValueError("saved case absent from frozen branch")
    rows = [json.loads(line) for line in (attempt / 'history.jsonl').read_text().splitlines()]
    measurements = measure_original_history(rows, packet['site'], case)
    if measurements['frame_count'] != 900:
        raise ValueError("saved original duration differs")
    after = {path.name: _sha(path) for path in attempt.iterdir() if path.is_file()}
    if before != after:
        raise ValueError("saved processing changed original acquisition")
    return {'format': 'sidewalk-elevator-saved-finalization',
            'case_id': case_id, 'site_packet_sha256': delivery['site_packet_sha256'],
            'original_acquisition_hashes': before,
            'frame_count': 900, 'observed_regions': measurements['observed_regions'],
            'observed_activities': measurements['observed_activities'],
            'min_side_gap_m': measurements['min_side_gap_m'],
            'front_overlap_frames': measurements['front_overlap_frames'],
            'five_feet_m_reference': measurements['five_feet_m_reference'],
            'physical_visibility_verified': False, 'legal_judgment': None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--site-packet', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve().is_relative_to(args.attempt.resolve()):
        raise ValueError("derived saved output must be new and outside original attempt")
    report = finalize(args.attempt, args.site_packet, args.source_root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
