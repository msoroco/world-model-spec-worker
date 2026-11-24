"""Bind case-identified synthetic source fixtures and measurement contracts."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n')


def main():
    manifest_path = HERE / 'execution-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    basis_path = HERE / 'selected-reference-fixture.json'
    basis = json.loads(basis_path.read_text())
    basis_id = json.loads(basis['files']['acquisition-provenance.json'])['case_id']
    basis_contract = json.loads((HERE / 'selected-reference-measurement-contract.json').read_text())
    basis_recipe = json.loads((HERE / 'selected-reference-recipe.json').read_text())
    for entry in manifest['cases']:
        if '__judgment-' not in entry['case_id']:
            continue
        cid = entry['case_id']
        folder = HERE / 'sweep-cases' / cid
        spec = copy.deepcopy(basis)
        spec['files'] = {name: content.replace(basis_id, cid)
                         for name, content in spec['files'].items()}
        trace = [json.loads(line) for line in spec['files']['trace.jsonl'].splitlines()]
        evidence = [json.loads(line) for line in spec['files']['capture/evidence.jsonl'].splitlines()]
        if len(trace) != 600 or len(evidence) != 600:
            raise ValueError('Synthetic fixture lacks full source span')
        for row, event in zip(trace, evidence):
            if row['frame'] != event['original_frame']:
                raise ValueError('Synthetic route source frame differs')
            projection = event['world']['road_projection']
            row['route_position_m'] = projection['s_m']
            row['route_road_id'] = projection['road_id']
            row['route_section_id'] = projection['section_id']
            row['route_lane_id'] = projection['lane_id']
        spec['files']['trace.jsonl'] = ''.join(json.dumps(row, separators=(',', ':')) + '\n'
                                               for row in trace)
        capture_manifest = json.loads(spec['files']['capture/manifest.json'])
        capture_manifest['sources']['trace.jsonl'] = hashlib.sha256(
            spec['files']['trace.jsonl'].encode()).hexdigest()
        spec['files']['capture/manifest.json'] = json.dumps(capture_manifest, indent=2) + '\n'
        spec_path = folder / 'synthetic-source.json'
        write(spec_path, spec)
        if spec_path.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Sweep fixture exceeds returned file limit')
        recipe = copy.deepcopy(basis_recipe)
        recipe['generator']['source'] = str(spec_path.relative_to(ROOT))
        recipe['generator']['sha256'] = sha(spec_path)
        recipe_path = folder / 'fixture-recipe.json'
        write(recipe_path, recipe)
        contract = copy.deepcopy(basis_contract)
        contract['case_id'] = cid
        contract_path = folder / 'measurement-contract.json'
        write(contract_path, contract)
        entry['measurement_procedure'] = {'entrypoint': 'measure_episode.py',
                                          'output_schema': 'c229597-source-motion-analysis-v1'}
        entry['measurement_contract'] = str(contract_path.relative_to(HERE))
        entry['fixture_recipe'] = str(recipe_path.relative_to(ROOT))
        reference = next(case for case in manifest['cases'] if case['case_id'].endswith('__reference'))
        entry['acquisition'] = copy.deepcopy(reference['acquisition'])
        entry['acquisition']['route_position_m'] = {
            'entrypoint': 'measure_episode.py',
            'evidence': 'trace.jsonl, video_frames.jsonl, road.xodr',
            'method': 'original CARLA waypoint s and road identity joined to every ego frame'}
        entry['negative'] = {'log': None}
        entry['native_handoff'] = copy.deepcopy(reference['native_handoff'])
    write(manifest_path, manifest)
    print(json.dumps({'synthetic_sweep_fixtures': 6,
                      'basis_fixture_sha256': sha(basis_path),
                      'manifest_sha256': sha(manifest_path)}))


if __name__ == '__main__':
    main()
