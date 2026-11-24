"""Add source-hashed 600-frame CPU fixtures to the current roundabout drafts."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NATIVE = HERE / 'native'
OUT = HERE / 'v2-diagnostic'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_rows(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(''.join(json.dumps(row, separators=(',', ':')) + '\n' for row in rows))


def main():
    manifest_path = HERE / 'v2-offline-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    plan = json.loads((HERE / 'case-plan.json').read_text())
    proposals = HERE / 'proposals/cases.json'
    proposals.parent.mkdir(exist_ok=True)
    proposals.write_text(json.dumps({'cases': plan['cases']}, indent=2) + '\n')
    for entry in manifest['cases']:
        witness = entry['case_id'].rsplit('__', 1)[-1]
        folder = OUT / witness
        construction_path = folder / 'construction.json'
        construction = json.loads(construction_path.read_text())
        construction['files'] = [item for item in construction['files'] if item['path'] != 'finalize.py']
        construction['files'].append({'path': 'finalize.py',
                                      'content': (NATIVE / 'v2_finalize.py').read_text()})
        construction_path.write_text(json.dumps(construction, indent=2) + '\n')
        entry['construction_sha256'] = sha(construction_path)
        track = [json.loads(line) for line in (folder / 'source-track.jsonl').read_text().splitlines()]
        sources = folder / 'sources'
        sources.mkdir(exist_ok=True)
        (sources / 'roundabout-track.jsonl').write_bytes((folder / 'source-track.jsonl').read_bytes())
        trace, evidence, graph_rows, graphs, mapping = [], [], [], [], []
        for point in track:
            i = point['frame']
            time_s = point['time_s']
            x, y = point['ego_x_m'], point['ego_y_m']
            position = [x, y, 0.0]
            prior = track[max(0, i-1)]
            velocity = [(x-prior['ego_x_m'])*20, (y-prior['ego_y_m'])*20, 0.0]
            speed = (velocity[0]**2+velocity[1]**2)**.5
            body = [[x + dx, y + dy, dz] for dx in (-1, 1)
                    for dy in (-.4, .4) for dz in (-.5, .5)]
            trace.append({'frame': 1000 + i, 'time_s': time_s,
                'position': {'x': x, 'y': y, 'z': 0}, 'position_m': position,
                'heading_deg': point['ego_heading_deg'], 'velocity_mps': velocity,
                'speed_mps': speed, 'speed_mph': speed / .44704,
                'speed_provenance': 'synthetic_native_sample',
                'control': {'throttle': 0, 'brake': 0}})
            evidence.append({'original_frame': 1000 + i, 'recording_time_s': time_s,
                'replay_frame': 1000 + i, 'replay_simulation_time_s': time_s,
                'actor_id': 99,
                'ego': {'position_m': position, 'heading_deg': point['ego_heading_deg'],
                    'speed_mps': speed, 'velocity_mps': velocity,
                    'speed_provenance': 'synthetic_native_sample',
                    'body_vertices_m': body},
                'world': {'weather': {'cloudiness': 0, 'precipitation': 0,
                    'wetness': 0, 'fog_density': 0}}})
            graph_rows.append({'frame': 1000 + i, 'simulation_time': time_s,
                'adapter_graph': f'graphs/base/{1000+i:08d}.adapter.json',
                'base': f'graphs/base/{1000+i:08d}.adapter.json', 'nodes': 1, 'edges': 0})
            graphs.append({'path': f'capture/native/graphs/base/{1000+i:08d}.adapter.json',
                'attributes': {'frame': 1000+i, 'simulation_time_s': time_s,
                    'synthetic_diagnostic': True},
                'nodes': [{'id': 'ego', 'attributes': {'sem_class': 'car',
                    'entity_id': 99, 'vertex': position, 'forward': [1, 0, 0],
                    'threedbbox': body}}], 'edges': []})
            mapping.append({'video_frame': i, 'native_frame': 1000+i, 'carla_frame': 1000+i,
                'time_s': time_s})
        write_rows(sources / 'trace.jsonl', trace)
        write_rows(sources / 'capture/evidence.jsonl', evidence)
        write_rows(sources / 'capture/native/frames.jsonl', graph_rows)
        write_rows(sources / 'video_frames.jsonl', mapping)
        (sources / 'capture/recorder_info.txt').write_text('Create 99: vehicle.tesla.model3\n')
        (sources / 'capture/manifest.json').write_text(json.dumps({
            'extraction_confirmed': True, 'frames': 600,
            'sources': {'road.xodr': sha(NATIVE / 'left-exit-road.xodr'),
                        'trace.jsonl': sha(sources / 'trace.jsonl')},
            'synthetic_diagnostic': True}) + '\n')
        generator = folder / 'generator.json'
        generator.write_text(json.dumps({'files': {}, 'graphs': graphs,
            'videos': [{'path': name+'.mkv', 'frames': 600, 'width': width,
                'height': height, 'fps': 20, 'color': 'black'}
                for name, width, height in (('overview', 1920, 1080),
                    ('approach', 1280, 720), ('reference_corner', 1280, 720),
                    ('driver_reference', 1280, 720))]}, separators=(',', ':')) + '\n')
        items = []
        for item in sorted(sources.rglob('*')):
            if item.is_file():
                assert item.stat().st_size <= 2 * 1024 * 1024
                items.append({'path': str(item.relative_to(sources)),
                    'source': str(item.relative_to(ROOT)), 'sha256': sha(item)})
        recipe = folder / 'recipe.json'
        recipe.write_text(json.dumps({'format': 'worker-fixture-recipe', 'sources': items,
            'generator': {'source': str(generator.relative_to(ROOT)),
                          'sha256': sha(generator)}}, indent=2) + '\n')
        contract = folder / 'measurement-contract.json'
        contract.write_text(json.dumps({'format': 'worker-measurement-contract',
            'case_id': entry['case_id'], 'requirements': [{'disposition_index': 0,
                'requirement': 'LVMC-11-43-010-C1', 'source': 'LVMC 11.43.010(C)(1)',
                'output_key': 'lane_passage', 'method': 'measure', 'value_type': 'object',
                'kind': 'measured', 'inputs': ['roundabout-track.jsonl', 'video_frames.jsonl']}],
            'negative': {'remove': ['roundabout-track.jsonl'],
                'error_contains': 'Missing required source: roundabout-track.jsonl'}}, indent=2) + '\n')
        entry['measurement_contract'] = str(contract.relative_to(HERE))
        entry['measurement_procedure'] = {'entrypoint': 'finalize.py',
                                          'output_schema': 'c131364-saved-analysis-v2'}
        entry['fixture_recipe'] = str(recipe.relative_to(ROOT))
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'manifest_sha256': sha(manifest_path), 'cases': [
        {'case_id': e['case_id'], 'construction_sha256': e['construction_sha256']}
        for e in manifest['cases']]}))


if __name__ == '__main__':
    main()
