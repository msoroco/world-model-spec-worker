"""Bind an independent original pixel review to exact-case motion measurements."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from parking import CASES
from physical_outcomes import evaluate
from physical_review import review
from reviewed_site import verify


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(attempt: Path, site_packet: Path, source_root: Path,
            reviewer_packet: Path, reviewer_sha256: str,
            *, diagnostic_fixture: bool = False) -> dict:
    attempt = Path(attempt).resolve()
    site_packet = Path(site_packet).resolve()
    packet = verify(site_packet, source_root)
    before = {path.name: _sha(path) for path in attempt.iterdir() if path.is_file()}
    seal_path = attempt / ('capture-seal.json' if diagnostic_fixture else 'delivery-seal.json')
    if not seal_path.is_file():
        raise ValueError('physical preparation original Native provenance and delivery seal required')
    seal = json.loads(seal_path.read_text())
    if seal.get('provenance_kind') != ('synthetic_fixture' if diagnostic_fixture else 'original_native'):
        raise ValueError('physical preparation original Native provenance required')
    if seal.get('site_packet_sha256') != _sha(site_packet):
        raise ValueError('physical preparation site source differs')
    history = attempt / 'history.jsonl'
    if seal.get('sources', {}).get('history.jsonl') != _sha(history):
        raise ValueError('physical preparation sealed history differs')
    reviewed = review(attempt, site_packet, source_root, reviewer_packet,
                      reviewer_sha256, diagnostic_fixture=diagnostic_fixture)
    case_id = seal.get('case_id')
    if reviewed.get('case_id') != case_id or reviewed.get('source_hashes') != seal['sources']:
        raise ValueError('physical preparation review binding differs')
    prefix = packet['assignment_id'] + '__'
    if not isinstance(case_id, str) or not case_id.startswith(prefix):
        raise ValueError('physical preparation exact case differs')
    case = next((item for item in CASES if item.id == case_id[len(prefix):]), None)
    if case is None:
        raise ValueError('physical preparation exact case missing')
    rows = [json.loads(line) for line in history.read_text().splitlines()]
    outcome = evaluate(case, rows, packet['site'], _sha(history), _sha(site_packet),
                       diagnostic_fixture=diagnostic_fixture)
    if outcome['physical_checks']['maneuver']['status'] != 'met':
        raise ValueError('physical preparation exact maneuver not met')
    after = {path.name: _sha(path) for path in attempt.iterdir() if path.is_file()}
    if before != after:
        raise ValueError('physical preparation changed original acquisition')
    return {'format': 'sidewalk-elevator-physical-preparation',
            'case_id': case_id, 'site_packet_sha256': _sha(site_packet),
            'reviewer_packet_sha256': reviewer_sha256,
            'original_acquisition_hashes': after,
            'physical_checks': outcome['physical_checks'],
            'realized_observables': outcome['realized_observables'],
            'provenance_kind': outcome['provenance_kind'],
            'diagnostic_fixture': diagnostic_fixture,
            'original_pixel_review_joined': not diagnostic_fixture,
            'legal_judgment': None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--site-packet', type=Path, required=True)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--reviewer-packet', type=Path, required=True)
    parser.add_argument('--reviewer-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists() or args.output.resolve().is_relative_to(args.attempt.resolve()):
        raise ValueError('physical preparation output must be new and outside original attempt')
    result = prepare(args.attempt, args.site_packet, args.source_root,
                     args.reviewer_packet, args.reviewer_sha256)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')


if __name__ == '__main__':
    main()
