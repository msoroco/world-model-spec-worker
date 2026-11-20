"""Compare original diagnostic business and residential district source packets."""
import argparse
import hashlib
import json
import math
from pathlib import Path

from comparison_audit import distance_and_start, load_sources, require


def district_packet(source):
    root = Path(source['root'])
    packet = json.loads((root / 'district-site-packet.json').read_text())
    document = (root / packet['source_document']).read_bytes()
    require(hashlib.sha256(document).hexdigest() == packet['source_document_sha256'],
            'District source-document hash changed')
    require(packet['district_type'] == source['route']['district_type'],
            'District packet and route disagree')
    require(source['route']['district_source_sha256'] == packet['source_document_sha256'],
            'Route district-source hash disagrees')
    return packet


def audit(left, right):
    lp, rp = district_packet(left), district_packet(right)
    require(lp['district_type'] == 'business' and rp['district_type'] == 'residential',
            'Business/residential district contrast missing')
    for name in ('road.xodr', 'drive_history.jsonl', 'body_history.jsonl',
                 'capture/evidence.jsonl'):
        require(left['hashes'][name] == right['hashes'][name], 'Fixed original source changed: ' + name)
    require(left['weather'] == right['weather'], 'Weather source changed')
    ld, ls = distance_and_start(left['drive'])
    rd, rs = distance_and_start(right['drive'])
    require(math.isclose(ld, 30.48, abs_tol=1e-7) and math.isclose(rd, 30.48, abs_tol=1e-7),
            'Common 100-foot source distance changed')
    require(ls == rs and left['route']['turn_onset_frame'] == right['route']['turn_onset_frame'],
            'Signal or turn-onset frames changed')
    return {'format': 'worker-turn-signal-source-comparison',
            'comparison_id': 'district_business_residential_100',
            'source_scope': 'saved synthetic diagnostic original sources',
            'left_source_hashes': left['hashes'], 'right_source_hashes': right['hashes'],
            'business_source_document_sha256': lp['source_document_sha256'],
            'residential_source_document_sha256': rp['source_document_sha256'],
            'left_continuous_signal_distance_m': ld, 'right_continuous_signal_distance_m': rd,
            'boundary_m': 30.48, 'software_comparison_passed': True,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--left', type=Path, required=True)
    parser.add_argument('--right', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(audit(load_sources(args.left), load_sources(args.right)), indent=2))


if __name__ == '__main__':
    main()
