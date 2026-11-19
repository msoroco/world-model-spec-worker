"""Build explicitly synthetic barrier source fixtures for CPU software proofs."""
import hashlib
import json

from build_diagnostic import PACKAGE, REPO, build, dump, lines


def variant(route):
    if route not in ('crossing', 'avoidance'):
        raise ValueError('Unknown barrier diagnostic route')
    base = build('reference' if route == 'crossing' else 'contrast')
    files = base['files']
    readback = json.loads(files['live-readback.json'])
    readback['plan']['control_kind'] = 'barrier'
    readback['plan']['cases'] = {
        'crossing': {'requested_pavement_crossing': True},
        'avoidance': {'requested_pavement_crossing': False}}
    readback['control_actor_id'] = readback.pop('warning_person_actor_id')
    readback['control_type_id'] = 'static.prop.trafficwarning'
    files['live-readback.json'] = json.dumps(readback, indent=2) + '\n'
    receipt = json.loads(files['capture-receipt.json'])
    receipt['case'] = route
    receipt['control_kind'] = 'barrier'
    receipt.pop('warning_act_verified', None)
    receipt['control_content_verified'] = False
    files['capture-receipt.json'] = json.dumps(receipt, indent=2) + '\n'
    actors = [json.loads(row) for row in files['native-actors.jsonl'].splitlines()]
    for actor in actors:
        actor['control_actor_id'] = actor.pop('warning_person_actor_id')
        actor['control_type_id'] = 'static.prop.trafficwarning'
        actor['control_xyz_m'] = actor.pop('warning_person_xyz_m')
    files['native-actors.jsonl'] = lines(actors)
    return base


def write():
    for route in ('crossing', 'avoidance'):
        folder = PACKAGE / 'variant-diagnostics' / 'barrier' / route
        folder.mkdir(parents=True, exist_ok=True)
        spec = folder / 'primary.json'
        spec.write_text(json.dumps(variant(route), separators=(',', ':')) + '\n')
        source = str(spec.relative_to(REPO))
        checksum = hashlib.sha256(spec.read_bytes()).hexdigest()
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-source.json',
                               'source': source, 'sha256': checksum}],
                  'generator': {'source': source, 'sha256': checksum}}
        (folder / 'primary-recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')


if __name__ == '__main__':
    write()
