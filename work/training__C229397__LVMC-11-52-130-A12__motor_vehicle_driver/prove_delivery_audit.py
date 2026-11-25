"""Exercise independent delivery audit on a source-shaped synthetic fixture."""
import json
from pathlib import Path
import tempfile

from delivery_audit import SOURCES, audit, sha
from finalize_delivery import finalize
from prove_saved import write_attempt


def reject(case, attempt, receipt, expected):
    try:
        audit(case, attempt, receipt, diagnostic=True)
    except ValueError as exc:
        if str(exc) == expected:
            return
        raise
    raise RuntimeError('invalid delivery source accepted: ' + expected)


def main():
    here = Path(__file__).resolve().parent
    bundle = json.loads((here / 'draft-crosswalk/controlled_2/primary/construction.json').read_text())
    config = next(json.loads(item['content']) for item in bundle['files'] if item['path'] == 'config.json')
    case = config['case_id']
    with tempfile.TemporaryDirectory(prefix='c229397-delivery-audit-') as directory:
        attempt = Path(directory) / 'attempt'
        attempt.mkdir()
        write_attempt(attempt)
        (attempt / 'config.json').write_text(json.dumps(config) + '\n')
        report_path = attempt / 'analysis-report.json'
        finalize(attempt, report_path)
        receipt = {'format': 'worker-saved-processing', 'case_id': case,
                   'candidate_id': 'primary', 'passed': True, 'recorded_only': True,
                   'originals_preserved': True, 'missing_evidence': False,
                   'physical_acceptance_claimed': False,
                   'legal_acceptance_claimed': False,
                   'timestamp_joins': {'passed': True, 'frames': 600},
                   'original_source_hashes': {name: sha(attempt / name) for name in SOURCES},
                   'result': str(attempt / 'result.json'),
                   'result_sha256': sha(attempt / 'result.json'),
                   'final_video_checks': {'passed': True, 'frames': 600}}
        receipt_path = Path(directory) / 'synthetic-processing-shape.json'
        receipt_path.write_text(json.dumps(receipt) + '\n')
        result = audit(case, attempt, receipt_path, diagnostic=True)
        if result['original_review_complete'] or result['physical_acceptance_claimed']:
            raise ValueError('Diagnostic audit claimed original physical review')
        reject(case + '__other', attempt, receipt_path, 'Selected crosswalk case differs')
        original_hash = receipt['original_source_hashes']['control-intent.jsonl']
        receipt['original_source_hashes']['control-intent.jsonl'] = '0' * 64
        receipt_path.write_text(json.dumps(receipt) + '\n')
        reject(case, attempt, receipt_path, 'Original source missing or stale: control-intent.jsonl')
        receipt['original_source_hashes']['control-intent.jsonl'] = original_hash
        receipt['timestamp_joins']['frames'] = 599
        receipt_path.write_text(json.dumps(receipt) + '\n')
        reject(case, attempt, receipt_path, 'Original saved frame join incomplete')
        receipt['timestamp_joins']['frames'] = 600
        receipt_path.write_text(json.dumps(receipt) + '\n')
        result_path = attempt / 'result.json'
        original_result = result_path.read_text()
        altered_result = json.loads(original_result)
        altered_result['target_checks'][0]['matched'] = False
        result_path.write_text(json.dumps(altered_result) + '\n')
        receipt['result_sha256'] = sha(result_path)
        receipt_path.write_text(json.dumps(receipt) + '\n')
        reject(case, attempt, receipt_path,
               'Saved crosswalk measurement or acceptance boundary differs')
        result_path.write_text(original_result)
        receipt['result_sha256'] = sha(result_path)
        receipt_path.write_text(json.dumps(receipt) + '\n')
        try:
            audit(case, attempt, receipt_path, diagnostic=False)
        except ValueError as exc:
            if str(exc) != 'Original camera or source decode receipt missing: overview':
                raise
        else:
            raise RuntimeError('original source decode omitted but accepted')
        (attempt / 'crosswalk-source-review.json').unlink()
        reject(case, attempt, receipt_path,
               'Original source missing or stale: crosswalk-source-review.json')
    print(json.dumps({'passed': True, 'case_id': case,
                      'checks': ['diagnostic source join', 'changed case', 'stale original',
                                 'short frame receipt', 'unmatched measured target',
                                 'missing original source decode',
                                 'missing independent review'],
                      'diagnostic_fixture': True,
                      'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
