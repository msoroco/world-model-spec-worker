"""Generate six textual Native-shaped variant fixtures from the owned bus recipe."""
import hashlib
import json
from pathlib import Path
from build_diagnostic import dumps, lines, update_position, hash_text
from variant_geometry import open_drive

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = ROOT / 'cases/designated_terminus/diagnostic.json'
VARIANTS = {
    'bus_stop': ('bus_stop', 5.0),
    'bus_stand': ('bus_stand', 5.0),
    'route_origin': ('route_origin', 5.0),
    'transient_stop': ('other_street', 40.0),
    'parking_other_street': ('other_street', 40.0),
    'tour_bus_other_street': ('other_street', 40.0),
}


def position(i, target, transient):
    if transient and i >= 145:
        extra = min(i - 145, 80) * .2
        return target + extra, 4.0 if i < 225 else 0.0
    return target - 20 + min(i, 100) * .2, 4.0 if i < 100 else 0.0


def main():
    for suffix, (kind, target) in VARIANTS.items():
        spec = json.loads(BASE.read_text())
        files = spec['files']
        road = open_drive(kind) + '\n'
        files['road.xodr'] = road
        zone_id = kind.replace('_', '-') + '-R1'
        zone = {'kind': kind, 'id': zone_id, 'route_id': 'R1'}
        if kind != 'other_street':
            zone['designation_source'] = {'path': 'road.xodr', 'sha256': hash_text(road)}
        context = json.loads(files['bus-context.json'])
        context.update(vehicle_class='tour_bus' if suffix == 'tour_bus_other_street' else 'route_bus_non_tour',
                       zone=zone, route_designation_source={
                         'candidate_reference': zone.get('designation_source'),
                         'official_authority_verified': False},
                       behavior_variant=suffix if suffix in ('transient_stop', 'parking_other_street') else 'standing',
                       native_lane_readback=[{'requested_x_m': target, 'road_id': 1,
                         'lane_id': -2, 'native_xy_m': [target, -5.25]}])
        files['bus-context.json'] = dumps(context) + '\n'
        history = [json.loads(line) for line in files['bus-history.jsonl'].splitlines()]
        transient = suffix == 'transient_stop'
        for i, row in enumerate(history):
            x, speed = position(i, target, transient)
            row.update(bus_speed_mps=speed,
                       parking_brake_applied=(100 <= i < 145 if transient else i >= 100),
                       driver_present=not (suffix == 'parking_other_street' and i >= 100),
                       occupied_zone_id=zone_id if abs(x - target) <= 5 else 'outside',
                       position_xyz_m=[x, -5.25, 1.0])
        files['bus-history.jsonl'] = lines(history)
        for name in ('trace.jsonl', 'capture/evidence.jsonl'):
            data = [json.loads(line) for line in files[name].splitlines()]
            for i, row in enumerate(data):
                x, speed = position(i, target, transient)
                update_position(row, x, speed)
            files[name] = lines(data)
        for i, graph in enumerate(spec['graphs']):
            x, speed = position(i, target, transient)
            update_position(graph, x, speed)
            graph['attributes']['source'] = 'C386410 exact variant software diagnostic'
        manifest = json.loads(files['capture/manifest.json'])
        manifest['sources'] = {'trace.jsonl': hash_text(files['trace.jsonl']),
                               'road.xodr': hash_text(road)}
        files['capture/manifest.json'] = dumps(manifest) + '\n'
        path = ROOT / 'cases' / suffix / 'diagnostic.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(spec, separators=(',', ':'), ensure_ascii=False) + '\n')
        source = str(path.relative_to(REPO))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'diagnostic-input.json', 'source': source, 'sha256': digest}],
                  'generator': {'source': source, 'sha256': digest}}
        (path.parent / 'recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')


if __name__ == '__main__':
    main()
