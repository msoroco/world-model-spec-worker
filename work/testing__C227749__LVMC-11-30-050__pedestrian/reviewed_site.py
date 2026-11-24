"""Integrity gate for independently reviewed Native crossing-site sources.

This checks source identity and exact scene bindings. It does not decide whether
the reviewed facts are true, the crossing is physically realized, or the law
applies. Those decisions require local review of the original records.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


FACTS = ('starting_curb_xy_m', 'opposite_curb_xy_m',
         'crosswalk_boundaries_xy_m', 'roadway_highway_public_use',
         'municipal_jurisdiction', 'governing_control')


def _inside(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        raise ValueError('reviewed source path must be relative')
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or not path.is_file():
        raise ValueError('reviewed source missing or outside attempt')
    return path


def audit_reviewed_site(scene: dict, attempt: Path) -> dict:
    """Require separately reviewed original records for every physical fact."""
    attempt = Path(attempt).resolve()
    packet_path = _inside(attempt, 'reviewed-site.json')
    packet = json.loads(packet_path.read_text(encoding='utf-8'))
    if packet.get('provenance_kind') != 'reviewed_original_site':
        raise ValueError('reviewed original site provenance required')
    if packet.get('diagnostic_fixture') is not False:
        raise ValueError('diagnostic fixture cannot establish site context')
    if packet.get('case_id') != scene['case_id']:
        raise ValueError('reviewed site case mismatch')
    if packet.get('loaded_map_sha256') != scene['map_source_sha256']:
        raise ValueError('reviewed site map mismatch')
    if packet.get('starting_curb_xy_m') != scene['starting_curb_xy_m']:
        raise ValueError('reviewed starting curb differs from scene')
    if packet.get('opposite_curb_xy_m') != scene['opposite_curb_xy_m']:
        raise ValueError('reviewed opposite curb differs from scene')
    if packet.get('crosswalk_boundaries_xy_m') != scene['crosswalk_boundaries_xy_m']:
        raise ValueError('reviewed crosswalk boundaries differ from scene')
    if packet.get('roadway_highway_public_use') not in ('reviewed_public_roadway',
                                                       'reviewed_private_roadway'):
        raise ValueError('reviewed roadway/public-use finding missing')
    if packet.get('municipal_jurisdiction') not in ('reviewed_within_municipality',
                                                    'reviewed_outside_municipality'):
        raise ValueError('reviewed municipal jurisdiction finding missing')
    if packet.get('governing_control') not in ('reviewed_none', 'reviewed_device'):
        raise ValueError('reviewed governing control finding missing')
    refs = packet.get('source_refs')
    if not isinstance(refs, dict) or set(refs) != set(FACTS):
        raise ValueError('every site fact needs an exact original source')
    checked = {}
    for fact in FACTS:
        ref = refs[fact]
        if not isinstance(ref, dict) or not isinstance(ref.get('path'), str):
            raise ValueError(f'{fact} source reference malformed')
        path = _inside(attempt, ref['path'])
        if not ref['path'].startswith('reviewed-source-documents/'):
            raise ValueError(f'{fact} original source outside reviewed documents')
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != ref.get('sha256') or not path.stat().st_size:
            raise ValueError(f'{fact} original source hash/contents invalid')
        if not isinstance(ref.get('finding'), str) or not ref['finding'].strip():
            raise ValueError(f'{fact} independent finding missing')
        checked[fact] = {'path': ref['path'], 'sha256': digest}
    return {'case_id': scene['case_id'],
            'reviewed_packet_sha256': hashlib.sha256(packet_path.read_bytes()).hexdigest(),
            'source_refs': checked, 'physical_acceptance_claimed': False,
            'legal_route_classification': 'unresolved'}
