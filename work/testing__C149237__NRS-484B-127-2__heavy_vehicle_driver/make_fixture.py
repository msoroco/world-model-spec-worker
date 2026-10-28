"""Build a tiny acquisition-only software fixture from this trial's pinned subset."""
import json
import shutil
from pathlib import Path

import runner

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def main():
    source = REPO / 'work/_shared/fixtures/base-v3'
    target = ROOT / 'fixture-diagnostic'
    if target.exists():
        raise FileExistsError('Retain earlier fixture; choose a fresh target')
    shutil.copytree(source, target)
    for name in ('config.json', 'case.json', 'result.json', 'analysis-report.json', 'compatibility.json'):
        if (target / name).exists():
            raise ValueError('Pinned acquisition base supplied a package output: ' + name)
    config = json.loads((ROOT / 'config.json').read_text())
    trace, evidence = rows(target / 'trace.jsonl'), rows(target / 'capture/evidence.jsonl')
    if not trace or len(trace) != len(evidence):
        raise ValueError('Pinned original trace/evidence inventory differs')
    channel_root = target / 'channels'
    channel_root.mkdir(exist_ok=False)
    names = [channel['name'] for channel in config['case']['recording_description']['channels']]
    streams = {name: (channel_root / (name + '.jsonl')).open('x') for name in names}
    try:
        with (target / 'physical_samples.jsonl').open('x') as samples:
            for point, event in zip(trace, evidence):
                if point['frame'] != event['original_frame']:
                    raise ValueError('Pinned original source frame differs')
                observed_body = event['ego']['body_vertices_m']
                # The other actor is a synthetic diagnostic source record. It
                # tests full-body gap arithmetic, never a claimed CARLA run.
                synthetic_other = None
                if config['mode'] in ('signed_yield', 'signed_non_through', 'truck_follow'):
                    shift = 135.0
                    synthetic_other = {'actor_id': -100, 'blueprint':
                        'diagnostic.synthetic.truck' if config['mode'] == 'truck_follow' else
                        'diagnostic.synthetic.vehicle',
                        'position_m': [point['position_m'][0] + shift,
                                       point['position_m'][1], point['position_m'][2]],
                        'speed_mps': 0.0,
                        'body_vertices_m': [[v[0] + shift, v[1], v[2]] for v in observed_body],
                        'source_kind': 'diagnostic synthetic actor, not physical evidence'}
                sample_point = dict(point)
                sample_point['scenario_measurements'] = {
                    'bidirectional_sight': [{'direction': d, 'visible_at_probe': False,
                        'target_visible_by_ray': False, 'probe_distance_m': 152.4,
                        'source_kind': 'diagnostic synthetic finite ray'} for d in (-1, 1)],
                    'sampled_visible_range_m': 120.0,
                    'native_sign_inventory': [{'id': 'diagnostic-201',
                        'type': '205' if config['mode'] == 'signed_yield' else '206',
                        'road_id': 1, 's_m': 87.0,
                        'source_kind': 'diagnostic synthetic landmark; not native scene evidence'}]
                        if config['mode'] in ('signed_yield', 'signed_non_through') else []}
                values = runner.source_values(config, sample_point, event, 0,
                                              observed_body, synthetic_other, point['frame'])
                samples.write(json.dumps({'frame': point['frame'], 'time_s': point['time_s'],
                    'route_index': 0, 'ego_body_vertices_m': observed_body,
                    'other': synthetic_other, 'source_values': values}) + '\n')
                for name, stream in streams.items():
                    stream.write(json.dumps({'time_s': point['time_s'],
                                             'value': values[name]}) + '\n')
    finally:
        for stream in streams.values():
            stream.close()
    provenance = json.loads((target / 'fixture-provenance.json').read_text())
    provenance['partition03_adaptations'] = [
        'Retained pinned three-frame source is a straight-road diagnostic subset, not this scenario geometry.',
        'All scenario channels were generated before analysis from original trace/evidence and labeled synthetic actor/ray records.',
        'Synthetic counterpart and 120 m rays test arithmetic and joins only; no native sign, crosswalk, truck, curve, maneuver or legal outcome is established.']
    (target / 'fixture-provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')


if __name__ == '__main__':
    main()
