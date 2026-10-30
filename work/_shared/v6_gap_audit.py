"""Read-only inventory of restored delivery evidence against pinned v6."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORK = ROOT / 'work'

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    current = sha(ROOT / batch['runtime']['root'] / 'SOURCE-MANIFEST.json')
    manifests = sorted(WORK.glob('testing__*/execution-manifest.json'))
    stale = fallback_missing = stale_compat = case_count = 0
    for path in manifests:
        manifest = json.loads(path.read_text())
        stale += manifest.get('runtime_manifest_sha256') != current
        for entry in manifest['cases']:
            case_count += 1
            fallback_missing += 'fallback1' not in {c.get('id') for c in entry.get('candidates', [])}
            receipt = json.loads((path.parent / entry['compatibility']['receipt']).read_text())
            stale_compat += receipt.get('runtime_manifest_sha256') != current
    queue = json.loads((WORK / '_shared/gpu-queue.json').read_text())
    summary = {
        'format': 'worker-v6-gap-audit-v1',
        'runtime_manifest_sha256': current,
        'packages': len(manifests),
        'cases': case_count,
        'comparisons': len(queue.get('comparison_audit_commands', [])),
        'packages_stale_runtime': stale,
        'cases_without_fallback1': fallback_missing,
        'cases_with_stale_primary_compatibility': stale_compat,
        'queue_rows_without_canonical_commands': sum(
            not all(row.get(k) for k in ('prepare_command', 'execute_command', 'accept_command'))
            for row in queue.get('cases', [])),
        'local_integration_proof_exists': (WORK / '_shared/local-integration-proof.json').exists(),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))

if __name__ == '__main__':
    main()
