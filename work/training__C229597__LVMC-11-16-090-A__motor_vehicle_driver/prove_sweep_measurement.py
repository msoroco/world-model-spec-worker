"""Exercise exact sweep finalizer source joins without claiming Native realization."""
import copy
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'sweep-cases'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expect_failure(action, phrase):
    try:
        action()
    except ValueError as error:
        if phrase not in str(error):
            raise
    else:
        raise AssertionError('Required source rejection missing: ' + phrase)


def main():
    index = json.loads((OUT / 'index.json').read_text())
    construction = json.loads((HERE / index['entries'][0]['construction']).read_text())
    source = next(file['content'] for file in construction['files']
                  if file['path'] == 'measure_episode.py')
    namespace = {'__name__': 'sweep_finalizer_test'}
    exec(compile(source, '<exact-sweep-finalizer>', 'exec'), namespace)
    derive = namespace['derive']
    passed = []
    for name in ('reference', 'contrast'):
        spec = json.loads((HERE / f'selected-{name}-fixture.json').read_text())
        rows = lambda path: [json.loads(line) for line in spec['files'][path].splitlines()]
        trace = rows('trace.jsonl')
        mapping = rows('video_frames.jsonl')
        evidence = rows('capture/evidence.jsonl')
        for motion, event in zip(trace, evidence):
            if event['original_frame'] != motion['frame']:
                raise ValueError('Fixture evidence/native frame differs')
            projection = event['world']['road_projection']
            motion['route_position_m'] = projection['s_m']
            motion['route_road_id'] = projection['road_id']
        measurement = derive(trace, mapping)
        if (len(measurement['route_position_series_m']) != 600
                or len(measurement['acceleration_series_mps2']) != 600
                or measurement['route_road_ids'] != [1]):
            raise ValueError('Original source route/acceleration series incomplete')
        passed.append({'fixture': name,
                       'first_route_position_m': measurement['route_position_series_m'][0],
                       'last_route_position_m': measurement['route_position_series_m'][-1],
                       'maximum_longitudinal_acceleration_mps2': measurement['maximum_acceleration_mps2']})
        missing = copy.deepcopy(trace)
        del missing[1]['route_position_m']
        expect_failure(lambda: derive(missing, mapping), 'Missing original route projection')
        changed_road = copy.deepcopy(trace)
        changed_road[1]['route_road_id'] = 2
        expect_failure(lambda: derive(changed_road, mapping), 'Original route changed road identity')
        changed_frame = copy.deepcopy(mapping)
        changed_frame[1]['carla_frame'] += 1
        expect_failure(lambda: derive(trace, changed_frame), 'Original source frame/timestamp join differs')
        reversed_acceleration = copy.deepcopy(trace)
        reversed_acceleration[1]['acceleration_mps2'] = [-0.5, 0.0, 0.0]
        if derive(reversed_acceleration, mapping)['acceleration_series_mps2'][1] != -0.5:
            raise ValueError('Longitudinal acceleration sign lost')
    proof = {'format': 'c229597-exact-sweep-measurement-cpu-v1',
             'construction_sha256': sha(HERE / index['entries'][0]['construction']),
             'source_fixture_cases': passed, 'negative_checks_per_fixture': 4,
             'native_executed': False, 'physical_response_verified': False,
             'highway_status_verified': False, 'legal_verdict_claimed': False}
    path = OUT / 'measurement-proof.json'
    path.write_text(json.dumps(proof, indent=2) + '\n')
    print(json.dumps({'positive_cases': len(passed), 'negative_checks': 8,
                      'proof_sha256': sha(path)}))


if __name__ == '__main__':
    main()
