"""Exercise the pinned converter on 900 synthetic truck frames and four videos.

The nine-frame diagnostic is expanded in memory. This is a software duration
test on its template road, not a Native capture or evidence of truck pixels.
"""
import argparse
import copy
import hashlib
import json
import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
os.environ.setdefault('SCENARIO_PIPELINE_OUTPUT_ROOT',
                      str(REPO / '.runtime-work/c149237-full-converter-adapter-cache'))
sys.path[:0] = [str(REPO / 'runtime/scenario_pipeline'), str(REPO / 'runtime/python')]
from worker_exchange.fixture_generator import generate
from worker_exchange.package_compatibility import _process_fixture
from worker_exchange.common import sha, write

CASE = HERE.name + '__gap_below_500ft'
CAMERAS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def rows(value):
    return [json.loads(line) for line in value.splitlines() if line.strip()]


def dump(value):
    return ''.join(json.dumps(row, separators=(',', ':'), allow_nan=False) + '\n' for row in value)


def move_x(points, dx):
    for point in points:
        point[0] += dx


def expand(template):
    source = {name: rows(template['files'][name]) for name in
              ('capture/evidence.jsonl', 'capture/native/frames.jsonl',
               'trace.jsonl', 'video_frames.jsonl', 'truck_history.jsonl')}
    result = copy.deepcopy(template)
    for name in source:
        result['files'][name] = ''
    result['graphs'] = []
    result['videos'] = []
    generated = {name: [] for name in source}
    by_frame = {}
    for graph in template['graphs']:
        by_frame.setdefault(int(Path(graph['path']).stem), []).append(graph)
    first_frame = source['trace.jsonl'][0]['frame']
    for index in range(900):
        j = index % 9
        frame = first_frame + index
        time_s = round((index + 1) / 20, 8)
        dx = .6 * (index - j)
        evidence = copy.deepcopy(source['capture/evidence.jsonl'][j])
        evidence['original_frame'] = evidence['replay_frame'] = frame
        evidence['recording_time_s'] = time_s
        evidence['replay_simulation_time_s'] = time_s
        evidence['ego']['position_m'][0] += dx
        move_x(evidence['ego']['body_vertices_m'], dx)
        evidence['world']['road_projection']['s_m'] += dx
        observations = evidence['original_observations']
        observations['frame'] = frame
        observations['time_s'] = time_s
        for actor in observations['participants']:
            actor['position_m'][0] += dx
            move_x(actor['body_vertices_m'], dx)
        generated['capture/evidence.jsonl'].append(evidence)

        trace = copy.deepcopy(source['trace.jsonl'][j])
        trace['frame'] = frame
        trace['time_s'] = time_s
        trace['position']['x'] += dx
        trace['position_m'][0] += dx
        generated['trace.jsonl'].append(trace)

        mapping = copy.deepcopy(source['video_frames.jsonl'][j])
        mapping.update(video_frame=index, carla_frame=frame,
                       native_frame=frame, time_s=time_s)
        generated['video_frames.jsonl'].append(mapping)

        history = copy.deepcopy(source['truck_history.jsonl'][j])
        history.update(frame=frame, time_s=time_s)
        for role in ('ego', 'lead'):
            move_x(history[role]['body_vertices_xy_m'], dx)
        generated['truck_history.jsonl'].append(history)

        native = copy.deepcopy(source['capture/native/frames.jsonl'][j])
        native['frame'] = frame
        native['simulation_time'] = time_s
        for kind in ('abstract', 'base'):
            native[kind] = f'graphs/{kind}/{frame:08d}.pkl'
        generated['capture/native/frames.jsonl'].append(native)
        for graph_source in by_frame[source['trace.jsonl'][j]['frame']]:
            graph = copy.deepcopy(graph_source)
            kind = Path(graph['path']).parent.name
            graph['path'] = f'capture/native/graphs/{kind}/{frame:08d}.pkl'
            graph['attributes']['frame'] = frame
            graph['attributes']['simulation_time_s'] = time_s
            graph['attributes']['observed_evidence'] = observations
            if kind == 'base':
                for node in graph['nodes']:
                    if node['id'] == 'ego':
                        node['attributes']['vertex'][0] += dx
                        move_x(node['attributes']['threedbbox'], dx)
                        node['attributes']['original_observation'] = observations['participants'][0]
            result['graphs'].append(graph)
    for name, values in generated.items():
        result['files'][name] = dump(values)
    manifest = json.loads(result['files']['capture/manifest.json'])
    manifest['frames'] = 900
    manifest['sources']['trace.jsonl'] = hashlib.sha256(result['files']['trace.jsonl'].encode()).hexdigest()
    result['files']['capture/manifest.json'] = json.dumps(manifest, indent=2) + '\n'
    provenance = json.loads(result['files']['fixture-provenance.json'])
    provenance['full_duration_expansion'] = '900 synthetic frames, template road, repeated source-shaped graph pattern'
    result['files']['fixture-provenance.json'] = json.dumps(provenance, indent=2) + '\n'
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output-root', type=Path, required=True)
    parser.add_argument('--receipt', type=Path, required=True)
    args = parser.parse_args()
    root = args.output_root.resolve()
    if root.exists():
        raise ValueError('Use a fresh output root')
    root.mkdir(parents=True)
    fixture = root / 'fixture'
    fixture.mkdir()
    template = json.loads((HERE / 'diagnostic.json').read_text())
    generated = expand(template)
    generate(generated, fixture)
    full_video = REPO / '.runtime-work/c149237-full-duration-v14'
    for name in CAMERAS:
        shutil.copyfile(full_video / (name + '.mkv'), fixture / (name + '.mkv'))
    validator = REPO / '.runtime-work/c101303-decoder-b/.lake/build/bin/adapterCheck'
    receipt = _process_fixture(HERE / 'execution-manifest.json', CASE, fixture,
                               root / 'processed', REPO / 'runtime/library', validator)
    receipt.update(format='worker-full-duration-converter-cpu-proof', frames=900,
                   diagnostic_fixture=True, physical_acceptance_claimed=False,
                   generated_source_sha256=sha(fixture / 'capture/evidence.jsonl'),
                   source_template_sha256=sha(HERE / 'diagnostic.json'),
                   script_sha256=sha(Path(__file__)),
                   limitations=['template road, not authored truck OpenDRIVE',
                                'synthetic motion and color media; no Native capture or truck pixels'])
    write(args.receipt, receipt)
    print(json.dumps({'frames': 900, 'converter_passed': True,
                      'checks': receipt['checks'], 'physical_acceptance_claimed': False}))


if __name__ == '__main__':
    main()
