"""Source-bound qualitative observation review; never decides statutory safety."""

import argparse
import hashlib
import json
from pathlib import Path


def require(value, message):
    if not value:
        raise ValueError(message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def review(contract_path, attempt, declaration_path, diagnostic=False):
    contract = json.loads(Path(contract_path).read_text())
    declaration = json.loads(Path(declaration_path).read_text())
    root = Path(attempt).resolve()
    manifest = json.loads((root / 'original-sources.json').read_text())
    expected_kind = 'synthetic_fixture' if diagnostic else 'original_native_capture'
    require(manifest.get('source_kind') == expected_kind,
            'reviewed original source kind missing')
    if not diagnostic:
        require(manifest.get('accepted_original_source') is True and
                manifest.get('reviewed_scene_packet_sha256'),
                'reviewed original capture acceptance missing')
    require(manifest.get('frame_count') == 900,
            'complete 900-frame source manifest missing')
    config = json.loads((root / 'config.json').read_text())
    source_case = config.get('selected_case_id')
    require(declaration.get('case_id') and
            declaration.get('case_id') == source_case and
            (not manifest.get('case_id') or manifest['case_id'] == source_case),
            'review case/source identity differs')
    require(declaration.get('legal_verdict') is None,
            'qualitative observation cannot declare a legal verdict')
    refs = {}
    for field in contract['required_sources']:
        digest = manifest.get('files', {}).get(field, {}).get('sha256')
        candidate = root / field
        source = candidate.resolve()
        require(not candidate.is_symlink() and source.is_relative_to(root) and source.is_file() and
                digest == sha(source), 'missing or changed original source: ' + field)
        refs[field] = digest
    reviews = {}
    for spec in contract['sweeps']:
        item = declaration.get('observations', {}).get(spec['sweep_id'])
        require(isinstance(item, dict), 'qualitative observation missing: ' + spec['sweep_id'])
        require(item.get('status') in ('observed', 'uncertain', 'not_observed'),
                'qualitative observation status missing')
        require(item.get('reviewer') and item.get('reason') and
                item.get('interval_frames') and len(item['interval_frames']) == 2,
                'reviewer, reason and interval required')
        lo, hi = item['interval_frames']
        require(type(lo) is int and type(hi) is int and 0 <= lo <= hi < 900,
                'review interval outside recorded frames')
        require(set(item.get('source_refs', [])) >= set(spec['source_refs']),
                'qualitative source reference missing')
        require(item.get('legal_verdict') is None,
                'qualitative observation cannot declare a legal verdict')
        reviews[spec['sweep_id']] = {'status': item['status'],
                                     'reviewer': item['reviewer'],
                                     'reason': item['reason'],
                                     'interval_frames': [lo, hi],
                                     'source_refs': item['source_refs']}
    return {'format': 'c229023-qualitative-source-review',
            'case_id': declaration['case_id'],
            'contract_sha256': sha(contract_path),
            'source_manifest_sha256': sha(root / 'original-sources.json'),
            'source_hashes': refs, 'observations': reviews,
            'diagnostic_fixture': diagnostic, 'legal_verdict': None,
            'physical_acceptance_claimed': False}


def compare(plan_path, left_path, right_path, comparison_id):
    plan = json.loads(Path(plan_path).read_text())
    matches = [x for x in plan['comparisons'] if x['comparison_id'] == comparison_id]
    require(len(matches) == 1, 'comparison plan missing')
    left = json.loads(Path(left_path).read_text())
    right = json.loads(Path(right_path).read_text())
    pair = matches[0]['case_ids']
    require(left['case_id'] == pair[0] and right['case_id'] == pair[1] and
            left['case_id'] != right['case_id'], 'comparison cases differ')
    require(left['contract_sha256'] == right['contract_sha256'] and
            left['legal_verdict'] is None and right['legal_verdict'] is None,
            'comparison source contract or legal status differs')
    require(left.get('source_manifest_sha256') and
            right.get('source_manifest_sha256') and
            left.get('source_hashes') and right.get('source_hashes') and
            set(left.get('observations', {})) == {'c229023-0', 'c229023-1'} and
            set(right.get('observations', {})) == {'c229023-0', 'c229023-1'},
            'comparison lacks source-bound qualitative observations')
    require(matches[0].get('deliberate_differences') is not None,
            'comparison difference missing')
    return {'comparison_id': comparison_id,
            'case_ids': pair,
            'declared_differences': matches[0]['deliberate_differences'],
            'review_source_hashes': [left['source_manifest_sha256'],
                                     right['source_manifest_sha256']],
            'observed_statuses': {
                sweep: [left['observations'][sweep]['status'],
                        right['observations'][sweep]['status']]
                for sweep in ('c229023-0', 'c229023-1')},
            'legal_verdict': None}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--contract', type=Path, required=True)
    parser.add_argument('--attempt', type=Path, required=True)
    parser.add_argument('--declaration', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--diagnostic', action='store_true')
    args = parser.parse_args()
    result = review(args.contract, args.attempt, args.declaration,
                    diagnostic=args.diagnostic)
    require(not args.output.exists(), 'retain prior source review')
    args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
