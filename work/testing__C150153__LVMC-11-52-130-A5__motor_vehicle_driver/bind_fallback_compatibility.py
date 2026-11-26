"""Bind passing exact fallback diagnostic compatibility proofs to their draft."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.fallback-diagnostic.json'


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def bind() -> None:
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get('status') != 'synthetic_fallback_diagnostic_only_unselected_original_capture_pending':
        raise ValueError('fallback receipts require an unselected diagnostic manifest')
    for entry in manifest['cases']:
        case_id = entry['case_id']
        kind = case_id.removeprefix(HERE.name + '__')
        for candidate_id in ('primary', 'fallback1'):
            candidate = entry if candidate_id == 'primary' else entry['candidates'][0]
            if candidate_id != 'primary' and candidate['id'] != candidate_id:
                raise ValueError('unexpected fallback candidate: ' + kind)
            output = ROOT / '.runtime-work/c150153-owner' / (
                'fallback-compat-' + kind + '-' + candidate_id)
            source = output / 'compatibility.json'
            receipt = json.loads(source.read_text())
            required = {'selected_measurements', 'negative_case_source',
                        'four_camera_sources', 'final_decode', 'native_validation'}
            if (receipt.get('passed') is not True or
                    receipt.get('case_id') != case_id or
                    receipt.get('candidate_id') != candidate_id or
                    receipt.get('construction_sha256') != candidate['construction_sha256'] or
                    receipt.get('runtime_manifest_sha256') != manifest['runtime_manifest_sha256'] or
                    receipt.get('negative_removed') != 'reviewed-site/packet.json' or
                    not required.issubset(receipt.get('checks', []))):
                raise ValueError('incomplete exact fallback compatibility: ' + kind + '/' + candidate_id)
            prefix = 'cpu-fallback-' + kind + '-' + candidate_id
            saved_receipt = HERE / (prefix + '.json')
            saved_analysis = HERE / (prefix + '-analysis.log')
            saved_negative = HERE / (prefix + '-negative.log')
            shutil.copy2(source, saved_receipt)
            shutil.copy2(output / 'compatibility-analysis.log', saved_analysis)
            shutil.copy2(output / 'negative-analysis.log', saved_negative)
            if (sha(saved_analysis) != receipt['log_sha256'] or
                    sha(saved_negative) != receipt['negative_log_sha256'] or
                    receipt['negative_error_contains'] not in saved_negative.read_text()):
                raise ValueError('fallback compatibility logs changed: ' + kind + '/' + candidate_id)
            candidate['compatibility'] = {'receipt': saved_receipt.name,
                                          'sha256': sha(saved_receipt),
                                          'log': saved_analysis.name,
                                          'negative_log': saved_negative.name}
            if candidate_id == 'primary':
                entry['negative'] = {'log': saved_negative.name}
            print(kind, candidate_id, 'compatibility bound', flush=True)
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    bind()
