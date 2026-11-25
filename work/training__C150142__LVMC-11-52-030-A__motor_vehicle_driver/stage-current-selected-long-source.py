"""Stage an unchanged retained synthetic acquisition into a current selected attempt."""
import argparse
import hashlib
import json
import os
from pathlib import Path


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for part in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--source', required=True)
    parser.add_argument('--attempt', required=True)
    parser.add_argument('--proof', required=True)
    args = parser.parse_args()
    source, attempt, proof = (Path(p).resolve() for p in (args.source, args.attempt, args.proof))
    repo = Path(__file__).resolve().parents[2]
    scratch = (repo / '.runtime-work').resolve()
    if scratch not in source.parents or scratch not in attempt.parents or scratch not in proof.parents:
        raise ValueError('All source, attempt and proof paths must be under .runtime-work')
    if source == attempt or not attempt.is_dir() or proof.exists():
        raise ValueError('Use a fresh materialized selected attempt and proof')
    old = json.loads((source / 'config.json').read_text())
    new = json.loads((attempt / 'config.json').read_text())
    if old != new or new['selected_case_id'] != json.loads((attempt / 'construction.json').read_text())['case_id']:
        raise ValueError('Retained synthetic source config differs from selected case')
    count = 0
    for root in source.iterdir():
        if root.name in ('channels', 'traffic_spec', 'converted', 'result.json', 'analysis-report.json'):
            continue
        if (attempt / root.name).exists():
            continue
        if root.is_symlink():
            raise ValueError('Source symlink is not permitted')
        if root.is_file():
            os.link(root, attempt / root.name)
            count += 1
        elif root.is_dir():
            for p in root.rglob('*'):
                if p.is_symlink():
                    raise ValueError('Source symlink is not permitted')
                q = attempt / p.relative_to(source)
                if p.is_dir():
                    q.mkdir(parents=True, exist_ok=True)
                elif p.is_file():
                    q.parent.mkdir(parents=True, exist_ok=True)
                    os.link(p, q)
                    count += 1
    required = ('trace.jsonl', 'video_frames.jsonl', 'native-raw-actors.jsonl',
                'statutory-context.json', 'native-map-readback.json', 'raw.mkv',
                'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
                'driver_reference.mkv', 'capture/manifest.json',
                'capture/evidence.jsonl', 'capture/native/frames.jsonl')
    for name in required:
        if not (attempt / name).is_file() or sha(attempt / name) != sha(source / name):
            raise ValueError('Missing or changed source: ' + name)
    rows = sum(1 for _ in (attempt / 'trace.jsonl').open())
    if rows != new['capture_frames'] or sum(1 for _ in (attempt / 'video_frames.jsonl').open()) != rows:
        raise ValueError('Selected frame schedule differs from retained source')
    receipt = {'format': 'c150142-current-selected-long-source-staging-v1',
               'case_id': new['selected_case_id'], 'source': str(source),
               'attempt': str(attempt), 'frame_count': rows,
               'linked_source_files': count,
               'required_source_sha256': {name: sha(attempt / name) for name in required},
               'original_native_observed': False, 'synthetic_native_sample': True}
    proof.write_text(json.dumps(receipt, sort_keys=True, separators=(',', ':')))
    print(json.dumps({'proof_sha256': sha(proof), 'frames': rows, 'linked_files': count}, sort_keys=True))


if __name__ == '__main__':
    main()
