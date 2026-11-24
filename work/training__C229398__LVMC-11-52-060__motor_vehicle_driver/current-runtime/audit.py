"""Independent source and comparison audit for current synthetic CPU proofs."""
import argparse
import hashlib
import json
from pathlib import Path


HERE = Path(__file__).resolve().parent
PACKAGE = HERE.parent
REPO = PACKAGE.parents[1]
MANIFEST = PACKAGE / 'execution-manifest.json'
GROUPS = ('below_15_ft', 'at_15_ft', 'above_15_ft')
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def audit(proof_directory, scratch_root):
    manifest = read(MANIFEST)
    manifest_sha = sha(MANIFEST)
    runtime_sha = sha(REPO / 'runtime/SOURCE-MANIFEST.json')
    require(manifest['runtime_manifest_sha256'] == runtime_sha, 'Runtime changed')
    by_group = {entry['case_id'].rsplit('__', 1)[-1]: entry for entry in manifest['cases']}
    require(set(by_group) == set(GROUPS), 'Selected case set differs')
    rows = []
    fixed = {}
    for group in GROUPS:
        entry = by_group[group]
        for candidate in CANDIDATES:
            selected = entry if candidate == 'primary' else next(row for row in entry['candidates'] if row['id'] == candidate)
            prefix = f'{group}-{candidate}'
            proof_path = proof_directory / f'{prefix}-proof.json'
            proof = read(proof_path)
            offline = read(proof_directory / f'{prefix}-offline.json')
            selection = read(proof_directory / f'{prefix}-selection.json')
            positive = read(proof_directory / f'{prefix}-compatibility.json')
            negative_path = proof_directory / f'{prefix}-negative.log'
            saved = read(proof_directory / f'{prefix}-saved.json')
            require(proof['passed'] is True and proof['selected_manifest_sha256_at_run'] == manifest_sha and
                    proof['runtime_manifest_sha256'] == runtime_sha and proof['candidate_id'] == candidate and
                    all(sha(proof_directory / name) == checksum for name, checksum in proof['receipts'].items()),
                    'Proof binding differs: ' + prefix)
            require(selection['manifest_sha256'] == manifest_sha and
                    selection['construction_sha256'] == selected['construction_sha256'] and
                    offline['offline_passed'] is True and offline['simulation_started'] is False,
                    'Selected offline identity differs: ' + prefix)
            require(positive['passed'] is True and positive['candidate_id'] == candidate and
                    positive['construction_sha256'] == selected['construction_sha256'] and
                    positive['runtime_manifest_sha256'] == runtime_sha and
                    positive['negative_log_sha256'] == sha(negative_path) and
                    positive['negative_error_contains'] in negative_path.read_text(),
                    'Compatibility positive/negative differs: ' + prefix)
            require(saved['passed'] is True and saved['recorded_only'] is True and
                    saved['originals_preserved'] is True and
                    saved['native_revision']['construction_sha256'] == selected['construction_sha256'] and
                    saved['analysis_revision']['runtime_manifest_sha256'] == runtime_sha and
                    saved['physical_acceptance_claimed'] is False and
                    saved['legal_acceptance_claimed'] is False,
                    'Saved processing differs: ' + prefix)
            attempt = scratch_root / f'{prefix}-compat'
            originals = saved['original_source_hashes']
            require(all((attempt / name).is_file() and sha(attempt / name) == checksum
                        for name, checksum in originals.items()),
                    'Original source changed: ' + prefix)
            require(saved['timestamp_joins']['frames'] == 600 and saved['timestamp_joins']['passed'] is True,
                    'Frame join differs: ' + prefix)
            config = read(PACKAGE / selected['construction'])
            config = json.loads(next(item['content'] for item in config['files'] if item['path'] == 'config.json'))
            invariant = {key: value for key, value in config.items()
                         if key not in ('case', 'case_id', 'case_suffix', 'selected_case_id',
                                        'candidate_id', 'target_projection_ft')}
            if candidate in fixed:
                require(fixed[candidate] == invariant, 'Comparison fixed conditions changed: ' + candidate)
            else:
                fixed[candidate] = invariant
            measured = positive['measurement_examples']['text_0_projection']['value']
            require(abs(measured - config['target_projection_ft']) < 0.01,
                    'Measured projection differs: ' + prefix)
            rows.append({'group': group, 'candidate': candidate, 'requested_ft': config['target_projection_ft'],
                         'measured_ft': measured, 'construction_sha256': selected['construction_sha256'],
                         'proof_sha256': sha(proof_path), 'saved_sha256': sha(proof_directory / f'{prefix}-saved.json')})
    for candidate in CANDIDATES:
        values = [row['measured_ft'] for row in rows if row['candidate'] == candidate]
        require(len(values) == 3 and values[0] < values[1] < values[2],
                'Projection ordering differs: ' + candidate)
    return {'format': 'c229398-current-runtime-source-comparison-audit-v1',
            'passed': True, 'runtime_manifest_sha256': runtime_sha,
            'selected_manifest_sha256': manifest_sha, 'chains': rows,
            'chain_count': len(rows), 'comparison_count': len(CANDIDATES),
            'diagnostic_only': True, 'original_native_observed': False,
            'physical_acceptance_claimed': False, 'legal_acceptance_claimed': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--proof-directory', type=Path, required=True)
    parser.add_argument('--scratch-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    receipt = audit(args.proof_directory.resolve(), args.scratch_root.resolve())
    args.output.write_text(json.dumps(receipt, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'passed': True, 'chains': receipt['chain_count'], 'receipt_sha256': sha(args.output)}))
