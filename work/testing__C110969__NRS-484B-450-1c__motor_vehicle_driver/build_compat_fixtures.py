"""Create explicit source-shaped, strictly synthetic two-frame compatibility fixtures."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
BASE = REPO / 'work/testing__C109749__NRS-484B-253__motor_vehicle_driver/cases/inside_yield/diagnostic.json'


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n'


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def build():
    plan = json.loads((ROOT / 'case-plan.json').read_text())
    scaffold = json.loads(BASE.read_text())
    for case in plan['cases']:
        ident = case['case_id']
        suffix = ident.removeprefix(ROOT.name + '__')
        folder = ROOT / 'cases' / suffix
        files = {name: scaffold['files'][name] for name in (
            'capture/evidence.jsonl', 'capture/native/frames.jsonl',
            'capture/recorder_info.txt', 'road.xodr')}
        files['road.xodr'] = files['road.xodr'].replace('C150530', 'C110969 diagnostic')
        files['acquisition-provenance.json'] = encoded({'diagnostic_fixture': True,
            'provenance_kind': 'synthetic_fixture', 'source_scope': 'CPU software compatibility only'})
        inside = case['body_destination'] == 'inside'
        centers = [(-10.0, 0.0), (0.0, 0.0) if inside else (-9.0, 0.0)]
        def box(x, y):
            return [[x - 0.5, y - 0.5], [x + 0.5, y - 0.5],
                    [x + 0.5, y + 0.5], [x - 0.5, y + 0.5]]
        samples = [{'frame': i, 'time_s': i / 20, 'body_footprint': box(x, y),
                    'speed_mps': 1.0 if i == 0 else 0.0}
                   for i, (x, y) in enumerate(centers)]
        exception = case['exception_context']
        activity_samples = []
        for i in range(2):
            activity_samples.append({'frame': i, 'source_ref': f'diagnostic_frame:{i}',
                'activity_observation': {'requested': case['activity_intent'],
                                         'original_control': {'brake': 0.0 if i == 0 else 1.0},
                                         'legal_class': 'unresolved'},
                'traffic_conflict_observation': {'present': True, 'necessity': 'unresolved'} if exception == 'necessary traffic conflict' else None,
                'law_direction_observation': {'source': 'diagnostic', 'compliance': 'unresolved'} if exception == 'law direction' else None,
                'officer_direction_observation': {'source': 'diagnostic', 'compliance': 'unresolved'} if exception == 'police officer direction' else None,
                'device_direction_observation': {'source': 'diagnostic', 'compliance': 'unresolved'} if exception == 'official traffic-control-device direction' else None})
        boundary = {'diagnostic_fixture': True, 'map_id': 'C110969-synthetic-map',
                    'highway_status': 'reviewed_highway', 'joining_roadways': True,
                    'boundary_method': 'synthetic rectangle for software validation',
                    'intersection_polygon': [[-5, -5], [5, -5], [5, 5], [-5, 5]],
                    'source_refs': [{'source': 'diagnostic-only-rectangle', 'physical_review': False}]}
        trace = {'case_id': ident, 'native_run_id': 'synthetic-compat-' + suffix,
                 'map_id': boundary['map_id'], 'fps': 20, 'samples': samples,
                 'source_refs': [{'source': 'diagnostic-only-two-frame-trace'}]}
        activity = {'case_id': ident, 'native_run_id': trace['native_run_id'],
                    'activity_source': 'synthetic independent fixture observer',
                    'activity_samples': activity_samples,
                    'activity_observation': {'legal_class': 'unresolved'},
                    'traffic_conflict_observation': activity_samples[-1]['traffic_conflict_observation'],
                    'law_direction_observation': activity_samples[-1]['law_direction_observation'],
                    'officer_direction_observation': activity_samples[-1]['officer_direction_observation'],
                    'device_direction_observation': activity_samples[-1]['device_direction_observation'],
                    'source_refs': [{'source': 'diagnostic-only-activity'}]}
        for name, value in (('boundary.json', boundary), ('trace.json', trace), ('activity.json', activity)):
            files[name] = encoded(value)
        files['diagnostic-manifest.json'] = encoded({'diagnostic_fixture': True,
            'case_id': ident, 'native_run_id': trace['native_run_id'],
            **{key: {'path': key + '.json', 'sha256': digest(files[key + '.json'])}
               for key in ('boundary', 'trace', 'activity')}})
        trace_rows = [{'frame': i, 'time_s': i / 20,
                       'position': {'x': x, 'y': y, 'z': 0}, 'position_m': [x, y, 0],
                       'heading_deg': 0, 'speed_mps': samples[i]['speed_mps'],
                       'speed_mph': samples[i]['speed_mps'] * 2.2369362921,
                       'velocity_mps': [samples[i]['speed_mps'], 0, 0], 'control': {}}
                      for i, (x, y) in enumerate(centers)]
        evidence_rows = [json.loads(line) for line in files['capture/evidence.jsonl'].splitlines()]
        for i, evidence in enumerate(evidence_rows):
            x, y = centers[i]
            evidence['ego']['position_m'] = [x, y, 0]
            evidence['ego']['speed_mps'] = samples[i]['speed_mps']
            evidence['ego']['heading_deg'] = 0
            evidence['ego']['body_vertices_m'] = [[vx, vy, z] for vx, vy in box(x, y) for z in (-0.5, 0.5)]
        files['capture/evidence.jsonl'] = ''.join(encoded(row) for row in evidence_rows)
        files['trace.jsonl'] = ''.join(encoded(row) for row in trace_rows)
        files['video_frames.jsonl'] = ''.join(encoded({'carla_frame': i, 'native_frame': i,
            'video_frame': i, 'time_s': i / 20}) for i in range(2))
        files['capture/manifest.json'] = encoded({'acquisition': 'diagnostic_fixture',
            'case_id': ident, 'extraction_confirmed': True, 'frames': 2,
            'sources': {'road.xodr': digest(files['road.xodr']),
                        'trace.jsonl': digest(files['trace.jsonl'])}, 'status': 'draft'})
        spec = {'files': files, 'graphs': scaffold['graphs'],
                'videos': scaffold['videos']}
        spec_path = folder / 'diagnostic.json'
        spec_path.write_text(encoded(spec))
        note_path = folder / 'diagnostic-source-note.json'
        note_path.write_text(encoded({'case_id': ident, 'diagnostic_fixture': True,
            'physical_review': False, 'legal_conclusion': None,
            'note': 'Synthetic two-frame source-shaped compatibility fixture; not an official highway or actual exception.'}))
        recipe = {'format': 'worker-fixture-recipe', 'generator': {
            'source': str(spec_path.relative_to(REPO)), 'sha256': hashlib.sha256(spec_path.read_bytes()).hexdigest()},
            'sources': [{'path': 'diagnostic-source-note.json',
                         'source': str(note_path.relative_to(REPO)),
                         'sha256': hashlib.sha256(note_path.read_bytes()).hexdigest()}]}
        (folder / 'fixture-recipe.json').write_text(encoded(recipe))
    print('built nine source-shaped synthetic compatibility fixture recipes')


if __name__ == '__main__':
    build()
