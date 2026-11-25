"""Selected package CPU assertions across three controlled meeting cases."""
import json
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE / 'native'))
from audit_three import audit


def test_selected_package():
    result = audit()
    assert result['frames'] == 600
    assert len(result['case_ids']) == 3
    assert result['right_passing_observed_each'] is True
    assert result['measured_available_fraction_to_oncoming'][-1] == 0.5
    assert result['measured_available_fraction_to_oncoming'][0] < 0.5
    assert result['legal_compliance'] == 'unassessed'
    manifest = json.loads((PACKAGE / 'execution-manifest.json').read_text())
    assert {case['case_id'] for case in manifest['cases']} == set(result['case_ids'])
    return {'passed': True, 'assertions': 7, 'selected_cases': 3,
            'legal_compliance': 'unassessed'}


if __name__ == '__main__':
    print(json.dumps(test_selected_package(), sort_keys=True))
