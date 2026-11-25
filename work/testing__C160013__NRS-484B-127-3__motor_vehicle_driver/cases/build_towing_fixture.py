"""Make a source-hashed diagnostic combination fixture from the wide source."""
import hashlib
import json
import shutil
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
SOURCE = PACKAGE / 'cases/fixtures/wide'
TARGET = PACKAGE / 'cases/fixtures/towed'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def serialize(value):
    return json.dumps(value, separators=(',', ':')) + '\n'


def build():
    TARGET.mkdir(parents=True, exist_ok=True)
    recipe = json.loads((PACKAGE / 'cases/wide-recipe.json').read_text())
    for item in recipe['sources']:
        source = REPO / item['source']
        target = TARGET / item['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    design = PACKAGE / 'cases/towed_entrant_can_occupy_gap-construction.json'
    construction = json.loads(design.read_text())
    packet = json.loads(next(item['content'] for item in construction['files']
                             if item['path'] == 'site_packet.json'))
    relationship = {'drawing_actor_id': 1, 'drawn_actor_id': 8,
                    'drawn_unit_has_motive_power': False,
                    'towing_design_source_sha256': packet['towing_design_source']['sha256']}
    relation = TARGET / 'towing-relationship.json'
    relation.write_text(serialize(relationship))
    context_path = TARGET / 'road_context.json'
    context = json.loads(context_path.read_text())
    context['towing_relationship_source'] = {'path': relation.name,
                                              'sha256': sha(relation),
                                              'review_status': 'reviewed_native_relationship'}
    context['towing_design_source'] = packet['towing_design_source']
    context_path.write_text(serialize(context))
    history = TARGET / 'caravan_history.jsonl'
    rows = []
    for line in history.read_text().splitlines():
        row = json.loads(line)
        powered = next(member for member in row['caravan_members'] if member['actor_id'] == 1)
        row['drawn_units'] = [{'actor_id': 8, 'blueprint_id': 'static.prop.diagnostic_trailer',
                               'body_vertices_xy_m': [[x - 4, y] for x, y in powered['body_vertices_xy_m']]}]
        row['towing_relationship'] = {'drawing_actor_id': 1, 'drawn_actor_id': 8}
        rows.append(row)
    history.write_text(''.join(serialize(row) for row in rows))
    for item in recipe['sources']:
        item['source'] = str((TARGET / item['path']).relative_to(REPO))
        item['sha256'] = sha(TARGET / item['path'])
    recipe['sources'].append({'path': relation.name,
                              'source': str(relation.relative_to(REPO)), 'sha256': sha(relation)})
    (PACKAGE / 'cases/towing-recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')
    print(json.dumps({'fixture_files': len(recipe['sources']),
                      'history_frames': len(rows), 'recipe_sha256': sha(PACKAGE / 'cases/towing-recipe.json')}))


if __name__ == '__main__':
    build()
