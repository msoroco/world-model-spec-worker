"""Clone a synthetic compatibility attempt for a frozen-manifest saved test."""

import argparse
import hashlib
import json
import shutil
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--side', choices='ab', required=True)
    parser.add_argument('--candidate', choices=('primary', 'fallback1'), required=True)
    args = parser.parse_args()
    source = ROOT / f'.runtime-work/c230259-297-2-compat-{args.side}-{args.candidate}-final'
    destination = ROOT / f'.runtime-work/c230259-297-2-saved-source-{args.side}-{args.candidate}-final'
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    selected = destination / 'candidate-selection.json'
    receipt = json.loads(selected.read_text())
    receipt['manifest_sha256'] = hashlib.sha256((BASE / 'execution-manifest.json').read_bytes()).hexdigest()
    selected.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'synthetic_source': str(source), 'saved_source': str(destination),
                      'candidate_id': args.candidate, 'physical_native_source': False}))


if __name__ == '__main__':
    main()
