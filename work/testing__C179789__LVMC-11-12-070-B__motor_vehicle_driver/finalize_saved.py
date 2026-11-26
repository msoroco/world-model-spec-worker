"""Measure a closed original two-actor capture without replaying Native control."""
import argparse
import hashlib
import json
from pathlib import Path

from original_runner import load_reviewed_site
from through_highway import ASSIGNMENT, measure


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def finalize(attempt, case_id, output):
    attempt, output = Path(attempt), Path(output)
    if not attempt.is_dir() or attempt.is_symlink():
        raise ValueError('closed original attempt missing')
    seal_path = attempt / 'capture-seal.json'
    if not seal_path.is_file() or seal_path.is_symlink():
        raise ValueError('closed original Native seal missing')
    seal = json.loads(seal_path.read_text())
    if (seal.get('case_id') != case_id or seal.get('provenance_kind') != 'native' or
            seal.get('diagnostic_fixture') is not False or seal.get('frames') != 900 or
            seal.get('events') != ['capture_finished', 'encoders_closed', 'restoration_verified']):
        raise ValueError('original capture identity or closure changed')
    for relative, digest in seal.get('sources', {}).items():
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts or not (attempt / path).is_file() or sha(attempt / path) != digest:
            raise ValueError('sealed original source changed: ' + relative)
    manifest_path = attempt / 'reviewed-site/source-manifest.json'
    site_path = attempt / 'reviewed-site/site-context.json'
    if sha(manifest_path) != seal.get('reviewed_manifest_sha256') or sha(site_path) != seal.get('reviewed_site_sha256'):
        raise ValueError('reviewed original source packet changed')
    site = load_reviewed_site(manifest_path, site_path, case_id)
    history = attempt / 'history.jsonl'
    if sha(history) != seal['sources'].get('history.jsonl'):
        raise ValueError('original two-actor history source changed')
    rows = [json.loads(line) for line in history.read_text().splitlines()]
    if len(rows) != 900:
        raise ValueError('original 900-frame history incomplete')
    name = case_id.removeprefix(ASSIGNMENT + '__')
    measurement = measure(site, name, site['map_sha256'], rows)
    result = {'format': 'c179789-original-saved-measurement-v1', 'case_id': case_id,
              'capture_seal_sha256': sha(seal_path), 'reviewed_site_sha256': sha(site_path),
              'history_sha256': sha(history), 'measurement': measurement,
              'physical_visibility_verified': False, 'antecedent_legal_review': 'unresolved',
              'right_of_way_legal_review': 'unresolved'}
    if output.exists():
        raise ValueError('retain prior saved measurement')
    output.write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--case', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    finalize(args.attempt, args.case, args.output)


if __name__ == '__main__':
    main()
