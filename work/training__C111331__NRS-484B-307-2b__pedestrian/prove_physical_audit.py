"""CPU negative proof for the independent original-source review gate."""
import json
from pathlib import Path
import tempfile

from physical_audit import audit


def reject(attempt, review, expected):
    try:
        audit(attempt, review)
    except (ValueError, FileNotFoundError) as error:
        assert expected in str(error), str(error)
        return
    raise AssertionError('unverified source was accepted')


def main():
    root = Path('.runtime-work').resolve()
    root.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='c111331-physical-audit-', dir=root) as name:
        folder = Path(name)
        case_id = 'training__C111331__NRS-484B-307-2b__pedestrian__witness_1'
        (folder / 'config.json').write_text(json.dumps({'case_id': case_id}) + '\n')
        review = folder / 'review.json'
        review.write_text('{}\n')
        reject(folder, review, 'Original Native capture report required')
        report = folder / 'native-capture-report.json'
        report.write_text(json.dumps({'case_id': case_id, 'frames': 599,
                                      'restoration': True, 'error': None}) + '\n')
        reject(folder, review, 'Complete restored Native capture required')
        report.write_text(json.dumps({'case_id': case_id, 'frames': 600,
                                      'restoration': True, 'error': None}) + '\n')
        reject(folder, review, 'Independent original Native review binding required')
    print('physical audit rejected three incomplete original-source conditions')


if __name__ == '__main__':
    main()
