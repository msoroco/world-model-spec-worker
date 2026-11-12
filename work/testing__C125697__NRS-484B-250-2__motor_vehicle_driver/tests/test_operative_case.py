"""CPU checks for the operative-device construction and diagnostic."""
import importlib.util
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace as NS

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

    def test_manifest_and_source_bound_proof(self):
        manifest = json.loads((HERE / 'execution-manifest.json').read_text())
        entry = next(row for row in manifest['cases'] if row['case_id'].endswith('__operative_signal'))
        self.assertEqual(entry['candidate_risk']['status'], 'physical')
        self.assertEqual(entry['candidates'], [])
        self.assertEqual(validate_candidates(HERE, entry, 'NRS-484B-250-2', 'C125697',
                                             required=False, require_alternate=False,
                                             candidate_count=1)['fallbacks'], [])
        receipt = json.loads((HERE / entry['compatibility']['receipt']).read_text())
        value = receipt['measurement_examples']['device_qualification_context']['value']
        self.assertTrue(value['all_sampled_states_operative'])
        self.assertEqual(value['official_device_exclusion_judgment'], 'unresolved')


if __name__ == '__main__':
    unittest.main()
