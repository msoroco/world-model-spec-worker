"""Check all five saved diagnostic receipts against their original sources."""
import argparse
import json
from pathlib import Path

from saved_delivery_gate import audit, sha


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[1]
SCRATCH = PROJECT / '.runtime-work' / 'p08-c227749-nov23'
ASSIGNMENT = ROOT.name


def main(scratch=SCRATCH, compat_prefix='compat-v4-'):
    results = []
    for construction in sorted((ROOT / 'cases').glob('*/construction.json')):
        name = construction.parent.name
        version = scratch / ('process-' + name) / 'v0001'
        attempt = scratch / (compat_prefix + name)
        result = audit(version, attempt, ASSIGNMENT + '__' + name, sha(construction))
        results.append(result)
    if len(results) != 5 or any(r['status'] != 'software_diagnostic_complete' for r in results):
        raise ValueError('five complete software diagnostics required')
    output = {'format': 'saved-delivery-diagnostic', 'assignment_id': ASSIGNMENT,
              'gate_source_sha256': sha(ROOT / 'saved_delivery_gate.py'),
              'status': 'software_diagnostic_complete', 'physical_acceptance': False,
              'legal_verdict': 'unresolved', 'cases': results}
    path = ROOT / 'saved-delivery-diagnostic.json'
    path.write_text(json.dumps(output, indent=2, sort_keys=True) + '\n')
    print(f'checked {len(results)} saved diagnostic receipts; {sum(r["original_sources_checked"] for r in results)} original hashes')
    print(f'output {path} sha256 {sha(path)}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--scratch', type=Path, default=SCRATCH)
    parser.add_argument('--compat-prefix', default='compat-v4-')
    args = parser.parse_args()
    main(args.scratch, args.compat_prefix)
