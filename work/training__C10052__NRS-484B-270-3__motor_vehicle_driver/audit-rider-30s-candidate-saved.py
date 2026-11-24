"""Independently check the exact 30 s rider candidate saved diagnostics."""
import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PACKAGE = HERE / 'rider-30s-primary'
IDS = ('primary', 'fallback1', 'fallback2', 'fallback3')
VIEWS = {'overview.mkv', 'approach.mkv', 'reference_corner.mkv',
         'driver_reference.mkv'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def check(proof_path):
    proof = json.loads(Path(proof_path).read_text())
    manifest = json.loads((PACKAGE / 'draft-manifest.json').read_text())
    recipe = json.loads((PACKAGE / 'fixture-recipe.json').read_text())
    assert proof['manifest_sha256'] == sha(PACKAGE / 'draft-manifest.json')
    assert proof['recipe_sha256'] == sha(PACKAGE / 'fixture-recipe.json')
    assert proof['source_count'] == len(recipe['sources']) == 616
    assert proof['selected'] is False and proof['accepted'] is False
    source_hashes = {item['path']: item['sha256'] for item in recipe['sources']}
    assert len(source_hashes) == 616
    entry = manifest['cases'][0]
    constructions = {'primary': (entry['construction'], entry['construction_sha256'])}
    constructions.update({item['id']: (item['construction'], item['construction_sha256'])
                          for item in entry['candidates']})
    rows = proof['candidates']
    assert [row['candidate_id'] for row in rows] == list(IDS)
    assert set(constructions) == set(IDS)
    assert len({row['construction_sha256'] for row in rows}) == 4
    for row in rows:
        candidate = row['candidate_id']
        path, expected = constructions[candidate]
        assert sha(PACKAGE / path) == expected == row['construction_sha256']
        assert row['original_frames'] == 600
        assert row['derived_channel_count'] == 12
        assert set(row['camera_frames']) == VIEWS
        assert all(count == 600 for count in row['camera_frames'].values())
        assert row['core_lean_passed'] and row['final_decode_passed']
        assert row['missing_source_rejected']
        assert row['measured_values']['simultaneous_conflict_frames'] == 0
        for relative, digest in row['source_hashes'].items():
            assert source_hashes[relative] == digest
    return {'format': 'c10052-rider-30s-candidate-independent-audit-v1',
            'passed': True, 'candidate_count': 4, 'source_count': 616,
            'frames_per_candidate': 600, 'selected': False,
            'proof_sha256': sha(proof_path)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--proof', type=Path,
                        default=PACKAGE / 'candidate-saved-proof.json')
    args = parser.parse_args()
    result = check(args.proof)
    if args.proof.resolve() == (PACKAGE / 'candidate-saved-proof.json').resolve():
        (PACKAGE / 'candidate-saved-audit.json').write_text(
            json.dumps(result, sort_keys=True, indent=2) + '\n')
    print(json.dumps(result, sort_keys=True))


if __name__ == '__main__':
    main()
