"""Return exact current-runtime primary public and saved CPU proof receipts."""
import hashlib
import json
from pathlib import Path
import shutil

PACKAGE = Path(__file__).resolve().parents[1]
ROOT = PACKAGE.parents[1]
DEST = PACKAGE / 'selected-proofs'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    DEST.mkdir(exist_ok=True)
    index = []
    for case, compat_name, saved_name in (
            ('reference', 'c230241-selected-ref-compat-v5', 'c230241-selected-ref-saved-v5'),
            ('contrast', 'c230241-selected-contrast-primary-compat-v2', 'c230241-selected-contrast-primary-saved-v2')):
        compat = ROOT / '.runtime-work' / compat_name
        saved = ROOT / '.runtime-work' / saved_name / 'v0001'
        receipt = json.loads((compat / 'compatibility.json').read_text())
        processing = json.loads((saved / 'processing.json').read_text())
        if not receipt['passed'] or receipt['case_id'] != PACKAGE.name + '__' + case:
            raise ValueError('Selected public receipt differs: ' + case)
        if not (processing['passed'] and processing['recorded_only'] and
                processing['timestamp_joins']['frames'] == 600 and
                processing['physical_acceptance_claimed'] is False):
            raise ValueError('Selected saved receipt differs: ' + case)
        returned = {}
        for label, path in (('compatibility', compat / 'compatibility.json'),
                            ('analysis', compat / 'compatibility-analysis.log'),
                            ('negative', compat / 'negative-analysis.log'),
                            ('processing', saved / 'processing.json'),
                            ('saved-analysis', saved / 'analysis.log')):
            target = DEST / f'{case}-{label}{".json" if label in ("compatibility", "processing") else ".log"}'
            shutil.copyfile(path, target)
            if target.stat().st_size > 2*1024*1024:
                raise ValueError('Returned proof exceeds 2 MiB: ' + str(target))
            returned[label] = {'path': str(target.relative_to(PACKAGE)),
                               'sha256': sha(target)}
        index.append({'case_id': receipt['case_id'],
                      'construction_sha256': receipt['construction_sha256'],
                      'fixture_sha256': receipt['fixture_sha256'],
                      'negative_removed': receipt['negative_removed'],
                      'proofs': returned})
    output = DEST / 'primary-index.json'
    output.write_text(json.dumps({'format': 'c230241-selected-primary-proof-index-v1',
                                  'cases': index, 'delivery_ready': False}, indent=2) + '\n')
    print(json.dumps({'cases': len(index), 'index_sha256': sha(output)}))


if __name__ == '__main__':
    main()
