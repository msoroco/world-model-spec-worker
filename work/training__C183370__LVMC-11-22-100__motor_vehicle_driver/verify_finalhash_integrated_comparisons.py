"""Recheck six source-bound CPU comparisons and swapped-source negatives."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


manifest_sha = sha(HERE / 'execution-manifest.json')
matrix = json.loads((HERE / 'update157-finalhash-six-comparison-matrix.json').read_text())
assert matrix['manifest_sha256'] == manifest_sha
assert matrix['all_six_diagnostic_comparisons_passed'] is True
assert matrix['canonical_acceptance_claimed'] is False
assert len(matrix['rows']) == 6
for row in matrix['rows']:
    positive_path = HERE / row['positive_receipt']
    negative_path = HERE / row['swapped_negative_receipt']
    assert sha(positive_path) == row['positive_sha256']
    assert sha(negative_path) == row['swapped_negative_sha256']
    positive = json.loads(positive_path.read_text())
    negative = json.loads(negative_path.read_text())
    assert positive['manifest_sha256'] == manifest_sha
    assert positive['diagnostic_only'] is True
    assert positive.get('accepted', False) is False
    assert negative['passed'] is True
    assert negative['rejection']
print(json.dumps({'comparisons': 6, 'manifest_sha256': manifest_sha,
                  'diagnostic_only': True}, sort_keys=True))
