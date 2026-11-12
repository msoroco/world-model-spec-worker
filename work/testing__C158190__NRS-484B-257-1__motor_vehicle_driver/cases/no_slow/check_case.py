"""Assert the exact no-slow contrast on original-shaped synthetic sources."""
import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parents[1]
REPO = WORK.parents[1]
sys.path.insert(0, str(WORK))
sys.path.insert(0, str(REPO / 'runtime/scenario_pipeline'))
from finalizer import finalize
from worker_exchange.fixture_recipe import materialize
from worker_exchange.measurement_contract import verify_report


def main():
    with tempfile.TemporaryDirectory(dir=REPO / '.runtime-work') as temporary:
        root = Path(temporary) / 'source'
        materialize(REPO, HERE / 'diagnostic-recipe.json', root)
        (root / 'config.json').write_bytes((HERE / 'config.json').read_bytes())
        report = finalize(root, root / 'analysis-report.json')
        values = verify_report(json.loads((WORK / 'measurement-contract.json').read_text()), report, root)
        result = json.loads((root / 'result.json').read_text())
        target = result['target_checks'][0]
        interaction = values['through_interaction']['value']
        slowness = values['slowness_before_entry']['value']
        if not (target['requested'] == target['measured'] == 6.0
                and target['matched']
                and not slowness['sampled_slowness_before_entry']
                and interaction['through_present_frame_count'] == interaction['crossing_frame_count']
                and interaction['ego_first_full_exit_frame']
                and values['yield_relation']['value']['yield_judgment'] == 'unresolved'):
            raise ValueError('Synthetic fixture does not realize no-slow contrast')
        print(json.dumps({'case_id': report['case_id'],
                          'nearest_view_speed_mps': target['measured'],
                          'sampled_slowness_before_entry': slowness['sampled_slowness_before_entry'],
                          'through_present_frame_count': interaction['through_present_frame_count'],
                          'ego_full_exit_frame': interaction['ego_first_full_exit_frame'],
                          'source_bound_measurements': len(values),
                          'legal_yield_judgment': 'unresolved',
                          'scope': 'synthetic source protocol only'}))


if __name__ == '__main__':
    main()
