"""Source-hashed synthetic CPU probes for both subsection (3)(c) endpoints."""
import hashlib
import json
import tempfile
from datetime import timedelta
from pathlib import Path

from branch_cases import check_review, operation_window_position
from prove_saved import fixture
from review_context import verified_sources


ROOT = Path(__file__).resolve().parents[1]
CASES = (
    ('after_cessation_below', '2026-11-25T15:29:59-08:00', 'before_lower'),
    ('after_cessation_at', '2026-11-25T15:30:00-08:00', 'at_lower'),
    ('after_cessation_above', '2026-11-25T15:30:01-08:00', 'interior'),
    ('before_next_operation_below', '2026-11-26T07:29:59-08:00', 'interior'),
    ('before_next_operation_at', '2026-11-26T07:30:00-08:00', 'at_upper'),
    ('before_next_operation_above', '2026-11-26T07:30:01-08:00', 'after_upper'),
)


def main():
    rows = []
    with tempfile.TemporaryDirectory() as temporary:
        base = Path(temporary)
        for name, civil, expected in CASES:
            attempt = base / name
            fixture(attempt, True, suffix='exception_c')
            context_path = attempt / 'school-context.json'
            context = json.loads(context_path.read_text())
            review = context['independent_review']
            assert review['case_facts']['children_present']['value'] is True
            assert review['case_facts']['school_session_day']['value'] is True
            civil_path = attempt / review['records']['civil_time']['path']
            source = json.loads(civil_path.read_text())
            source['civil_time_at_capture'] = civil
            civil_path.write_text(json.dumps(source) + '\n')
            digest = hashlib.sha256(civil_path.read_bytes()).hexdigest()
            review['records']['civil_time']['sha256'] = digest
            review['operation_clock']['civil_time_at_capture'] = civil
            review['operation_clock']['source_sha256']['civil_time'] = digest
            for fact in review['case_facts'].values():
                if 'civil_time' in fact['source_sha256']:
                    fact['source_sha256']['civil_time'] = digest
            verified = verified_sources(attempt, context)
            position = operation_window_position(verified['operation_clock'])
            assert position['position'] == expected, (name, position)
            assert position['lower'] == '2026-11-25T15:30:00-08:00'
            assert position['upper'] == '2026-11-26T07:30:00-08:00'
            if expected == 'interior':
                check_review(verified, 'exception_c')
                selected_gate = 'accepted_as_synthetic_interior'
            else:
                try:
                    check_review(verified, 'exception_c')
                except ValueError as error:
                    assert ('half-hour operation fact differs' in str(error) or
                            'legally unresolved half-hour endpoint' in str(error))
                    selected_gate = 'rejected_outside_or_unresolved_endpoint'
                else:
                    raise AssertionError('Selected exception (c) gate accepted non-interior time')
            rows.append({'probe': name, 'civil_time_at_capture': civil,
                         'position': position['position'],
                         'operation_ceases_at': review['operation_clock']['operation_ceases_at'],
                         'next_operation_begins_at': review['operation_clock']['next_operation_begins_at'],
                         'school_session_day': True, 'children_present': True,
                         'school_operation_source_sha256': review['records']['school_operation']['sha256'],
                         'civil_time_source_sha256': digest,
                         'source_verified': True,
                         'selected_exception_c_gate': selected_gate,
                         'legal_endpoint_interpretation': 'unresolved' if expected.startswith('at_') else 'not_at_endpoint'})
            if name == 'after_cessation_at':
                civil_path.write_text('{}\n')
                try:
                    verified_sources(attempt, context)
                except ValueError as error:
                    assert 'hash differs: civil_time' in str(error)
                else:
                    raise AssertionError('Changed civil-time source accepted')
    receipt = {'format': 'c263073-operation-boundary-cpu-v1',
               'synthetic_diagnostic_only': True, 'original_native_executed': False,
               'timestamp_resolution_s': 1,
               'half_hour_seconds': int(timedelta(minutes=30).total_seconds()),
               'changed_civil_source_rejected': True,
               'probes': rows}
    out = ROOT / 'proofs' / 'operation-boundary-cpu.json'
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'probes_passed': len(rows), 'receipt': str(out.relative_to(ROOT)),
                      'endpoint_legal_interpretation': 'unresolved'}))


if __name__ == '__main__':
    main()
