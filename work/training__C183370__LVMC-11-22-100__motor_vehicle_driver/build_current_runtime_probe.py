"""Stage a cutover reproof without treating historical receipts as current."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = HERE / 'execution-manifest.json'
TARGET = HERE / 'current-runtime-probe-manifest.json'


def main():
    batch = json.loads((ROOT / 'batch.json').read_text())
    manifest = json.loads(SOURCE.read_text())
    manifest['runtime_manifest_sha256'] = batch['runtime']['source_manifest_sha256']
    manifest['status'] = 'cutover_reproof_in_progress'
    for case in manifest['cases']:
        for key in ('offline', 'compatibility', 'negative', 'saved_processing',
                    'delivery_acceptance', 'physical_preparation'):
            case.pop(key, None)
        case['candidate_offline_status'] = 'cutover_reproof_pending'
        for candidate in case['candidates']:
            for key in ('offline', 'compatibility', 'saved_processing'):
                candidate.pop(key, None)
    TARGET.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'path': str(TARGET.relative_to(ROOT)),
                      'sha256': hashlib.sha256(TARGET.read_bytes()).hexdigest(),
                      'cases': len(manifest['cases'])}))


if __name__ == '__main__':
    main()
