"""Bind the 287(c) public compatibility and recorded-only CPU receipts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ASSIGNMENT = HERE.parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(value, message):
    if not value:
        raise ValueError(message)


def audit():
    manifest = json.loads((ASSIGNMENT / 'crossref-287c-manifest.json').read_text())
    require(manifest['status'] == 'unselected_cpu_source_feasibility',
            '287(c) must retain truthful unselected status')
    rows = []
    for label, entry in zip(('marked', 'unmarked'), manifest['cases']):
        case = ASSIGNMENT.name + '__crossref_287c_' + label
        proof_dir = HERE / label / 'proofs'
        compatibility_path = proof_dir / 'compatibility.json'
        positive_path = proof_dir / 'positive-analysis.log'
        negative_path = proof_dir / 'negative-analysis.log'
        saved_path = proof_dir / 'processing.json'
        compatibility = json.loads(compatibility_path.read_text())
        saved = json.loads(saved_path.read_text())
        require(entry['case_id'] == case and entry['kind'] == 'unselected_cpu_diagnostic',
                '287(c) exact case identity or selection differs')
        require(sha(ASSIGNMENT / entry['construction']) == entry['construction_sha256'],
                '287(c) construction hash differs')
        require(compatibility['passed'] and compatibility['case_id'] == case and
                compatibility['candidate_id'] == 'primary' and
                compatibility['construction_sha256'] == entry['construction_sha256'] and
                compatibility['runtime_manifest_sha256'] == manifest['runtime_manifest_sha256'],
                '287(c) public compatibility is stale')
        require(compatibility['fixture_recipe_sha256'] == sha(HERE / label / 'recipe.json') and
                compatibility['measurement_contract_sha256'] ==
                sha(ASSIGNMENT / entry['measurement_contract']),
                '287(c) source recipe or exact measurement contract differs')
        require(compatibility['log_sha256'] == sha(positive_path) and
                compatibility['negative_log_sha256'] == sha(negative_path) and
                compatibility['negative_removed'] == 'curb-samples.jsonl' and
                compatibility['negative_error_contains'] in negative_path.read_text(),
                '287(c) positive or missing-source negative log differs')
        require({'actual_analysis', 'lean_decoder', 'render', 'final_decode',
                 'negative_case_source'}.issubset(set(compatibility['checks'])),
                '287(c) public proof stages are incomplete')
        require(saved['format'] == 'worker-saved-processing' and saved['passed'] and
                saved['recorded_only'] and saved['originals_preserved'] and
                saved['case_id'] == case and saved['candidate_id'] == 'primary' and
                saved['native_revision']['construction_sha256'] == entry['construction_sha256'] and
                saved['analysis_log_sha256'] == sha(positive_path) and
                saved['timestamp_joins']['passed'] and
                saved['timestamp_joins']['frames'] == 600 and
                not saved['physical_acceptance_claimed'] and
                not saved['legal_acceptance_claimed'],
                '287(c) recorded-only receipt or its limits differ')
        rows.append({'case_id': case,
                     'construction_sha256': entry['construction_sha256'],
                     'compatibility_sha256': sha(compatibility_path),
                     'positive_log_sha256': sha(positive_path),
                     'negative_log_sha256': sha(negative_path),
                     'saved_processing_sha256': sha(saved_path),
                     'public_positive': True,
                     'missing_source_rejected': True,
                     'recorded_only_saved': True})
    result = {'format': 'c230222-287c-public-cpu-proof-v1',
              'cases': rows, 'public_manifest_sha256':
              sha(ASSIGNMENT / 'crossref-287c-manifest.json'),
              'source_proof_sha256': sha(HERE / 'source-proof.json'),
              'comparison_proof_sha256': sha(HERE / 'comparison-proof.json'),
              'original_native_observed': False,
              'operating_official_devices_verified': False,
              'original_marking_pixels_verified': False,
              'delivery_selected': False}
    target = HERE / 'public-proof.json'
    target.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'cases': len(rows), 'proof_sha256': sha(target)}))


if __name__ == '__main__':
    audit()
