import json
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
REPO=ROOT.parents[1]
sys.path.insert(0,str(REPO/'runtime'))
sys.path.insert(0,str(REPO/'runtime/scenario_pipeline'))


class SemanticDraftTests(unittest.TestCase):
    def test_full_exact_stage_chain_bound_to_five_constructions(self):
        from scenario_pipeline.worker_exchange.semantic_delivery import validate
        assignment=json.loads((REPO/'inputs'/ROOT.name/'assignment.json').read_text())
        manifest=json.loads((ROOT/'execution-manifest.draft.json').read_text())
        receipt=validate(ROOT,assignment,manifest)
        self.assertEqual(receipt['stage_count'],6)
        self.assertEqual(receipt['selected_cases'],5)

    def test_changed_quote_and_missing_judgment_source_rejected(self):
        from batch_pipeline import stages
        assignment=json.loads((REPO/'inputs'/ROOT.name/'assignment.json').read_text())
        template=json.loads((ROOT/'proposals/template.json').read_text())
        template['quote']='invented law text'
        with self.assertRaisesRegex(ValueError,'quote is not exact'):
            stages.validate('template',template,{'request':{'law_id':assignment['law_id'],
                'actor':assignment['actor']},'law_record':assignment['law']})
        judgment=json.loads((ROOT/'proposals/judgment-entry-time.json').read_text())
        judgment['observable_requirements']['recording_needs']=[]
        with self.assertRaisesRegex(ValueError,'Missing judgment evidence'):
            stages.validate('judgment_observables',judgment,
                {'request':{'template_id':judgment['template_id'],'phrase':judgment['phrase'],
                            'note':judgment['note']}})


if __name__=='__main__':
    unittest.main()
