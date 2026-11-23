"""Make a synthetic, source-aligned graph for a recorded-only CPU check."""
import hashlib
import json
import shutil
from pathlib import Path

P = Path(__file__).resolve().parent
ROOT = P.parents[1]
SOURCE = ROOT / '.runtime-work/c229597-motion-finalizer-v5/positive'
TARGET = ROOT / '.runtime-work/c229597-saved-v7/attempt'
VIEWS = ('overview', 'approach', 'reference_corner', 'driver_reference')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, separators=(',', ':'), allow_nan=False) + '\n')


def main():
    TARGET.mkdir(parents=True, exist_ok=False)
    for name in ('construction.json', 'config.json', 'acquisition-provenance.json',
                 'video_frames.jsonl'):
        shutil.copy2(SOURCE / name, TARGET / name)
    shutil.copy2(ROOT / '.runtime-work/c229597-saved-v3-overview.mkv',
                 TARGET / 'overview.mkv')
    for name in VIEWS[1:]:
        shutil.copy2(ROOT / '.runtime-work/c229597-saved-v3-detail.mkv',
                     TARGET / (name + '.mkv'))
    trace = [json.loads(line) for line in (SOURCE / 'trace.jsonl').read_text().splitlines()]
    if len(trace) != 600:
        raise ValueError('Synthetic source has incomplete motion')
    for row in trace:
        row['speed_mph'] = row['speed_mps'] / .44704
    (TARGET / 'trace.jsonl').write_text(''.join(json.dumps(row, allow_nan=False) + '\n'
                                               for row in trace))
    road = ('<OpenDRIVE><header revMajor="1" revMinor="4" name="C229597-diagnostic" '
            'version="1" north="200" south="-200" east="200" west="-200" />'
            '<road id="1" name="straight-diagnostic" length="200" junction="-1">'
            '<link /><planView><geometry s="0" x="0" y="0" hdg="0" length="200">'
            '<line /></geometry></planView><elevationProfile><elevation s="0" a="0" '
            'b="0" c="0" d="0" /></elevationProfile><lanes><laneOffset s="0" '
            'a="0" b="0" c="0" d="0" /><laneSection s="0"><left />'
            '<center><lane id="0" type="none" level="false" /></center>'
            '<right><lane id="-1" type="driving" level="false"><width sOffset="0" '
            'a="3.5" b="0" c="0" d="0" /></lane></right></laneSection></lanes>'
            '<objects /><signals /></road></OpenDRIVE>\n')
    (TARGET / 'road.xodr').write_text(road)
    capture = TARGET / 'capture'
    (capture / 'native').mkdir(parents=True)
    (capture / 'recorder_info.txt').write_text('Create 107: vehicle.tesla.model3\n')
    with (capture / 'evidence.jsonl').open('w') as evidence, \
            (capture / 'native/frames.jsonl').open('w') as frames:
        for row in trace:
            frame, time_s = row['frame'], row['time_s']
            center = row['position_m']
            box = [[center[0] + dx, center[1] + dy, z]
                   for dx in (-2., 2.) for dy in (-.8, .8) for z in (0., 1.5)]
            graph = f'graphs/base/{frame:08d}.adapter.json'
            event = {'original_frame': frame, 'recording_time_s': time_s,
                     'replay_frame': frame, 'replay_simulation_time_s': time_s,
                     'actor_id': 107,
                     'ego': {'body_vertices_m': box, 'heading_deg': 0.,
                             'position_m': center, 'speed_mps': row['speed_mps'],
                             'speed_provenance': 'synthetic_native_sample'},
                     'world': {'road_projection': {'lane_id': -1, 'road_id': 1,
                                                   's_m': center[0], 'section_id': 0}},
                     'synthetic_diagnostic': True}
            evidence.write(json.dumps(event, separators=(',', ':')) + '\n')
            frames.write(json.dumps({'frame': frame, 'simulation_time': time_s,
                                     'adapter_graph': graph, 'base': graph,
                                     'nodes': 1, 'edges': 0}, separators=(',', ':')) + '\n')
            write(capture / 'native' / graph,
                  {'format': 'native-adapter-graph-v1', 'multigraph': False,
                   'metadata': {'frame': frame, 'simulation_time_s': time_s,
                                'synthetic_diagnostic': True},
                   'nodes': [{'id': 'ego', 'attributes': {'sem_class': 'ego',
                                                       'entity_id': 107, 'vertex': center,
                                                       'forward': [1, 0, 0],
                                                       'threedbbox': box}}],
                   'edges': []})
    config = json.loads((TARGET / 'config.json').read_text())
    write(capture / 'manifest.json',
          {'case_id': config['case_id'], 'frames': 600, 'extraction_confirmed': True,
           'synthetic_diagnostic': True,
           'sources': {'road.xodr': sha(TARGET / 'road.xodr'),
                       'trace.jsonl': sha(TARGET / 'trace.jsonl')}})
    print(json.dumps({'frames': len(trace), 'graph_files': len(trace),
                      'source_kind': 'synthetic_diagnostic'}))


if __name__ == '__main__':
    main()
