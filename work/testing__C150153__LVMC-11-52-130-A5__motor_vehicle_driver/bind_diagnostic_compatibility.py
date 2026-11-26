"""Bind twelve passing pinned synthetic compatibility receipts to draft manifest."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
MANIFEST = HERE / 'execution-manifest.source-bound-diagnostic.json'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def bind():
    manifest = json.loads(MANIFEST.read_text())
    if manifest.get('status') != 'synthetic_diagnostic_only_unselected_original_capture_pending':
        raise ValueError('Cannot bind diagnostic receipt to selected original manifest')
    for entry in manifest['cases']:
        case_id = entry['case_id']
        kind = case_id.removeprefix(HERE.name + '__')
        output = ROOT / '.runtime-work/c150153-owner' / (
            'compat-west-inside-v3' if kind == 'west_inside' else 'compat-' + kind)
        receipt_source = output / 'compatibility.json'
        receipt = json.loads(receipt_source.read_text())
        if (receipt.get('passed') is not True or receipt.get('case_id') != case_id or
                receipt.get('candidate_id') != 'primary' or
                receipt.get('construction_sha256') != entry['construction_sha256'] or
                receipt.get('runtime_manifest_sha256') != manifest['runtime_manifest_sha256'] or
                receipt.get('negative_removed') != 'reviewed-site/packet.json' or
                'selected_measurements' not in receipt.get('checks', []) or
                'negative_case_source' not in receipt.get('checks', [])):
            raise ValueError('Incomplete exact diagnostic compatibility: ' + case_id)
        saved_receipt = HERE / ('cpu-compat-' + kind + '.json')
        saved_analysis = HERE / ('cpu-compat-analysis-' + kind + '.log')
        saved_negative = HERE / ('cpu-compat-negative-' + kind + '.log')
        shutil.copy2(receipt_source, saved_receipt)
        shutil.copy2(output / 'compatibility-analysis.log', saved_analysis)
        shutil.copy2(output / 'negative-analysis.log', saved_negative)
        if (sha(saved_analysis) != receipt['log_sha256'] or
                sha(saved_negative) != receipt['negative_log_sha256'] or
                receipt['negative_error_contains'] not in saved_negative.read_text()):
            raise ValueError('Positive or negative compatibility log changed: ' + case_id)
        entry['compatibility'] = {'receipt': saved_receipt.name,
                                  'sha256': sha(saved_receipt),
                                  'log': saved_analysis.name}
        entry['negative'] = {'log': saved_negative.name}
        print(kind, 'compatibility bound')
    MANIFEST.write_text(json.dumps(manifest, indent=2) + '\n')


if __name__ == '__main__':
    bind()
