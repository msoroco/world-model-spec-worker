"""Add converter-only synthetic frame joins to existing sealed yield fixtures.

The road, evidence and empty graphs below are CPU compatibility scaffolding.
They neither replace the sealed yield measurements nor show original traffic.
"""

import hashlib
import json
from pathlib import Path

from yield_view import CASES


ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
ROAD = '''<?xml version="1.0" encoding="UTF-8"?>
<OpenDRIVE>
  <header revMajor="1" revMinor="4" name="C157964 synthetic converter road" version="1" north="6" south="-6" east="80" west="-80" vendor="worker-diagnostic"/>
  <road name="synthetic converter road" length="160" id="157964" junction="-1">
    <link/>
    <planView><geometry s="0" x="-80" y="0" hdg="0" length="160"><line/></geometry></planView>
    <elevationProfile><elevation s="0" a="0" b="0" c="0" d="0"/></elevationProfile>
    <lateralProfile/>
    <lanes><laneOffset s="0" a="0" b="0" c="0" d="0"/>
      <laneSection s="0"><center><lane id="0" type="none" level="false"/></center>
        <left><lane id="1" type="driving" level="false"><width sOffset="0" a="5" b="0" c="0" d="0"/></lane></left>
        <right/>
      </laneSection>
    </lanes>
  </road>
</OpenDRIVE>
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def dump(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, separators=(',', ':')) + '\n')


def add(case):
    folder = ROOT / 'diagnostic-sources' / case.case_id
    rows = json.loads((folder / 'original-attempt/rows.json').read_text())
    assert len(rows) == 900
    road = folder / 'road.xodr'
    road.write_text(ROAD)
    recorder = folder / 'carla_recorder.log'
    recorder.write_text('Version: 1\nMap: OpenDriveMap\n'
                        ' Create 10: vehicle.tesla.model3 (0) at (0, 0, 0)\n')
    info = folder / 'capture/recorder_info.txt'
    info.parent.mkdir(parents=True, exist_ok=True)
    info.write_text(recorder.read_text())
    trace_path = folder / 'trace.jsonl'
    trace = [json.loads(line) for line in trace_path.read_text().splitlines()]
    assert len(trace) == len(rows)
    for row, item in zip(rows, trace):
        assert item['frame'] == row['original_frame']
        item['speed_mph'] = row['ego_speed_mps'] / .44704
    with trace_path.open('w') as stream:
        for item in trace:
            stream.write(json.dumps(item, sort_keys=True) + '\n')
    evidence_path = folder / 'capture/evidence.jsonl'
    frame_path = folder / 'capture/native/frames.jsonl'
    frame_path.parent.mkdir(parents=True, exist_ok=True)
    graphs = []
    with evidence_path.open('w') as evidence, frame_path.open('w') as frame_stream:
        for row in rows:
            frame = row['original_frame']
            time_s = row['time_s']
            speed = row['ego_speed_mps']
            evidence.write(json.dumps({
                'original_frame': frame, 'replay_frame': frame,
                'actor_id': 10, 'recording_time_s': time_s,
                'replay_simulation_time_s': time_s,
                'ego': {'position_m': [0, 0, 0], 'heading_deg': 0,
                        'speed_mps': speed,
                        'speed_provenance': 'synthetic_native_sample',
                        'body_vertices_m': [[-.2, -.2, 0], [.2, -.2, 0],
                                            [.2, .2, 0], [-.2, .2, 0]]},
                'world': {'weather': {}, 'road_projection': {}},
            }, sort_keys=True) + '\n')
            graph = f'graphs/base/{frame:08d}.adapter.json'
            frame_stream.write(json.dumps({
                'frame': frame, 'simulation_time': time_s,
                'adapter_graph': graph, 'nodes': 0, 'edges': 0,
            }, sort_keys=True) + '\n')
            graphs.append({'path': 'capture/native/' + graph,
                           'attributes': {'frame': frame, 'time_s': time_s},
                           'nodes': [], 'edges': []})
    manifest = {'status': 'draft', 'acquisition': 'synthetic_fixture',
                'case_id': ROOT.name + '__' + case.case_id,
                'source_run': 'synthetic_diagnostic_fixture',
                'map': 'OpenDriveMap', 'frames': 900,
                'required_observations': [], 'extraction_confirmed': True,
                'sources': {'road.xodr': sha(road),
                            'trace.jsonl': sha(trace_path),
                            'carla_recorder.log': sha(recorder)}}
    dump(folder / 'capture/manifest.json', manifest)
    spec_path = ROOT / ('diagnostic-fixture-spec-' + case.case_id + '.json')
    spec = json.loads(spec_path.read_text())
    spec['graphs'] = graphs
    dump(spec_path, spec)
    recipe_path = ROOT / ('diagnostic-fixture-recipe-' + case.case_id + '.json')
    recipe = json.loads(recipe_path.read_text())
    by_path = {entry['path']: entry for entry in recipe['sources']}
    for file in sorted(folder.rglob('*')):
        if file.is_file():
            relative = file.relative_to(folder).as_posix()
            by_path[relative] = {'path': relative,
                                 'source': file.relative_to(REPO).as_posix(),
                                 'sha256': sha(file)}
            assert file.stat().st_size <= 2 * 1024 * 1024, relative
    recipe['sources'] = [by_path[k] for k in sorted(by_path)]
    recipe['generator']['sha256'] = sha(spec_path)
    dump(recipe_path, recipe)
    return {'case_id': case.case_id, 'sources': len(by_path),
            'graphs': len(graphs), 'spec_size': spec_path.stat().st_size}


def main():
    print(json.dumps([add(case) for case in CASES], indent=2))


if __name__ == '__main__':
    main()
