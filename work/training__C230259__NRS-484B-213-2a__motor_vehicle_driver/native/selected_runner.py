"""Exact source-owned Native entrypoint for the six selected feature cases."""
import argparse
import hashlib
import json
from pathlib import Path

from draft_runner import check as check_geometry


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(bundle):
    bundle = Path(bundle)
    config = json.loads((bundle / 'config.json').read_text())
    assignment = json.loads((bundle / 'assignment-source.json').read_text())
    case = config.get('case_id')
    if not isinstance(case, str) or assignment['assignment_id'] + '__' + case.split('__')[-1] != case:
        raise ValueError('Selected case not bound to frozen assignment')
    if config.get('assignment_sha256') != sha(bundle / 'assignment-source.json') or config.get('road_sha256') != sha(bundle / 'road.xodr'):
        raise ValueError('Selected assignment or road source changed')
    if config.get('candidate_id') not in ('primary', 'fallback1'):
        raise ValueError('Unknown selected candidate')
    if config.get('original_native_observed') is not False or config.get('physical_verified') is not False:
        raise ValueError('Unreviewed physical observation claimed')
    geometry = check_geometry(config, (bundle / 'road.xodr').read_text())
    if len(config.get('supported_case_ids', [])) != 1 or config['supported_case_ids'][0] != case:
        raise ValueError('Selected exact case support differs')
    if len(config.get('required_atoms', [])) == 0 or config.get('source_packets') is None:
        raise ValueError('Missing pinned Core atom/source policy')
    return {'case_id': case, 'candidate_id': config['candidate_id'],
            'geometry': geometry, 'frames': 600,
            'native_executed': False, 'legal_verdict': None}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--check', action='store_true')
    p.add_argument('--bundle', type=Path, default=Path.cwd())
    p.add_argument('--output-dir', type=Path)
    p.add_argument('--host')
    p.add_argument('--port', type=int)
    args = p.parse_args()
    checked = check(args.bundle)
    if args.check:
        print(json.dumps(checked))
        return
    if not args.output_dir or not args.host or not args.port:
        p.error('Native output, host and port required')
    from capture_feature import execute
    execute(args.bundle, args.output_dir, args.host, args.port, checked)


if __name__ == '__main__':
    main()
