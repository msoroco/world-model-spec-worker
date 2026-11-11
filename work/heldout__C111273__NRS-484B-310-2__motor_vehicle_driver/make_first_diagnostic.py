"""Create a synthetic source-shaped flashing-yellow diagnostic, with no physical claim."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
repo = root.parents[1]
assignment = root.name
case_id = assignment + '__east_cautious_approach'
example = json.loads((repo/'runtime/fixtures/example.json').read_text())
frames = [json.loads(line) for line in example['files']['video_frames.jsonl'].splitlines() if line.strip()]
def series(rows):
    return ''.join(json.dumps(row, allow_nan=False)+'\n' for row in rows)
signals = []
parties = []
for index, fm in enumerate(frames):
    frame, time_s = fm['carla_frame'], fm['time_s']
    on = index < 4
    signals.append({'frame': frame, 'time_s': time_s,
        'light_actor_id': 37, 'opendrive_id': 'signal-test-1',
        'yellow_commanded': on, 'native_light_state': 'Yellow' if on else 'Off',
        'lens_pixel_visible': None})
    parties.append({'frame': frame, 'time_s': time_s,
        'ego': {'actor_id': 17, 'center_xy': [float(index), 0.0], 'speed_mps': 4.0},
        'crossing': {'actor_id': 18, 'center_xy': [3.0, float(index)], 'speed_mps': 6.0}})
example['files']['signal_state.jsonl'] = series(signals)
example['files']['participant_state.jsonl'] = series(parties)
example['files']['signal_context.json'] = json.dumps({
    'official_control_source': 'synthetic Native actor and OpenDRIVE premise; official status unverified',
    'selected_direction': 'east', 'opendrive_id': 'signal-test-1',
    'light_actor_id': 37, 'junction_id': 10, 'flash_period_s': .5,
    'lens_pixel_visibility': 'unverified', 'legal_caution_judgment': 'unresolved'})+'\n'
example['files']['fixture-provenance.json'] = json.dumps({
    'kind': 'textual CPU signal diagnostic', 'case_id': case_id,
    'physical_recording': False, 'law_or_canonical_acceptance': False})+'\n'
path = root/'diagnostic-input.json'
path.write_text(json.dumps(example, separators=(',', ':'))+'\n')
digest = hashlib.sha256(path.read_bytes()).hexdigest()
recipe = {'format': 'worker-fixture-recipe',
    'sources': [{'path': 'diagnostic-input.json',
        'source': str(path.relative_to(repo)), 'sha256': digest}],
    'generator': {'source': str(path.relative_to(repo)), 'sha256': digest}}
(root/'diagnostic-recipe.json').write_text(json.dumps(recipe, indent=2)+'\n')
contract = {'format': 'worker-measurement-contract', 'case_id': case_id,
    'requirements': [{'disposition_index': 0,
        'requirement': 'rapidly flashing illuminated yellow lens with official device and cautious passage',
        'source': 'NRS 484B.310(2) full text in inputs/'+assignment+'/assignment.json',
        'output_key': 'flashing_yellow', 'method': 'analyze',
        'value_type': 'object', 'kind': 'measured',
        'inputs': ['signal_context.json', 'signal_state.jsonl',
            'participant_state.jsonl', 'video_frames.jsonl', 'trace.jsonl']}],
    'negative': {'remove': ['signal_state.jsonl'],
        'error_contains': 'Missing required source: signal_state.jsonl'}}
(root/'first-measurement-contract.json').write_text(json.dumps(contract, indent=2)+'\n')
manifest_path = root/'execution-manifest.json'
manifest = json.loads(manifest_path.read_text())
entry = manifest['cases'][0]
entry['measurement_contract'] = 'first-measurement-contract.json'
entry['fixture_recipe'] = str((root/'diagnostic-recipe.json').relative_to(repo))
manifest_path.write_text(json.dumps(manifest, indent=2)+'\n')
print(path.stat().st_size)
