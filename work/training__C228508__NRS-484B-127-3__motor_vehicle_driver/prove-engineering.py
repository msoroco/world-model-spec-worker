"""Exercise the current exact-case construction policy without CARLA."""

import importlib.util
import json
import hashlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'native' / 'engineering.py'
spec = importlib.util.spec_from_file_location('c228508_engineering', SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class Actor:
    def __init__(self):
        self.commands = []

    def set_target_velocity(self, vector):
        self.commands.append(vector)


def vector_factory(**kwargs):
    return kwargs


observed = {}
for candidate in ('primary', 'fallback1'):
    for suffix in ('probe_a', 'probe_b'):
        key = suffix + '-' + candidate
        observed[key] = module.check(suffix, candidate)
        actors = {name: Actor() for name in ('lead', 'ego_combination', 'rear')}
        module.apply_group_command(actors, vector_factory, suffix, candidate)
        assert {a.commands[0]['x'] for a in actors.values()} == {module.CANDIDATES[candidate]}
        assert all(len(a.commands) == 1 for a in actors.values())

assert observed['probe_a-primary']['gap_target_m'] == observed['probe_a-fallback1']['gap_target_m']
assert observed['probe_b-primary']['gap_target_m'] == observed['probe_b-fallback1']['gap_target_m']
assert observed['probe_a-primary']['gap_target_m'] > observed['probe_b-primary']['gap_target_m']
assert observed['probe_a-primary']['group_speed_request_mps'] == observed['probe_b-primary']['group_speed_request_mps']
assert observed['probe_a-fallback1']['group_speed_request_mps'] == observed['probe_b-fallback1']['group_speed_request_mps']
assert observed['probe_a-primary']['group_speed_request_mps'] > observed['probe_a-fallback1']['group_speed_request_mps']

negative = {}
for name, action in {
    'unknown_case': lambda: module.plan('other'),
    'unknown_candidate': lambda: module.plan('probe_a', 'other'),
    'frame_overrun': lambda: module.commanded_centers('probe_a', 'primary', 600),
    'missing_group_actor': lambda: module.clear_spaces({'lead': 1, 'ego_combination': 0, 'rear': -1}),
    'overlap': lambda: module.clear_spaces({'lead': 0, 'ego_combination': 0, 'rear': 0, 'potential_entrant': 0}),
    'missing_command_actor': lambda: module.apply_group_command({'lead': Actor()}, vector_factory, 'probe_a', 'primary'),
}.items():
    try:
        action()
    except ValueError as error:
        negative[name] = str(error)
    else:
        raise AssertionError('Damaged construction accepted: ' + name)

proof = {'format': 'c228508-caravan-construction-policy-proof-v1',
         'engineering_sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
         'cases': observed, 'negative_rejections': negative,
         'selected_delivery_claimed': False, 'native_execution_claimed': False,
         'limitations': ['Authored 600-frame geometry and group velocity commands are CPU diagnostics only',
                         'Original Native bodies, combination coupling, independent caravan/region authority, cameras and entry safety remain unverified']}
output = ROOT / 'engineering-proof.json'
output.write_text(json.dumps(proof, indent=2) + '\n')
print(json.dumps({'proof_sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                  'candidate_paths': len(observed), 'negative_rejections': len(negative)}))
