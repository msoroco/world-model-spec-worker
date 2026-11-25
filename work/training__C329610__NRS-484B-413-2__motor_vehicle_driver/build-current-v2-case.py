"""Derive a current runtime synthetic fixture from one exact signal source."""
import argparse
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def write_rows(path, rows):
    path.write_text(''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in rows))


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + '\n')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(suffix):
    source = HERE / 'current-v2-case-sources' / suffix
    source.mkdir(parents=True, exist_ok=True)
    (source / 'capture').mkdir(exist_ok=True)
    raw = read_rows(HERE / 'signal-fixtures' / (suffix + '.jsonl'))
    base = HERE / 'current-v2-fixture'
    assert len(raw) == 800
    native = read_rows(base / 'native_samples.jsonl')
    trace = read_rows(base / 'trace.jsonl')
    evidence = read_rows(base / 'capture/evidence.jsonl')
    body_history = read_rows(base / 'body_history.jsonl')
    spec = json.loads((HERE / 'current-v2-fixture-spec.json').read_text())
    road = json.loads((base / 'road_geometry.json').read_text())
    road['area_classification'] = raw[0]['area']
    write_json(source / 'road_geometry.json', road)
    (source / 'road.xodr').write_bytes((base / 'road.xodr').read_bytes())
    (source / 'video_frames.jsonl').write_bytes((base / 'video_frames.jsonl').read_bytes())
    for i, row in enumerate(raw):
        x, y = row['ego_xy_m']
        angle = math.radians(row['heading_deg'])
        fx, fy = math.cos(angle), math.sin(angle)
        rx, ry = -fy, fx
        corners = [[x + u * fx + v * rx, y + u * fy + v * ry] for u, v in
                   ((-2.6, -1.1), (-2.6, 1.1), (2.6, 1.1), (2.6, -1.1))]
        body = [[a, b, z] for a, b in corners for z in (0, 1.5)]
        speed = 0.0 if i == 0 else math.dist(raw[i - 1]['ego_xy_m'], row['ego_xy_m']) * 20
        t = (i + 1) / 20
        native[i] = dict(row, time_s=t, native_frame=100 + i, native_center_xy_m=[x, y],
                         native_forward_xy=[fx, fy], native_body_xy_m=corners,
                         speed_mps=speed, light_state_bits=1 if row['signal'] == 'left' else 0,
                         left_indicator_state_observed=row['signal'] == 'left')
        trace[i]['position_m'] = [x, y, .5]
        trace[i]['position'] = {'x': x, 'y': y, 'z': .5}
        trace[i]['heading_deg'] = row['heading_deg']
        trace[i]['speed_mps'] = speed
        trace[i]['speed_mph'] = speed / .44704
        trace[i]['velocity_mps'] = [speed * fx, speed * fy, 0.0]
        evidence[i]['ego']['position_m'] = [x, y, .5]
        evidence[i]['ego']['body_vertices_m'] = body
        evidence[i]['ego']['heading_deg'] = row['heading_deg']
        evidence[i]['ego']['speed_mps'] = speed
        evidence[i]['world']['road_projection']['s_m'] = x + 120
        body_history[i]['body_vertices_m'] = body
        graph = spec['graphs'][i]
        node = graph['nodes'][0]['attributes']
        node['vertex'] = [x, y, .5]
        node['forward'] = [fx, fy, 0.0]
        node['threedbbox'] = body
    for name, rows in [('native_samples.jsonl', native), ('trace.jsonl', trace),
                       ('capture/evidence.jsonl', evidence), ('body_history.jsonl', body_history)]:
        write_rows(source / name, rows)
    manifest = json.loads((base / 'capture/manifest.json').read_text())
    manifest['sources'] = {'road.xodr': sha(source / 'road.xodr'),
                           'trace.jsonl': sha(source / 'trace.jsonl')}
    write_json(source / 'capture/manifest.json', manifest)
    spec_path = HERE / ('current-v2-' + suffix + '-spec.json')
    write_json(spec_path, spec)
    recipe = json.loads((HERE / 'current-v2-fixture-recipe.json').read_text())
    recipe['sources'] = [{'path': path, 'source': str((source / path).relative_to(ROOT)),
                          'sha256': sha(source / path)} for path in
                         ('road_geometry.json', 'trace.jsonl', 'video_frames.jsonl',
                          'native_samples.jsonl', 'body_history.jsonl', 'road.xodr',
                          'capture/evidence.jsonl', 'capture/manifest.json')]
    recipe['generator'] = {'source': str(spec_path.relative_to(ROOT)), 'sha256': sha(spec_path)}
    recipe_path = HERE / ('current-v2-' + suffix + '-recipe.json')
    write_json(recipe_path, recipe)
    construction = json.loads((HERE / 'draft-candidates' / suffix / 'primary/construction.json').read_text())
    current = json.loads((HERE / 'current-v2-below100-primary-construction.json').read_text())
    finalizer = next(item['content'] for item in current['files'] if item['path'] == 'finalize.py')
    next(item for item in construction['files'] if item['path'] == 'finalize.py')['content'] = finalizer
    construction_path = HERE / ('current-v2-' + suffix + '-primary-construction.json')
    write_json(construction_path, construction)
    contract = json.loads((HERE / 'draft-candidates' / suffix / 'measurement-contract.json').read_text())
    contract['format'] = 'worker-measurement-contract'
    contract['status'] = 'unselected_contract_draft'
    contract_path = HERE / ('current-v2-' + suffix + '-measurement-contract.json')
    write_json(contract_path, contract)
    print(json.dumps({'suffix': suffix, 'construction_sha256': sha(construction_path),
                      'recipe_sha256': sha(recipe_path), 'contract_sha256': sha(contract_path),
                      'spec_sha256': sha(spec_path)}, sort_keys=True))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('suffix', choices=['below_100_ft', 'at_100_ft', 'above_100_ft', 'below_300_ft',
                                           'at_300_ft', 'above_300_ft'])
    main(parser.parse_args().suffix)
