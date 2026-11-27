"""Measure the restricted-street facts from sealed Native and cited context."""
import hashlib
import json
import sys
from pathlib import Path

from source_contract import load

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from restriction_measure import measure


def evaluate(attempt: Path, case_id: str) -> dict:
    packet = load(attempt, case_id)
    facts = dict(packet['context'].get('facts', {}))
    facts['source_kind'] = packet['source_kind']
    facts['observed_speed_mps'] = max(row['ego_speed_mps'] for row in packet['rows'])
    refs = packet['context']['authority_refs']
    facts['weight_source_ref'] = refs['weight']['path']
    facts['route_source_ref'] = refs['truck_route']['path']
    raw = json.dumps(facts, sort_keys=True, allow_nan=False).encode()
    result = measure(raw, hashlib.sha256(raw).hexdigest())
    return {'format': 'c394566-source-bound-measurement-v1', 'case_id': case_id,
            'factual_measurements': result, 'rows': packet['rows'], 'context': packet['context'], 'source_kind': packet['source_kind'],
            'source_hashes': packet['source_hashes'],
            'authority_hashes': packet['authority_hashes'],
            'original_authority_reviewed': False,
            'physical_or_legal_accepted': False}
