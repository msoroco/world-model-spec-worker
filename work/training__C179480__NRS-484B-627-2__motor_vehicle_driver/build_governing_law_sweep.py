"""Source-shaped control-phase samples; no legal-compliance judgment."""
import copy
import hashlib
import json
from pathlib import Path

from source_measurement import analyze_control
from control_phase_measurement import measure_red_onset

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'fixtures/law_required_stop-sources'
OUTPUT = HERE.parents[1] / '.runtime-work/c179480-governing-law-sweep'
ONSETS = (180, 220, 260)  # zero-based sample index, at 20 Hz


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def construct(rows, onset):
    if onset not in ONSETS:
        raise ValueError('Unreviewed control-phase onset')
    if len(rows) != 600 or any(row.get('source_kind') != 'synthetic_native_sample' for row in rows):
        raise ValueError('Expected 600 source-labeled diagnostic frames')
    output = copy.deepcopy(rows)
    light_id = None
    for i, (original, row) in enumerate(zip(rows, output)):
        control = original.get('governing_control_state')
        if (not isinstance(control, dict) or
                control.get('source_kind') != 'synthetic_native_sample' or
                control.get('control_state') != 'TrafficLightState.Red'):
            raise ValueError('Source control state missing or changed')
        ident = control.get('control_actor_id')
        if type(ident) is not int or (light_id is not None and ident != light_id):
            raise ValueError('Source control identity changed')
        light_id = ident
        state = 'TrafficLightState.Green' if i < onset else 'TrafficLightState.Red'
        row['governing_control_state']['control_state'] = state
        inventory = row.get('scene_actor_inventory', {}).get('actors', [])
        lights = [actor for actor in inventory if actor.get('actor_id') == ident]
        if len(lights) != 1 or lights[0].get('type_id') != 'traffic.traffic_light':
            raise ValueError('Source light inventory missing')
        lights[0]['state'] = state
        row['governing_control_state']['sweep_source_kind'] = 'synthetic_control_phase_probe'
        row['governing_control_state']['red_onset_sample'] = onset
    return output


def build():
    actor = SOURCE/'native-actors.jsonl'
    frame_map = SOURCE/'video_frames.jsonl'
    rows = [json.loads(line) for line in actor.read_text().splitlines()]
    light_id = json.loads((SOURCE/'native-map-readback.json').read_text())['surveyed_governing_traffic_light_id']
    probes = []
    for onset in ONSETS:
        folder = OUTPUT/('onset-'+str(onset))
        folder.mkdir(parents=True, exist_ok=True)
        sampled = folder/'native-actors.jsonl'
        sampled.write_text(''.join(json.dumps(row, separators=(',', ':'), allow_nan=False)+'\n'
                                   for row in construct(rows, onset)))
        mapping = folder/'video_frames.jsonl'
        mapping.write_bytes(frame_map.read_bytes())
        measured = analyze_control(sampled, mapping, expected_control_id=light_id,
                                   source_kind='synthetic_native_sample')
        phase = measure_red_onset(sampled, mapping, expected_control_id=light_id,
                                  source_kind='synthetic_native_sample')
        associated_red = measured['associated_red_frames']
        if (measured['sample_count'] != 600 or not associated_red or
                measured['compliance_with_law'] != 'independent_original_source_review_required' or
                phase['red_onset_sample'] != onset or phase['red_onset_s'] != onset/20 or
                phase['associated_red_frame_count'] != len(associated_red)):
            raise ValueError('Control probe lost the source question')
        probes.append({'red_onset_sample': onset, 'red_onset_s': onset/20,
                       'actor_source_sha256': sha(sampled), 'frame_map_sha256': sha(mapping),
                       'associated_red_frame_count': len(associated_red),
                       'first_associated_red_frame': associated_red[0],
                       'measured_red_onset_s': phase['red_onset_s'],
                       'compliance_with_law': measured['compliance_with_law']})
    if len({row['actor_source_sha256'] for row in probes}) != 3:
        raise ValueError('Control phases lack distinct source histories')
    return {'format': 'c179480-governing-law-engineering-probe-v1',
            'assignment_id': HERE.name, 'passed': True,
            'source_actor_sha256': sha(actor), 'source_frame_map_sha256': sha(frame_map),
            'sample_rate_hz': 20, 'duration_s': 30, 'probe_rows': probes,
            'original_native_observed': False, 'physical_or_legal_acceptance_claimed': False,
            'scope': 'synthetic light-phase samples; no legal applicability or compliance judgment'}


if __name__ == '__main__':
    print(json.dumps(build(), indent=2, sort_keys=True))
