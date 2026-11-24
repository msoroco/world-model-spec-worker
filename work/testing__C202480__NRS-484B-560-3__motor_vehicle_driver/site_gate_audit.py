"""Review the retained original site packet before canonical saved processing."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from reviewed_site_gate import verify


def audit(attempt: Path, case_id: str) -> dict:
    attempt = Path(attempt).resolve()
    provenance_path = attempt / 'acquisition-provenance.json'
    if not provenance_path.is_file():
        raise ValueError('original Native acquisition provenance missing')
    provenance = json.loads(provenance_path.read_text(encoding='utf-8'))
    if (provenance.get('provenance_kind') != 'native' or
            provenance.get('diagnostic_fixture') is not False):
        raise ValueError('canonical site audit requires original Native acquisition')
    packet = attempt / 'site/packet.json'
    result = verify(packet, Path(__file__).with_name('case-plan.json'), case_id)
    result['original_acquisition_provenance_sha256'] = hashlib.sha256(
        provenance_path.read_bytes()).hexdigest()
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', required=True, type=Path)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = audit(args.attempt, args.case)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'case_id': args.case, 'original_site_review_passed': True}))


if __name__ == '__main__':
    main()
