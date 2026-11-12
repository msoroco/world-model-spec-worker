"""Exercise the first exact-case measurement against retained diagnostic sources."""

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))

from finalizer import finalize
from worker_exchange.fixture_recipe import materialize
from worker_exchange.measurement_contract import validate, verify_report


def main():
    plan = json.loads((HERE / 'case-plan.json').read_text())
    contract = json.loads((HERE / 'measurement-contract.json').read_text())
    case_id = json.loads((HERE / 'config.json').read_text())['selected_case_id']
    validate(contract, plan['requirement_dispositions'],
             (HERE / 'finalizer.py').read_text(), case_id)
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work') as temporary:
        root = Path(temporary)
        positive = root / 'positive'
        materialize(REPO, HERE / 'diagnostic-recipe.json', positive)
        (positive / 'config.json').write_bytes((HERE / 'config.json').read_bytes())
        report = finalize(positive, positive / 'analysis-report.json')
        values = verify_report(contract, report, positive)
        physical = json.loads((positive / 'result.json').read_text())
        if (physical['physical_checks']['maneuver']['status'] != 'met'
                or physical['provenance_kind'] != 'synthetic_fixture'
                or physical['physical_acceptance_claimed'] is not False):
            raise ValueError('Synthetic full-body clearance proof differs')
        entry = values['slowness_before_entry']['value']
        if not (entry['first_body_entry'] and entry['closest_view_before_entry']
                and entry['sampled_slowness_before_entry']):
            raise ValueError('Diagnostic fixture lacks sampled slowing before full-body entry')
        interaction = values['through_interaction']['value']
        relation = values['yield_relation']['value']
        if not (interaction['ego_first_full_exit_frame']
                and interaction['through_present_frame_count'] == interaction['crossing_frame_count']
                and interaction['through_intersection_entry_frame']
                and relation['ego_first_body_entry_frame'] == interaction['ego_first_body_entry_frame']
                and relation['yield_judgment'] == 'unresolved'
                and relation['legal_adequacy_assessed'] is False):
            raise ValueError('Synthetic full-crossing through/yield relation differs')
        negative = root / 'negative'
        materialize(REPO, HERE / 'diagnostic-recipe.json', negative)
        (negative / 'config.json').write_bytes((HERE / 'config.json').read_bytes())
        (negative / contract['negative']['remove'][0]).unlink()
        try:
            finalize(negative, negative / 'analysis-report.json')
        except ValueError as error:
            if contract['negative']['error_contains'] not in str(error):
                raise
            failure = str(error)
        else:
            raise AssertionError('Missing source did not fail')
    print(json.dumps({'case_id': case_id, 'measurements': sorted(values),
                      'speed_at_closest_view_mps': values['speed_at_closest_view_mps']['value'],
                      'first_body_entry_frame': entry['first_body_entry']['frame'],
                      'ego_first_full_exit_frame': interaction['ego_first_full_exit_frame'],
                      'through_intersection_entry_frame': interaction['through_intersection_entry_frame'],
                      'synthetic_clearance_status': physical['physical_checks']['maneuver']['status'],
                      'negative_error': failure, 'scope': 'synthetic source protocol only'}))


if __name__ == '__main__':
    main()
