"""Generate candidate-bound 900-frame comparison sources, strictly synthetic."""
import copy
import hashlib
import json
from pathlib import Path

folder = Path(__file__).resolve().parent
repo = folder.parent.parent
manifest = json.loads((folder / 'execution-manifest.json').read_text())
root = repo / '.runtime-work/c101303-fallback-projection-v1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def config(row):
    bundle = json.loads((folder / row['construction']).read_text())
    embedded = next(item['content'] for item in bundle['files'] if item['path'] == 'config.json')
    return json.loads(embedded)


def source_rows(entry):
    recipe = json.loads((repo / entry['fixture_recipe']).read_text())
    source = repo / recipe['generator']['source']
    if sha(source) != recipe['generator']['sha256']:
        raise ValueError('Diagnostic recipe source changed: ' + entry['case_id'])
    value = json.loads(source.read_text())
    rows = [json.loads(line) for line in value['files']['vehicle_history.jsonl'].splitlines() if line]
    if not rows or len(rows) > 900:
        raise ValueError('Missing compact source history')
    return source, rows


receipt = {'format': 'worker-fallback-candidate-source-projections',
           'scope': 'synthetic CPU comparison source only',
           'physical_fallback_motion_proven': False,
           'legal_judgment_claimed': False,
           'generator_sha256': sha(Path(__file__)), 'sources': []}
root.mkdir(parents=True, exist_ok=True)
for entry in manifest['cases']:
    label = entry['case_id'].rsplit('source_verified_', 1)[1]
    original_path, original = source_rows(entry)
    primary = config(entry)
    for candidate in entry['candidates']:
        name = candidate['id']
        changed = config(candidate)
        changed_config = {key: value for key, value in changed.items()
                          if primary.get(key) != value and key not in ('selected_case_id', 'supported_case_ids')}
        output = root / (label + '-' + name + '.jsonl')
        frame_zero = original[0]['frame']
        gap_delta = changed.get('requested_engineering_gap_m', 0) - primary.get('requested_engineering_gap_m', 0)
        speed_changed = changed.get('ego_target_speed_mps') != primary.get('ego_target_speed_mps')
        rows = []
        for index in range(900):
            row = copy.deepcopy(original[min(index, len(original) - 1)])
            row['frame'] = frame_zero + index
            row['time_s'] = round((index + 1) / 20, 6)
            if gap_delta:
                row['lead']['body_vertices_xy_m'] = [
                    [point[0] + gap_delta, point[1]] for point in row['lead']['body_vertices_xy_m']]
            if speed_changed:
                # Five moving samples keep the diagnostic body shift small; this
                # is an authored projection, never an observed CARLA trajectory.
                speed = changed['ego_target_speed_mps']
                moving = index < 5
                row['ego']['velocity_mps'] = [speed if moving else 0.0, 0, 0]
                row['ego']['speed_source'] = 'synthetic_candidate_projection'
                displacement = speed * min(index, 5) / 20
                row['ego']['body_vertices_xy_m'] = [
                    [point[0] + displacement, point[1]] for point in row['ego']['body_vertices_xy_m']]
            row['diagnostic_projection'] = {
                'candidate_id': name, 'construction_sha256': candidate['construction_sha256'],
                'changed_config': changed_config, 'physical_motion_proven': False}
            rows.append(row)
        output.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))
        receipt['sources'].append({
            'case_id': entry['case_id'], 'candidate_id': name,
            'construction_sha256': candidate['construction_sha256'],
            'source_specification': str(original_path.relative_to(repo)),
            'source_specification_sha256': sha(original_path),
            'changed_config': changed_config,
            'path': str(output.relative_to(repo)), 'sha256': sha(output), 'frames': 900})
    print('projected', label, 'three fallback comparison sources', flush=True)
(folder / 'fallback-candidate-source-receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
