"""Check all six generated source-shaped diagnostics without physical claims."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(FOLDER))
from case_observation import SUFFIXES, audit_case
from property_route import analyze


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prove(fixture_root: Path) -> dict:
    rows = []
    for suffix in SUFFIXES:
        folder = fixture_root / suffix
        if not folder.is_dir():
            raise ValueError('diagnostic fixture missing: ' + suffix)
        map_path = folder / 'map-packet.json'
        trace_path = folder / 'trace.json'
        packet = json.loads(map_path.read_text())
        trace = json.loads(trace_path.read_text())
        if packet.get('diagnostic_fixture') is not True or trace.get('diagnostic_fixture') is not True:
            raise ValueError('explicit diagnostic provenance required')
        authority = folder / 'authority.json'
        xodr = folder / 'road.xodr'
        if (packet['source']['sha256'] != sha(authority)
                or packet['native_map']['sha256'] != sha(xodr)
                or json.loads(authority.read_text())['opendrive_sha256'] != sha(xodr)):
            raise ValueError('diagnostic source seals differ')
        case = {'case_id': trace['case_id']}
        observation = analyze(packet, trace, case)
        audited = audit_case(observation, trace, case)
        if audited['planned_case'] != suffix:
            raise ValueError('diagnostic case contrast differs')
        rows.append({'case_id': case['case_id'], 'map_sha256': sha(map_path),
                     'trace_sha256': sha(trace_path), 'authority_sha256': sha(authority),
                     'xodr_sha256': sha(xodr), 'observation': observation,
                     'case_audit': audited, 'physical_acceptance_claimed': False})
    return {'format': 'property-diagnostic-observation-proof-v1',
            'assignment_id': FOLDER.name, 'case_count': len(rows), 'cases': rows,
            'diagnostic_only': True, 'physical_acceptance_claimed': False}


if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: prove_diagnostics.py FIXTURE_ROOT OUTPUT_JSON')
    output = Path(sys.argv[2])
    output.write_text(json.dumps(prove(Path(sys.argv[1])), indent=2, sort_keys=True) + '\n')
    print(json.dumps({'passed': True, 'cases': len(SUFFIXES),
                      'diagnostic_only': True, 'physical_acceptance_claimed': False}))
