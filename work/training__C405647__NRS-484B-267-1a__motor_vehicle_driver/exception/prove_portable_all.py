"""Run exact pinned v1 synthetic portable positives and negatives for eight bundles."""
import json
from pathlib import Path

from probe_compat import prove

HERE = Path(__file__).resolve().parent


def run():
    receipts = []
    for case in ('exception_1_1', 'exception_1_2'):
        for candidate in ('primary', 'fallback1', 'fallback2', 'fallback3'):
            receipt = prove(case, candidate, reuse=True)
            receipts.append(receipt)
            print(case, candidate, receipt['positive_receipt_sha256'], flush=True)
    summary = {'format': 'c405647-exception-unselected-v1-portable-v1',
               'manifest_sha256': receipts[0]['manifest_sha256'],
               'receipts': receipts,
               'strict_recipe_v2_verified': False,
               'physical_or_legal_result_claimed': False}
    (HERE / 'portable-summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    return {'passed': True, 'receipts': len(receipts),
            'strict_recipe_v2_verified': False}


if __name__ == '__main__':
    print(json.dumps(run(), sort_keys=True))
