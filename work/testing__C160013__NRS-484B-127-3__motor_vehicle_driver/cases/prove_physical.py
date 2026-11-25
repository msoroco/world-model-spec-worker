"""Exercise pinned caravan physical preparation on text-only synthetic sources."""
import json
import os
import shutil
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
STAGE = REPO / '.runtime-work/c160013-physical-proof'


def run():
    output_root = Path(os.environ.get('SCENARIO_PIPELINE_OUTPUT_ROOT', '/')).resolve()
    if not output_root.is_relative_to(REPO / '.runtime-work'):
        raise ValueError('Export SCENARIO_PIPELINE_OUTPUT_ROOT under .runtime-work')
    from worker_exchange.native_output import assess_physical
    results = {}
    for suffix, source_name in (('entrant_can_occupy_gap', 'wide'),
                                ('entrant_cannot_occupy_gap', 'narrow')):
        stage = STAGE / suffix
        stage.mkdir(parents=True, exist_ok=True)
        source = REPO / '.runtime-work/c160013-comparison-proof' / source_name
        shutil.copyfile(source / 'video_frames.jsonl', stage / 'video_frames.jsonl')
        construction = json.loads((PACKAGE / 'cases' / (suffix + '-construction.json')).read_text())
        config = json.loads(next(item['content'] for item in construction['files']
                                 if item['path'] == 'config.json'))
        (stage / 'config.json').write_text(json.dumps(config) + '\n')
        (stage / 'caravan_context.json').write_text(json.dumps({'diagnostic': True}) + '\n')
        with (source / 'caravan_history.jsonl').open() as original, \
                (stage / 'caravan_history.jsonl').open('w') as history, \
                (stage / 'trace.jsonl').open('w') as trace:
            for line in original:
                row = json.loads(line)
                rear, front = row['caravan_members'][:2]
                entrant = row['entering_vehicle']
                y = sum(vertex[1] for vertex in entrant['body_vertices_xy_m']) / len(entrant['body_vertices_xy_m'])
                row['participants'] = {
                    'rear': {'actor_id': rear['actor_id'], 'body_vertices_m': rear['body_vertices_xy_m']},
                    'subject': {'actor_id': front['actor_id'], 'body_vertices_m': front['body_vertices_xy_m']},
                    'entrant': {'actor_id': entrant['actor_id'],
                                'body_vertices_m': entrant['body_vertices_xy_m'],
                                'lane_id': -1 if y > -1.5 else -2}}
                history.write(json.dumps(row) + '\n')
                trace.write(json.dumps({'frame': row['frame'], 'time_s': row['time_s']}) + '\n')
        positive = assess_physical(stage, config, [{'matched': True}])
        statuses = {key: positive['physical_checks'][key]['status']
                    for key in ('setup', 'target', 'maneuver')}
        if statuses != {'setup': 'met', 'target': 'met', 'maneuver': 'met'}:
            raise ValueError('Pinned physical preparation did not meet synthetic case: ' + str(statuses))
        missing = stage / 'caravan_context.json'
        missing.unlink()
        negative = assess_physical(stage, config, [{'matched': True}])
        if negative['physical_checks']['maneuver']['status'] != 'unverified':
            raise ValueError('Missing original caravan context was not rejected')
        results[suffix] = {'positive': statuses,
                           'missing_context': negative['physical_checks']['maneuver']['status'],
                           'synthetic_only': True,
                           'legal_conclusion': 'unresolved'}
    receipt = {'format': 'worker-c160013-physical-diagnostic',
               'results': results, 'physical_acceptance_claimed': False}
    (PACKAGE / 'cases/caravan-physical-diagnostic.json').write_text(json.dumps(receipt, indent=2) + '\n')
    print(json.dumps(receipt))


if __name__ == '__main__':
    run()
