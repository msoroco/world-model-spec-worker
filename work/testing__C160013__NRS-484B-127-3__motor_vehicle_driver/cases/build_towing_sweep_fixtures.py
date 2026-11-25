"""Build three distinct text-only synthetic source recipes for towing sweep CPU proofs."""
import hashlib
import json
import shutil
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = PACKAGE.parents[1]
BASE = PACKAGE / 'cases/fixtures'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build():
    template = json.loads((PACKAGE / 'cases/towing-recipe.json').read_text())
    relations = BASE / 'towed/towing-relationship.json'
    for i in range(3):
        source = BASE / ('narrow' if i == 0 else 'towed')
        target = BASE / ('towing_sweep_' + str(i))
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target)
        shutil.copyfile(relations, target / relations.name)
        context_path = target / 'road_context.json'
        context = json.loads(context_path.read_text())
        context['towing_relationship_source'] = {
            'path': relations.name, 'sha256': sha(target / relations.name),
            'review_status': 'reviewed_native_relationship'}
        construction = json.loads((PACKAGE / 'cases' /
            ('caravan_spacing_towed_physical-' + str(i).zfill(4) + '-construction.json')).read_text())
        site = json.loads(next(item['content'] for item in construction['files']
                               if item['path'] == 'site_packet.json'))
        context['towing_design_source'] = site['towing_design_source']
        context_path.write_text(json.dumps(context, separators=(',', ':')) + '\n')
        history = target / 'caravan_history.jsonl'
        rows = [json.loads(line) for line in history.read_text().splitlines()]
        for row in rows:
            if i == 2:
                for member in row['caravan_members']:
                    shift = {1: 0, 2: -3.5, 3: -7}[member['actor_id']]
                    member['body_vertices_xy_m'] = [[x + shift, y] for x, y in
                                                    member['body_vertices_xy_m']]
                row['entering_vehicle']['body_vertices_xy_m'] = [
                    [x - 1.75, y] for x, y in row['entering_vehicle']['body_vertices_xy_m']]
            if i in (0, 2):
                powered = next(member for member in row['caravan_members']
                               if member['actor_id'] == 1)
                row['drawn_units'] = [{
                    'actor_id': 8, 'blueprint_id': 'static.prop.diagnostic_trailer',
                    'body_vertices_xy_m': [[x - 4, y] for x, y in powered['body_vertices_xy_m']]}]
                row['towing_relationship'] = {'drawing_actor_id': 1, 'drawn_actor_id': 8}
        history.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))
        recipe = json.loads(json.dumps(template))
        if i == 0:
            recipe['generator'] = json.loads(
                (PACKAGE / 'cases/narrow-recipe.json').read_text())['generator']
        for item in recipe['sources']:
            path = target / item['path']
            if not path.is_file():
                raise ValueError('Missing exact synthetic source: ' + str(path))
            item['source'] = str(path.relative_to(REPO))
            item['sha256'] = sha(path)
        recipe_path = PACKAGE / 'cases' / ('towing-sweep-' + str(i) + '-recipe.json')
        recipe_path.write_text(json.dumps(recipe, indent=2) + '\n')
        print(json.dumps({'case_index': i, 'history_frames': len(rows),
                          'recipe_sha256': sha(recipe_path)}))


if __name__ == '__main__':
    build()
