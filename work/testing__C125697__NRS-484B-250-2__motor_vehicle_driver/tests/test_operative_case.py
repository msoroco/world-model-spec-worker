"""CPU checks for the operative-device construction and diagnostic."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS
from unittest.mock import patch

HERE = Path(__file__).resolve().parents[1]
OUT = HERE / 'cases/operative_signal'
sys.path.insert(0, str(OUT))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / 'runtime'))
from scenario_pipeline.worker_exchange.candidate_constructions import validate as validate_candidates


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    loaded = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(loaded)
    return loaded


signal = module('operative_signal_control', OUT / 'signal_control.py')
finalizer = module('operative_finalizer', OUT / 'finalizer.py')
prior_signal = sys.modules.get('signal_control')
sys.modules['signal_control'] = signal
try:
    controlled = module('operative_controlled_pair', OUT / 'controlled_pair.py')
finally:
    if prior_signal is None:
        del sys.modules['signal_control']
    else:
        sys.modules['signal_control'] = prior_signal


class Light:
    def __init__(self, identifier, state='Yellow'):
        self.id, self.state, self.frozen = identifier, state, False

    def get_state(self):
        return self.state

    def set_state(self, state):
        self.state = state

    def freeze(self, value):
        self.frozen = value


class OperativeCase(unittest.TestCase):
    def test_red_green_extra_red_and_restoration(self):
        lights = [Light(17), Light(18), Light(19)]
        world = NS(tick=lambda: None)
        states = NS(Red='Red', Green='Green')
        with signal.request_operative(world, lights, states):
            self.assertEqual([light.state for light in lights], ['Red', 'Green', 'Red'])
            self.assertTrue(all(light.frozen for light in lights))
        self.assertEqual([light.state for light in lights], ['Yellow'] * 3)
        self.assertFalse(any(light.frozen for light in lights))

    def test_original_state_and_head_identity_required(self):
        diagnostic = json.loads((OUT / 'diagnostic.json').read_text())
        context = json.loads(diagnostic['files']['junction_context.json'])
        history = [json.loads(row) for row in diagnostic['files']['crossing_history.jsonl'].splitlines()]
        value = finalizer.measure_signal_context(context, history)
        self.assertEqual((value['ego_governing_state'], value['other_governing_state']), ('Red', 'Green'))
        history[1]['entrance_signal_states'][1]['state'] = 'Off'
        with self.assertRaisesRegex(ValueError, 'operative Red/Green'):
            finalizer.measure_signal_context(context, history)
        history[1]['entrance_signal_states'][1]['state'] = 'Green'
        history[1]['entrance_signal_states'][1]['actor_id'] = 99
        with self.assertRaisesRegex(ValueError, 'Stable distinct entrance head'):
            finalizer.measure_signal_context(context, history)

    def test_operative_head_order_rejects_reversed_entrance_inventory(self):
        plan = {'approaches': {'ego': {'road_id': 1, 'lane_id': -1},
                               'other': {'road_id': 2, 'lane_id': -1}}}
        site = {'native_map_name': 'TownX',
                'entrance_road_lanes': [[2, -1], [1, -1]]}
        world = NS(get_map=lambda: NS(name='TownX'))
        with patch.object(controlled, 'plan_pair', return_value=plan):
            with self.assertRaisesRegex(ValueError, 'map ego then other'):
                with controlled.construct_operational_pair(world, site, {}, None,
                                                           NS(Red='Red', Green='Green'), 'right'):
                    pass

    def test_manifest_and_source_bound_proof(self):
        manifest = json.loads((HERE / 'execution-manifest.json').read_text())
        entry = next(row for row in manifest['cases'] if row['case_id'].endswith('__operative_signal'))
        self.assertEqual(entry['candidate_risk']['status'], 'physical')
        self.assertEqual(validate_candidates(HERE, entry, 'NRS-484B-250-2', 'C125697',
                                             required=True, require_alternate=True,
                                             candidate_count=4)['fallbacks'],
                         ['fallback1', 'fallback2', 'fallback3'])
        receipt = json.loads((HERE / entry['compatibility']['receipt']).read_text())
        value = receipt['measurement_examples']['device_qualification_context']['value']
        self.assertTrue(value['all_sampled_states_operative'])
        self.assertEqual(value['official_device_exclusion_judgment'], 'unresolved')

    def test_fallbacks_preserve_operative_state_and_isolate_changes(self):
        manifest = json.loads((HERE / 'execution-manifest.json').read_text())
        entry = next(row for row in manifest['cases'] if row['case_id'].endswith('__operative_signal'))
        original = json.loads(next(item['content'] for item in
                                   json.loads((HERE / entry['construction']).read_text())['files']
                                   if item['path'] == 'config.json'))
        for candidate in entry['candidates']:
            cfg = json.loads(next(item['content'] for item in
                                  json.loads((HERE / candidate['construction']).read_text())['files']
                                  if item['path'] == 'config.json'))
            self.assertEqual(cfg['signal_mode'], 'operative_ego_red_other_green')
            ident = candidate['id']
            if ident == 'fallback1':
                self.assertEqual(cfg['site']['ego_approach'][0], -4)
                cfg['site']['ego_approach'] = original['site']['ego_approach']
                cfg['site']['routes']['ego'][0] = original['site']['routes']['ego'][0]
            elif ident == 'fallback2':
                self.assertNotEqual(cfg['site']['cameras']['approach'], original['site']['cameras']['approach'])
                cfg['site']['cameras']['approach'] = original['site']['cameras']['approach']
            else:
                self.assertEqual(cfg['other_release_frame'], 24)
                cfg['other_release_frame'] = original['other_release_frame']
            cfg.pop('site_review')
            fixed = dict(original)
            fixed.pop('site_review')
            self.assertEqual(cfg, fixed)


if __name__ == '__main__':
    unittest.main()
