"""Read-only source-bound crossing measurement from a saved Native attempt."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from delivery_audit import audit_saved, CAMERAS

REQUIRED = ('scene.json', 'walker-body-history.jsonl', 'camera-frame-joins.jsonl',
            *(name + '.mkv' for name in CAMERAS))


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def read_attempt(attempt):
    root = Path(attempt).resolve()
    index_path = root/'acquisition.json'
    if not index_path.is_file():
        raise ValueError('Missing required source: acquisition.json')
    index = json.loads(index_path.read_text())
    sources = {}
    for name in REQUIRED:
        item = index.get(name)
        path = root/name
        if not path.is_file() or not item:
            raise ValueError('Missing required source: '+name)
        if item.get('kind') != 'original_native':
            raise ValueError('original Native source required: '+name)
        actual = sha(path)
        if item.get('sha256') != actual:
            raise ValueError('source hash mismatch: '+name)
        sources[name] = actual
    scene = json.loads((root/'scene.json').read_text())
    rows = _rows(root/'walker-body-history.jsonl')
    joins = _rows(root/'camera-frame-joins.jsonl')
    cameras = {name:index[name+'.mkv'] for name in CAMERAS}
    measurement = audit_saved(scene,rows,joins,cameras)
    diagnostic = index.get('_diagnostic_fixture', False)
    if type(diagnostic) is not bool:
        raise ValueError('diagnostic fixture marker invalid')
    return {'format':'worker-pedestrian-crossing-measurement',
            'case_id':scene['case_id'], 'measurement':measurement,
            'sources_sha256':sources, 'legal_verdict_claimed':False,
            'diagnostic_fixture':diagnostic,
            'physical_visibility':'unconfirmed_by_this_measurement'}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--attempt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    report=read_attempt(args.attempt)
    output=Path(args.output).resolve()
    if output.exists():
        raise ValueError('retain prior report; choose a new output')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    print(json.dumps({'case_id':report['case_id'],'saved_measurement_passed':True}))


if __name__=='__main__': main()
