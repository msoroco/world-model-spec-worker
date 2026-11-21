"""Recheck all 48 final selected CPU diagnostic chains without writing output."""
import json

import audit_current_selected_48 as auditor

auditor.LABELS = {
    'reference': 'update157-finalchain-a',
    'contrast': 'update157-finalchain-a',
    'newly_laid_crossing': 'update157-finalchain-a',
    'barrier_crossing': 'update157-finalchain-b',
    'barrier_avoidance': 'update157-finalchain-b',
    'warning_sign_crossing': 'update157-finalchain-b',
    'warning_sign_avoidance': 'update157-finalchain-c',
    'highway_closed_sign_crossing': 'update157-finalchain-c',
    'highway_closed_sign_avoidance': 'update157-finalchain-c',
    'employee_exception_employee_crossing': 'update157-finalchain-d',
    'employee_exception_nonemployee_crossing': 'update157-finalchain-d',
    'newly_laid_avoidance': 'update157-finalchain-d',
}

result = auditor.audit(None)
assert result['selected_case_count'] == 12
assert result['candidate_count'] == 48
assert result['diagnostic_only'] is True
assert result['original_native_verified'] is False
print(json.dumps({'cases': 12, 'candidates': 48,
                  'manifest_sha256': result['manifest_sha256'],
                  'diagnostic_only': True}, sort_keys=True))
