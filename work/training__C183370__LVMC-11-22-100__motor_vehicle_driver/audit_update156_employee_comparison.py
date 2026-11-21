"""Run the selected employee-pair diagnostic on current integrated sources."""
import hashlib
import json
from pathlib import Path

import audit_selected_same_cell_comparisons as comparison

HERE = Path(__file__).resolve().parent
for short in ('employee_exception_employee_crossing',
              'employee_exception_nonemployee_crossing'):
    comparison.SOURCE_LABELS[short] = 'update156-integrated'

result = comparison.audit('comparison_employee_exception')
target = HERE / 'update156-integrated-employee-comparison.json'
if target.exists():
    raise ValueError('Retain previous employee comparison')
target.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
print(json.dumps({'passed': result['passed'], 'diagnostic_only': result['diagnostic_only'],
                  'sha256': hashlib.sha256(target.read_bytes()).hexdigest()}, sort_keys=True))

try:
    comparison.audit('comparison_employee_exception', swapped=True)
except ValueError as error:
    negative = {'passed': True, 'rejection': str(error)}
else:
    raise AssertionError('Swapped employee sources were accepted')
negative_path = HERE / 'update156-integrated-employee-comparison-swapped-negative.json'
if negative_path.exists():
    raise ValueError('Retain previous employee comparison negative')
negative_path.write_text(json.dumps(negative, indent=2, sort_keys=True) + '\n')
print(json.dumps({'swapped_source_rejected': True,
                  'sha256': hashlib.sha256(negative_path.read_bytes()).hexdigest()}, sort_keys=True))
