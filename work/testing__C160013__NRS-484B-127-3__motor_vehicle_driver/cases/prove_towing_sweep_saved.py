"""Prove source-only observed and absent entry for exact towing sweep IDs."""
import hashlib
import json
import shutil
import sys
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
sys.path.insert(0, str(PACKAGE))
from caravan_towing_sweep_saved import finalize


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run():
    wide = REPO / '.runtime-work/c160013-towing-compat-v1'
    narrow = REPO / '.runtime-work/c160013-narrow-compat-v2'
    stage = REPO / '.runtime-work/c160013-towing-sweep-saved-narrow'
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    names = ('road_context.json', 'caravan_history.jsonl', 'video_frames.jsonl',
             'business_district_source.txt', 'caravan_membership_source.txt',
             'route_source.txt', 'lane_source.txt')
    for name in names:
        shutil.copyfile(narrow / name, stage / name)
    for name in ('towing-relationship.json', 'towing_design_source.txt'):
        shutil.copyfile(wide / name, stage / name)
    context_path = stage / 'road_context.json'
    context = json.loads(context_path.read_text())
    context['towing_relationship_source'] = {
        'path': 'towing-relationship.json', 'sha256': sha(stage / 'towing-relationship.json'),
        'review_status': 'reviewed_native_relationship'}
    context['towing_design_source'] = {
        'path': 'towing_design_source.txt', 'sha256': sha(stage / 'towing_design_source.txt')}
    context_path.write_text(json.dumps(context, indent=2) + '\n')
    history = stage / 'caravan_history.jsonl'
    rows = [json.loads(line) for line in history.read_text().splitlines()]
    for row in rows:
        powered = next(item for item in row['caravan_members'] if item['actor_id'] == 1)
        row['drawn_units'] = [{
            'actor_id': 8, 'blueprint_id': 'static.prop.diagnostic_trailer',
            'body_vertices_xy_m': [[x - 4, y] for x, y in powered['body_vertices_xy_m']]}]
        row['towing_relationship'] = {'drawing_actor_id': 1, 'drawn_actor_id': 8}
    history.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))
    absent = finalize(stage, 'caravan_spacing_towed_physical-0000',
                      drawing_actor_id=1, drawn_actor_id=8)
    observed = finalize(wide, 'caravan_spacing_towed_physical-0001',
                        drawing_actor_id=1, drawn_actor_id=8)
    middle_stage = REPO / '.runtime-work/c160013-towing-sweep-saved-middle'
    if middle_stage.exists():
        shutil.rmtree(middle_stage)
    middle_stage.mkdir(parents=True)
    for name in names + ('towing-relationship.json', 'towing_design_source.txt'):
        shutil.copyfile(wide / name, middle_stage / name)
    middle_history = middle_stage / 'caravan_history.jsonl'
    middle_rows = [json.loads(line) for line in middle_history.read_text().splitlines()]
    for row in middle_rows:
        for member in row['caravan_members']:
            shift = {1: 0, 2: -3.5, 3: -7}[member['actor_id']]
            member['body_vertices_xy_m'] = [[x + shift, y] for x, y in
                                            member['body_vertices_xy_m']]
        row['entering_vehicle']['body_vertices_xy_m'] = [
            [x - 1.75, y] for x, y in row['entering_vehicle']['body_vertices_xy_m']]
    middle_history.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n'
                                      for row in middle_rows))
    midpoint = finalize(middle_stage, 'caravan_spacing_towed_physical-0002',
                        drawing_actor_id=1, drawn_actor_id=8)
    if (absent['entry_observed'] is not False or observed['entry_observed'] is not True
            or midpoint['entry_observed'] is not True
            or any(item['original_frames'] != 900 for item in (absent, observed, midpoint))):
        raise ValueError('Exact saved sweep outcome changed')
    rows[0]['drawn_units'] = []
    history.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))
    try:
        finalize(stage, 'caravan_spacing_towed_physical-0000',
                 drawing_actor_id=1, drawn_actor_id=8)
    except ValueError as exc:
        if 'towing pair missing' not in str(exc):
            raise
        negative = str(exc)
    else:
        raise AssertionError('Missing original drawn body accepted')
    receipt = {'format': 'worker-towing-sweep-saved-diagnostic',
               'case_results': [absent, observed, midpoint],
               'missing_drawn_body_rejected': negative,
               'physical_acceptance_claimed': False,
               'legal_conclusion': 'unresolved'}
    (PACKAGE / 'cases/towing-sweep-saved-diagnostic.json').write_text(
        json.dumps(receipt, indent=2) + '\n')
    print(json.dumps({'case_count': 3, 'frames_per_case': 900,
                      'missing_drawn_body_rejected': True}))


if __name__ == '__main__':
    run()
