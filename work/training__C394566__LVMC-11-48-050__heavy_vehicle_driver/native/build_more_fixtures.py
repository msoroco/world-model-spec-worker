"""Build bounded synthetic source fixtures for the remaining planned contrasts."""
import copy
import hashlib
import json
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1]
ROOT = FOLDER.parents[1]
AID = FOLDER.name
SOURCE = ROOT / 'work/training__C394566__LVMC-11-48-060__motor_vehicle_driver/diagnostic-probe_01.json'

VARIANTS = {
    'weight_below_8000': {'unladen_weight_lb': 7999},
    'weight_8000': {'unladen_weight_lb': 8000},
    'weight_above_8000': {'unladen_weight_lb': 8001},
    'other_district': {'district': 'other'},
    'residence_district': {'district': 'residence'},
    'time_1859': {'civil_timestamp': '2026-11-27T18:59:00-08:00'},
    'time_1901': {'civil_timestamp': '2026-11-27T19:01:00-08:00'},
    'time_0559': {'civil_timestamp': '2026-11-27T05:59:00-08:00'},
    'time_0601': {'civil_timestamp': '2026-11-27T06:01:00-08:00'},
    'permit_absent': {'written_permit_status': 'absent'},
    'permit_written': {'written_permit_status': 'present'},
    'permit_scope_match': {'written_permit_status': 'present', 'permit_scope_claim': 'matched'},
    'permit_scope_mismatch': {'written_permit_status': 'present', 'permit_scope_claim': 'mismatched'},
    'stationary': {'stationary': True},
    'moving': {'stationary': False},
}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build():
    original = json.loads(SOURCE.read_text())
    source_files = original['files']
    assignment = ROOT / 'inputs' / AID / 'assignment.json'
    for suffix, changes in VARIANTS.items():
        case = AID + '__' + suffix
        files = {name: value for name, value in source_files.items()
                 if name not in ('native_route_trace.jsonl', 'route_context.json')}
        files['capture/manifest.json'] = files['capture/manifest.json'].replace(
            'training__C394566__LVMC-11-48-060__motor_vehicle_driver__probe_01', case)
        maps = [json.loads(line) for line in files['video_frames.jsonl'].splitlines()]
        rows = []
        for line, frame in zip(source_files['native_route_trace.jsonl'].splitlines(), maps):
            row = json.loads(line)
            row.update(case_id=case, source_kind='original_native_pose', time_s=frame['time_s'],
                       vehicle_half_extent_m=[3.0, 1.2])
            if changes.get('stationary'):
                row.update(ego_x_m=0.0, ego_y_m=0.0, ego_speed_mps=0.0)
            rows.append(json.dumps(row, separators=(',', ':')))
        graphs = copy.deepcopy(original['graphs'])
        if changes.get('stationary'):
            trace = []
            for line in files['trace.jsonl'].splitlines():
                row = json.loads(line)
                row.update(position={'x': 0.0, 'y': 0.0, 'z': 0.0},
                           position_m=[0.0, 0.0, 0.0], speed_mps=0.0,
                           speed_mph=0.0, velocity_mps=[0.0, 0.0, 0.0])
                trace.append(json.dumps(row, separators=(',', ':')))
            files['trace.jsonl'] = '\n'.join(trace) + '\n'
            evidence = []
            for line in files['capture/evidence.jsonl'].splitlines():
                row = json.loads(line)
                row['ego']['position_m'] = [0.0, 0.0, 0.0]
                row['ego']['speed_mps'] = 0.0
                for participant in row['original_observations']['participants']:
                    if participant['actor_id'] == row['actor_id']:
                        participant['position_m'] = [0.0, 0.0, 0.0]
                        participant['velocity_mps'] = [0.0, 0.0, 0.0]
                        participant['speed_mps'] = 0.0
                evidence.append(json.dumps(row, separators=(',', ':')))
            files['capture/evidence.jsonl'] = '\n'.join(evidence) + '\n'
            for graph, observed_line in zip(graphs, evidence):
                observed = json.loads(observed_line)
                graph['attributes']['observed_evidence'] = observed['original_observations']
                for node in graph['nodes']:
                    if node.get('id') == 'ego':
                        node['attributes']['vertex'] = [0.0, 0.0, 0.0]
            capture = json.loads(files['capture/manifest.json'])
            capture['sources']['trace.jsonl'] = hashlib.sha256(files['trace.jsonl'].encode()).hexdigest()
            files['capture/manifest.json'] = json.dumps(capture, separators=(',', ':')) + '\n'
        assert len(rows) == len(maps) == 600
        files['original-route-rows.jsonl'] = '\n'.join(rows) + '\n'
        facts = {'unladen_weight_lb': 8001, 'district': 'residence', 'truck_route': False,
                 'civil_timestamp': '2026-11-27T20:00:00-08:00',
                 'written_permit_status': 'absent', 'permit_scope_claim': 'unverified'}
        facts.update({key: value for key, value in changes.items() if key != 'stationary'})
        refs = {}
        values = {'weight': facts['unladen_weight_lb'], 'district': facts['district'],
                  'truck_route': facts['truck_route'], 'civil_clock': facts['civil_timestamp'],
                  'permit': {'status': facts['written_permit_status'],
                             'scope_claim': facts['permit_scope_claim']}}
        for name, value in values.items():
            path = name + '.source.json'
            content = json.dumps({'source_kind': 'synthetic_diagnostic', 'fact': name,
                                  'requested_value': value}, sort_keys=True) + '\n'
            files[path] = content
            refs[name] = {'path': path, 'sha256': hashlib.sha256(content.encode()).hexdigest()}
        terms = {
            'ru.truck': {'source_kind': 'synthetic_diagnostic', 'vehicle_class': 'truck'},
            'ru.commercial_motor_vehicle': {'source_kind': 'synthetic_diagnostic', 'vehicle_class': 'heavy_vehicle'},
            'kin.extent': {'source_kind': 'synthetic_diagnostic', 'half_extent_m': [3.0, 1.2], 'certified_weight_separate': True},
            'st.roadway': {'source_kind': 'synthetic_diagnostic', 'road_id': json.loads(rows[0])['road_id']},
            'dev.regulatory_sign': {'source_kind': 'synthetic_diagnostic', 'truck_route_designation': facts['truck_route'], 'authority_separate': True},
            'env.civil_time': {'source_kind': 'synthetic_diagnostic', 'timestamp': facts['civil_timestamp']},
            'drv.condition_in_effect': {'source_kind': 'synthetic_diagnostic', 'clock_window_review_required': True},
            'kin.velocity': {'source_kind': 'synthetic_diagnostic', 'route_trace_required': True},
        }
        context = {'case_id': case, 'source_kind': 'synthetic_native_sample',
                   'authority_refs': refs, 'facts': facts, 'legal_verdict': None, **terms}
        files['authority-context.json'] = json.dumps(context, sort_keys=True) + '\n'
        protected = ('authority-context.json', 'original-route-rows.jsonl', 'video_frames.jsonl')
        seal = {'case_id': case, 'sha256': {name: hashlib.sha256(files[name].encode()).hexdigest()
                                           for name in protected}, 'physical_or_legal_accepted': False}
        files['capture-seal.json'] = json.dumps(seal, sort_keys=True) + '\n'
        specification = {'files': files, 'graphs': graphs, 'videos': original['videos']}
        out = FOLDER / ('diagnostic-' + suffix + '.json')
        out.write_text(json.dumps(specification, separators=(',', ':')) + '\n')
        if out.stat().st_size > 2 * 1024 * 1024:
            raise ValueError('Returned fixture exceeds 2 MiB: ' + suffix)
        recipe = {'format': 'worker-fixture-recipe',
                  'sources': [{'path': 'fixture-assignment.json',
                               'source': str(assignment.relative_to(ROOT)), 'sha256': sha(assignment)}],
                  'generator': {'source': str(out.relative_to(ROOT)), 'sha256': sha(out)}}
        (FOLDER / ('fixture-recipe-' + suffix + '.json')).write_text(json.dumps(recipe, indent=2) + '\n')
        print(suffix, out.stat().st_size)


if __name__ == '__main__':
    build()
