"""Run exception source checker on all 28 retained diagnostic saved outputs."""
import hashlib
import json
from pathlib import Path

from delivery_audit import validate_exception_measurement


ROOT = Path(__file__).resolve().parents[3]
WORK = Path(__file__).resolve().parents[1]


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    plan = json.loads((WORK / 'case-plan.json').read_text())
    expected = {item['case_id'] for item in plan['cases']
                if 'exception_spec' in item}
    assert len(expected) == 28
    paths = {}
    for report in (ROOT / '.runtime-work').glob(
            'c150142-*-result-*/v0001/analysis/analysis-report.json'):
        try:
            case = json.loads(report.read_text())['case_id']
        except (KeyError, ValueError):
            continue
        if case in expected:
            paths.setdefault(case, []).append(report.parent)
    passed = []
    for case in sorted(expected):
        errors = []
        for attempt in sorted(paths.get(case, []), reverse=True):
            try:
                result = validate_exception_measurement(
                    attempt, plan, case, 'synthetic_native_sample')
                passed.append({'case_id': case, 'frames': result['frames'],
                               'source_kind': result['source_kind'],
                               'analysis_report_sha256': sha(attempt / 'analysis-report.json'),
                               'config_sha256': sha(attempt / 'config.json'),
                               'result_sha256': sha(attempt / 'result.json'),
                               'diagnostic_attempt': str(attempt.relative_to(ROOT))})
                break
            except (ValueError, OSError, KeyError) as error:
                errors.append(str(error))
        else:
            raise ValueError('No passing diagnostic saved exception for ' + case +
                             ': ' + '; '.join(errors[:3]))
    print(json.dumps({'format': 'c150142-exception-audit-matrix-v1',
                      'cases_passed': len(passed), 'cases': passed,
                      'original_native_observed': False,
                      'physical_acceptance_claimed': False}, sort_keys=True))


if __name__ == '__main__':
    main()
