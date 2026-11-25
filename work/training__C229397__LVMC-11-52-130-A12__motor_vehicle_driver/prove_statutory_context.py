"""Source-shaped positive and negative proof for independent context audit."""
import json
from pathlib import Path
import tempfile

from prove_saved import write_attempt
from statutory_context_audit import audit


def reject(path, case_id, expected):
    try:
        audit(path, case_id)
    except ValueError as exc:
        if str(exc) == expected:
            return
        raise
    raise RuntimeError('invalid statutory context accepted: ' + expected)


def main():
    here = Path(__file__).resolve().parent
    bundle = json.loads((here / 'draft-crosswalk/controlled_2/primary/construction.json').read_text())
    config = next(json.loads(item['content']) for item in bundle['files'] if item['path'] == 'config.json')
    case_id = config['case_id']
    with tempfile.TemporaryDirectory(prefix='c229397-context-') as directory:
        good = Path(directory) / 'good'
        good.mkdir()
        write_attempt(good)
        (good / 'config.json').write_text(json.dumps(config) + '\n')
        report = audit(good, case_id)
        if report['legal_verdict'] is not None or report['physical_acceptance_claimed']:
            raise ValueError('source-shaped proof claimed law or physical acceptance')
        if any(value != 'unresolved' for value in report['exception_review'].values()):
            raise ValueError('source-shaped exception findings differ')
        reject(good, case_id + '__other', 'statutory context case identity differs')

        bad = Path(directory) / 'missing_review'
        bad.mkdir()
        write_attempt(bad)
        (bad / 'config.json').write_text(json.dumps(config) + '\n')
        (bad / 'crosswalk-source-review.json').unlink()
        reject(bad, case_id, 'independent crosswalk source review missing')

        bad = Path(directory) / 'stale_exception'
        bad.mkdir()
        write_attempt(bad)
        (bad / 'config.json').write_text(json.dumps(config) + '\n')
        review_path = bad / 'crosswalk-source-review.json'
        review = json.loads(review_path.read_text())
        review['findings']['traffic_conflict_review_source_id']['sha256'] = '0' * 64
        review_path.write_text(json.dumps(review) + '\n')
        reject(bad, case_id, 'crosswalk source review hash differs: traffic_conflict_review_source_id')

        bad = Path(directory) / 'missing_exception'
        bad.mkdir()
        write_attempt(bad)
        (bad / 'config.json').write_text(json.dumps(config) + '\n')
        review_path = bad / 'crosswalk-source-review.json'
        review = json.loads(review_path.read_text())
        del review['findings']['directions_review_source_id']
        review_path.write_text(json.dumps(review) + '\n')
        reject(bad, case_id, 'crosswalk source review findings incomplete')

        bad = Path(directory) / 'wrong_inventory'
        bad.mkdir()
        write_attempt(bad)
        (bad / 'config.json').write_text(json.dumps(config) + '\n')
        inventory_path = bad / 'crosswalk-inventory.json'
        inventory = json.loads(inventory_path.read_text())
        inventory['source_kind'] = 'unknown'
        inventory_path.write_text(json.dumps(inventory) + '\n')
        reject(bad, case_id, 'statutory context requires original Native inventory')
    print(json.dumps({'passed': True, 'case_id': case_id,
                      'review_sha256': report['review_sha256'],
                      'checks': ['source-shaped review', 'changed case', 'missing review',
                                 'stale exception source', 'missing exception finding',
                                 'non-Native inventory'],
                      'physical_acceptance_claimed': False,
                      'legal_verdict': None}, sort_keys=True))


if __name__ == '__main__':
    main()
