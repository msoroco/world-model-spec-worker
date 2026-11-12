"""Assert the exact through-entered branch on retained synthetic source frames."""
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
        interaction = values['through_interaction']['value']
        slowness = values['slowness_before_entry']['value']
        view = slowness['closest_view_frame']
        rows = [json.loads(line) for line in (root / 'video_frames.jsonl').read_text().splitlines()]
        first = rows[0]['carla_frame']
        from shapely.geometry import MultiPoint, Polygon
        polygon = Polygon(json.loads((root/'control_context.json').read_text())['intersection_xy_m'])
        bodies = [json.loads(line) for line in (root/'interaction_history.jsonl').read_text().splitlines()]
        by_frame = {row['frame']: row for row in bodies}
        def through_inside(frame):
            state = by_frame[frame]['through']
            return state is not None and MultiPoint(
                [(p[0], p[1]) for p in state['body_vertices_m']]
            ).convex_hull.intersects(polygon)
        if not (interaction['through_intersection_entry_frame'] == first
                and through_inside(view) and through_inside(first)
                and interaction['ego_first_body_entry_frame'] > view
                and interaction['ego_first_full_exit_frame']
                and values['yield_relation']['value']['yield_judgment'] == 'unresolved'):
            raise ValueError('Synthetic fixture does not realize through-entered branch at nearest view')
        print(json.dumps({'case_id': report['case_id'], 'first_original_frame': first,
                          'closest_view_frame': view,
                          'through_entry_frame': interaction['through_intersection_entry_frame'],
                          'ego_entry_frame': interaction['ego_first_body_entry_frame'],
                          'ego_full_exit_frame': interaction['ego_first_full_exit_frame'],
                          'source_bound_measurements': len(values),
                          'legal_yield_judgment': 'unresolved',
                          'scope': 'synthetic source protocol only'}))


if __name__ == '__main__':
    main()
