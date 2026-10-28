"""Prepare software-only acquisition inputs from this checkout's retained diagnostic subset."""
import json
import math
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'work/_shared/fixtures/base-v3'
IDS = json.loads((ROOT / 'partitions/demo-test-02.json').read_text())['assignment_ids']


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def value(term, point, event, distance):
    if term == 'kin.position': return point['position_m']
    if term == 'kin.heading': return point['heading_deg']
    if term == 'kin.speed': return point['speed_mps']
    if term == 'kin.velocity': return point['velocity_mps']
    if term == 'kin.path_length': return distance
    if term == 'env.precipitation': return event['world']['weather']['precipitation']
    if term == 'env.wet_road': return event['world']['weather']['wetness']
    if term == 'sig.turn_indicator':
        bits = point['speed_comparison_native']['ego']['light_attributes']['vehicle_light_state']
        return {'frame': point['frame'], 'api_light_bits': bits,
                'source': 'retained diagnostic actor original light state; no right turn performed'}
    if term == 'sig.hand_signal':
        return {'frame': point['frame'], 'observed': False,
                'reason': 'retained diagnostic subset has no arm-signal acquisition'}
    if term in ('env.visibility', 'env.ice_or_snow'):
        return {'frame': point['frame'], 'value': None, 'verified': False,
                'source': 'retained source scene only; not transferred to new geometry'}
    if term.startswith(('st.', 'dev.')):
        return {'frame': point['frame'], 'native_projection': event['world'].get('road_projection'),
                'map_context': event['original_observations'].get('map_context'),
                'specific_term': term, 'new_scene_confirmed': False,
                'administrative_authority_confirmed': False}
    if term.startswith('rel.'):
        return {'frame': point['frame'], 'ego': event['ego'],
                'other': event['original_observations'].get('participants'),
                'new_case_relation_confirmed': False}
    if term.startswith('drv.'):
        return {'frame': point['frame'], 'ego': event['ego'],
                'other': event['original_observations'].get('participants'),
                'new_case_maneuver_confirmed': False}
    raise ValueError(term)


def main():
    if not BASE.is_dir():
        raise FileNotFoundError(BASE)
    for aid in IDS:
        folder = ROOT / 'work' / aid
        target = folder / 'fixture-diagnostic'
        if target.exists():
            raise FileExistsError('Retain earlier diagnostic source: ' + str(target))
        shutil.copytree(BASE, target)
        for prohibited in ('config.json', 'case.json', 'result.json', 'analysis-report.json', 'compatibility.json'):
            if (target / prohibited).exists():
                raise ValueError('Pinned base includes package output: ' + prohibited)
        trace, evidence = rows(target / 'trace.jsonl'), rows(target / 'capture/evidence.jsonl')
        if not trace or len(trace) != len(evidence):
            raise ValueError('Pinned retained trace/evidence inventory differs')
        names = [s['name'] for s in json.loads((folder / 'config.json').read_text())['case']['recording_description']['channels']]
        channels = target / 'channels'
        channels.mkdir(exist_ok=False)
        streams = {name: (channels / (name + '.jsonl')).open('x') for name in names}
        distance = 0.0
        prior = None
        try:
            for point, event in zip(trace, evidence):
                if point['frame'] != event['original_frame']:
                    raise ValueError('Original retained trace/evidence frame differs')
                if prior is not None:
                    distance += math.dist(prior, point['position_m'])
                prior = point['position_m']
                for name, stream in streams.items():
                    stream.write(json.dumps({'time_s': point['time_s'],
                        'value': value(name, point, event, distance)}) + '\n')
        finally:
            for stream in streams.values():
                stream.close()
        provenance = json.loads((target / 'fixture-provenance.json').read_text())
        provenance['partition02_adaptation'] = {
            'assignment_id': aid,
            'source': 'pinned runtime retained three-frame straight-road acquisition',
            'purpose': 'Software-only original frame/channel/analysis/validator/converter/video compatibility',
            'not_new_scene_evidence': True,
            'physical_motion_confirmed': False,
            'context': 'No intersection, divider, one-way sign, speed suitability, or right turn is established by these frames.',
            'channels': names,
        }
        (target / 'fixture-provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
        print(aid, len(trace), len(names))


if __name__ == '__main__': main()
