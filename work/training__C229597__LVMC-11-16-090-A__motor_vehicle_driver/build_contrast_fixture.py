"""Create a distinct synthetic contrast source with lower motion response."""
import copy
import hashlib
import json
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
ASSIGNMENT = P.name


def sha_text(value):
    return hashlib.sha256(value.encode()).hexdigest()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(value):
    return [json.loads(line) for line in value.splitlines() if line.strip()]


def encoded(rows):
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n'
                   for row in rows)


def main():
    source = json.loads((P / 'selected-reference-fixture.json').read_text())
    spec = copy.deepcopy(source)
    files = spec['files']
    trace = lines(files['trace.jsonl'])
    evidence = lines(files['capture/evidence.jsonl'])
    x = 0.0
    for index, (motion, event, graph) in enumerate(zip(trace, evidence, spec['graphs'])):
        speed = 4.0 + index * .005
        if index:
            x += (speed + (4.0 + (index - 1) * .005)) / 40
        motion['position_m'] = [x, 0.0, 0.0]
        motion['position'] = {'x': x, 'y': 0.0, 'z': 0.0}
        motion['velocity_mps'] = [speed, 0.0, 0.0]
        motion['acceleration_mps2'] = [.1, 0.0, 0.0]
        motion['speed_mps'] = speed
        motion['speed_mph'] = speed / .44704
        box = [[x + dx, dy, z] for dx in (-2., 2.)
               for dy in (-.8, .8) for z in (0., 1.5)]
        event['ego']['position_m'] = [x, 0.0, 0.0]
        event['ego']['speed_mps'] = speed
        event['ego']['body_vertices_m'] = box
        event['world']['road_projection']['s_m'] = x
        graph['nodes'][0]['attributes']['vertex'] = [x, 0.0, 0.0]
        graph['nodes'][0]['attributes']['threedbbox'] = box
    files['trace.jsonl'] = encoded(trace)
    files['capture/evidence.jsonl'] = encoded(evidence)
    provenance = json.loads(files['acquisition-provenance.json'])
    provenance['case_id'] = ASSIGNMENT + '__contrast'
    files['acquisition-provenance.json'] = json.dumps(provenance, separators=(',', ':')) + '\n'
    capture = json.loads(files['capture/manifest.json'])
    capture['case_id'] = ASSIGNMENT + '__contrast'
    capture['sources']['trace.jsonl'] = sha_text(files['trace.jsonl'])
    files['capture/manifest.json'] = json.dumps(capture, separators=(',', ':')) + '\n'
    spec_path = P / 'selected-contrast-fixture.json'
    spec_path.write_text(json.dumps(spec, separators=(',', ':'), allow_nan=False) + '\n')
    recipe = json.loads((P / 'selected-reference-recipe.json').read_text())
    recipe['generator'] = {'source': spec_path.relative_to(ROOT).as_posix(),
                           'sha256': sha(spec_path)}
    (P / 'selected-contrast-recipe.json').write_text(json.dumps(recipe, indent=2) + '\n')
    contract = json.loads((P / 'selected-reference-measurement-contract.json').read_text())
    contract['case_id'] = ASSIGNMENT + '__contrast'
    (P / 'selected-contrast-measurement-contract.json').write_text(json.dumps(contract, indent=2) + '\n')
    manifest = json.loads((P / 'selected-reference-manifest.json').read_text())
    contrast = copy.deepcopy(json.loads((P / 'draft-primary-manifest.json').read_text())['cases'][1])
    contrast['measurement_contract'] = 'selected-contrast-measurement-contract.json'
    contrast['fixture_recipe'] = 'work/' + ASSIGNMENT + '/selected-contrast-recipe.json'
    manifest['cases'].append(contrast)
    manifest['status'] = 'selected_pair_cpu_in_progress'
    (P / 'selected-pair-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'frames': len(trace), 'contrast_speed_increase_mps': trace[-1]['speed_mps']-trace[0]['speed_mps'],
                      'spec_bytes': spec_path.stat().st_size, 'manifest_sha256': sha(P/'selected-pair-manifest.json')}))


if __name__ == '__main__':
    main()
