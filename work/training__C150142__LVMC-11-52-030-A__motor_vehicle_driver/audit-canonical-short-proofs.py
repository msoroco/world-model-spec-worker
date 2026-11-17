"""Independently bind 56 short-case CPU proofs to the installed manifest."""
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
CANDIDATES = ('primary', 'fallback1', 'fallback2', 'fallback3')
SLUGS = (
    'reference', 'contrast', 'ordinary_red_signed',
    'mail_adjacent_deposit', 'mail_no_box_deposit', 'mail_adjacent_no_deposit',
    'armored_car_signed_business', 'armored_car_signed_no_business',
    'armored_car_unsigned_business', 'armored_car_unsigned_no_business',
    'emergency_vehicle_signed_business', 'emergency_vehicle_signed_no_business',
    'emergency_vehicle_unsigned_business',
    'emergency_vehicle_unsigned_no_business',
)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def require(test, message):
    if not test:
        raise ValueError(message)


def main():
    manifest_path = ROOT / 'execution-manifest.json'
    manifest_hash = sha(manifest_path)
    manifest = json.loads(manifest_path.read_text())
    entries = {row['case_id']: row for row in manifest['cases']}
    counts = {}
    for slug in SLUGS:
        case_id = ROOT.name + '__' + slug
        entry = entries[case_id]
        require((ROOT / entry['measurement_contract']).is_file() and
                (REPO / entry['fixture_recipe']).is_file(),
                'Canonical diagnostic binding absent: ' + slug)
        proof_path = ROOT / f'selected-{slug}-four-candidate-proof-canonicalnext-v1.json'
        proof = json.loads(proof_path.read_text())
        require(proof['selected_case_id'] == case_id and
                proof['original_native_observed'] is False and
                len(proof['records']) == 4,
                'Selected proof index incomplete: ' + slug)
        require({row['candidate_id'] for row in proof['records']} == set(CANDIDATES),
                'Candidate coverage differs: ' + slug)
        for record in proof['records']:
            candidate = record['candidate_id']
            selected = entry if candidate == 'primary' else next(
                row for row in entry['candidates'] if row['id'] == candidate)
            expected_frames = 240 if slug in SLUGS[:3] else 361
            require(record['case_id'] == case_id and
                    record['manifest_sha256'] == manifest_hash and
                    record['construction_sha256'] == selected['construction_sha256'] and
                    record['saved_frames'] == expected_frames and
                    record['source_kind'] == 'synthetic_native_sample' and
                    record['physical_acceptance_claimed'] is False,
                    'Selected proof binding differs: ' + slug + '/' + candidate)
            prefix = (REPO / '.runtime-work' /
                      f'c150142-selected-{slug}-{candidate}-canonicalnext-v1')
            compatibility_path = Path(str(prefix) + '-compat') / 'compatibility.json'
            negative_path = Path(str(prefix) + '-compat') / 'negative-analysis.log'
            saved_path = Path(str(prefix) + '-process.full.log')
            require(sha(compatibility_path) == record['compatibility_receipt_sha256'] and
                    sha(negative_path) == record['compatibility_negative_log_sha256'] and
                    sha(saved_path) == record['saved_result_sha256'],
                    'Pinned proof bytes changed: ' + slug + '/' + candidate)
            compat = json.loads(compatibility_path.read_text())
            saved = json.loads(saved_path.read_text())
            require(compat['passed'] is True and
                    compat['case_id'] == case_id and
                    compat['candidate_id'] == candidate and
                    compat['construction_sha256'] == selected['construction_sha256'] and
                    compat['negative_removed'] in compat['fixture_manifest'] and
                    saved['passed'] is True and
                    saved['case_id'] == case_id and
                    saved['candidate_id'] == candidate and
                    saved['missing_evidence'] is False and
                    saved['originals_preserved'] is True and
                    saved['timestamp_joins']['frames'] == expected_frames and
                    saved['final_video_checks']['frames'] == expected_frames and
                    saved['physical_acceptance_claimed'] is False and
                    saved['legal_acceptance_claimed'] is False,
                    'Pinned proof checks incomplete: ' + slug + '/' + candidate)
        counts[slug] = 4
    output = ROOT / 'update051-canonical-short-proof-audit.json'
    output.write_text(json.dumps({
        'format': 'c150142-canonical-short-proof-audit-v1',
        'passed': True, 'manifest_sha256': manifest_hash,
        'cases': len(SLUGS), 'candidate_proofs': sum(counts.values()),
        'case_candidate_counts': counts,
        'source_kind': 'synthetic_native_sample',
        'original_native_observed': False,
        'physical_acceptance_claimed': False,
    }, indent=2) + '\n')
    print(output.relative_to(REPO))


if __name__ == '__main__':
    main()
