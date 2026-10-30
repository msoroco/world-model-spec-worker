"""Hash-check and summarize every selected CPU delivery proof log."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIELDS = {
    'offline': ('offline', 'log', 'log_sha256'),
    'compatibility_receipt': ('compatibility', 'receipt', 'sha256'),
    'saved_processing': ('post_capture', 'test_log', 'test_log_sha256'),
    'audit_positive': ('delivery_acceptance', 'test_log', 'test_log_sha256'),
    'audit_negative': ('delivery_acceptance', 'negative_log', 'negative_log_sha256'),
}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    rows = {name: [] for name in FIELDS}
    packages = 0
    for manifest_path in sorted((ROOT / 'work').glob('testing__*/execution-manifest.json')):
        packages += 1
        folder = manifest_path.parent
        manifest = json.loads(manifest_path.read_text())
        for case in manifest['cases']:
            assert case['kind'] == 'delivery'
            for name, (section, path_key, hash_key) in FIELDS.items():
                proof = case[section]
                path = folder / proof[path_key]
                assert path.is_file(), path
                digest = sha(path)
                assert digest == proof[hash_key], (path, digest, proof[hash_key])
                rows[name].append(f"{case['case_id']} {digest}\n")
            assert case['offline']['exit_code'] == 0
            assert case['post_capture']['test_exit_code'] == 0
            assert case['delivery_acceptance']['test_exit_code'] == 0
            assert case['delivery_acceptance']['negative_exit_code'] != 0
    assert packages == 43 and all(len(items) == 236 for items in rows.values())
    result = {'format': 'worker-delivery-proof-index-v1', 'packages': packages,
              'cases': 236, 'log_digests': {
                  name: hashlib.sha256(''.join(items).encode()).hexdigest()
                  for name, items in rows.items()},
              'digest_rule': 'SHA-256 of sorted manifest order lines: case_id, space, declared SHA-256, newline',
              'physical_acceptance_claimed': False}
    output = ROOT / 'work/_shared/delivery-proof-index.json'
    output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
