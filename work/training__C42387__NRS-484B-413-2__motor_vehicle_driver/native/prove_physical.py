"""Exercise three source-derived right-turn outcomes in isolated CPU fixtures."""
from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from physical_preparation import REQUIRED, assess


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))


def run(source, kind, output, scratch):
    if kind not in ('complete_motion', 'incomplete_motion', 'missing_evidence'):
        raise ValueError('Unknown physical test')
    with tempfile.TemporaryDirectory(dir=scratch, prefix='c42387-physical-') as directory:
        root = Path(directory)
        for name in REQUIRED:
            shutil.copyfile(Path(source) / name, root / name)
        if kind == 'incomplete_motion':
            for name in ('body_history.jsonl', 'native_samples.jsonl'):
                path = root / name
                rows = [json.loads(line) for line in path.read_text().splitlines()]
                for row in rows:
                    row['road_id'] = 1
                write_rows(path, rows)
        if kind == 'missing_evidence':
            (root / 'body_history.jsonl').unlink()
        assessment = assess(root)
        expected = {'complete_motion':'met', 'incomplete_motion':'not_met',
                    'missing_evidence':'unverified'}[kind]
        if assessment['status'] != expected:
            raise ValueError('Source-derived physical outcome differs: ' + assessment['status'])
        result = {'format':'c42387-physical-cpu-fixture-v1',
            'provenance_kind':'synthetic_fixture','diagnostic_fixture':True,
            'physical_checks':{'maneuver':{'status':assessment['status'],
                'method':assessment.get('engineering_completion',
                    'source-bound 600-frame body/Native turn assessment'),
                'sources':assessment['source_hashes'],
                'details':assessment['observed']}},
            'maneuver_completed':expected == 'met',
            'realized_observables':assessment['observed'] if expected == 'met' else {},
            'legal_verdict_claimed':False,
            'scope':'synthetic source-shaped CPU test; no original Native acceptance'}
        Path(output).write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
        return {'kind':kind,'status':assessment['status'],
                'source_hash_count':len(assessment['source_hashes'])}


if __name__ == '__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--kind',choices=('complete_motion','incomplete_motion','missing_evidence'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--scratch',type=Path,required=True)
    args=parser.parse_args()
    print(json.dumps(run(args.source,args.kind,args.output,args.scratch),sort_keys=True))
