"""Return current source-bound fallback receipts after all public/saved runs pass."""
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
    entries = []
    for case in ('reference', 'contrast'):
        for candidate in ('fallback1', 'fallback2', 'fallback3'):
            prefix = f'c230241-selected-{("ref" if case == "reference" else "contrast")}-{candidate}'
            suffix = '-v2' if case == 'contrast' else ''
            compat = ROOT / '.runtime-work' / (prefix + '-compat' + suffix)
            saved = ROOT / '.runtime-work' / (prefix + '-saved' + suffix) / 'v0001'
            receipt = json.loads((compat / 'compatibility.json').read_text())
            processing = json.loads((saved / 'processing.json').read_text())
            if (receipt['case_id'] != PACKAGE.name + '__' + case or
                    receipt['candidate_id'] != candidate or receipt['passed'] is not True or
                    not processing['passed'] or not processing['recorded_only'] or
                    processing['timestamp_joins']['frames'] != 600 or
                    processing['physical_acceptance_claimed'] is not False):
                raise ValueError('Fallback public/saved proof differs: ' + case + '/' + candidate)
            returned = {}
            for label, path in (
                    ('compatibility', compat / 'compatibility.json'),
                    ('analysis', compat / 'compatibility-analysis.log'),
                    ('negative', compat / 'negative-analysis.log'),
                    ('processing', saved / 'processing.json'),
                    ('saved-analysis', saved / 'analysis.log')):
                ext = '.json' if label in ('compatibility', 'processing') else '.log'
                target = DEST / f'{case}-{candidate}-{label}{ext}'
                shutil.copyfile(path, target)
                if target.stat().st_size > 2 * 1024 * 1024:
                    raise ValueError('Returned proof exceeds 2 MiB: ' + str(target))
                returned[label] = {'path': target.relative_to(PACKAGE).as_posix(),
                                   'sha256': sha(target)}
            if returned['analysis']['sha256'] != receipt['log_sha256']:
                raise ValueError('Public analysis log changed')
            if returned['negative']['sha256'] != receipt['negative_log_sha256']:
                raise ValueError('Public negative log changed')
            entries.append({'case_id': receipt['case_id'], 'candidate_id': candidate,
                            'construction_sha256': receipt['construction_sha256'],
                            'fixture_sha256': receipt['fixture_sha256'],
                            'proofs': returned})
    output = DEST / 'fallback-index.json'
    output.write_text(json.dumps({'format': 'c230241-selected-fallback-proof-index-v1',
                                  'entries': entries, 'delivery_ready': False}, indent=2) + '\n')
    print(json.dumps({'fallbacks': len(entries), 'index_sha256': sha(output)}))


if __name__ == '__main__':
    main()
