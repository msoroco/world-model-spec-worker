from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import sys
import unittest

folder = Path(__file__).resolve().parents[1]
root = folder.parents[1]
sys.path.insert(0, str(root / 'runtime/scenario_pipeline'))
from batch_pipeline import stages


class Tests(unittest.TestCase):
    def test_canonical_stage_contracts_and_source_bindings(self):
        proposal = folder / 'proposals'
        assignment = json.loads((root / 'inputs' / folder.name / 'assignment.json').read_text())
        index = json.loads((proposal / 'semantic-index.json').read_text())
        self.assertEqual(set(index['stages']), {'relevance_batch', 'relevance', 'template',
                                                'judgment_observables', 'bindings', 'cases'})
        for stage, ref in index['stages'].items():
            if stage == 'judgment_observables':
                self.assertEqual(ref, [])
                continue
            self.assertEqual(sha256((folder / ref['path']).read_bytes()).hexdigest(), ref['sha256'])
        law_id = assignment['law_id']
        actor = assignment['actor']
        request = {'cell': assignment['cell'], 'actor': actor}
        load = lambda name: json.loads((proposal / (name + '.json')).read_text())
        common = {'request': request, 'law_records': {law_id: assignment['law']}, 'dependencies': []}
        stages.validate('relevance_batch', deepcopy(load('relevance-batch')), common)
        stages.validate('relevance', deepcopy(load('relevance')), common)
        rules = json.loads((stages.ROOT / 'data/canonical_parameter_aliases.json').read_text())
        template = load('template')
        stages.validate('template', deepcopy(template),
                        {'request': {'law_id': law_id, 'actor': actor}, 'law_record': assignment['law'],
                         'canonical_parameter_rules': rules, 'dependencies': []})
        binding = load('bindings')
        stages.validate('bindings', deepcopy(binding),
                        {'request': dict(request, template_ids=[template['template_id']]),
                         'canonical_parameter_rules': rules, 'dependencies': [template]})
        cases = load('cases')
        stages.validate('cases', deepcopy(cases),
                        {'request': request, 'dependencies': [binding], 'templates': [template],
                         'canonical_parameter_rules': rules, 'judgment_completion_policy': {}})
        selected = {item['case_id'] for item in cases['cases'] if item['target_type'] != 'baseline'}
        plan = json.loads((folder / 'case-plan.json').read_text())
        self.assertEqual(selected, {item['case_id'] for item in plan['cases']})
        self.assertEqual(len(plan['comparisons']), 9)
