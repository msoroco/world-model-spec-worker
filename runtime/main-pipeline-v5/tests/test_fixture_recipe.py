import json
import tempfile
import unittest
from pathlib import Path
from worker_exchange.common import sha
from worker_exchange.fixture_recipe import materialize


class FixtureRecipeTests(unittest.TestCase):
    def test_text_addition_is_bound_and_regenerated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);base=root/'runtime/fixtures/base';base.mkdir(parents=True)
            (base/'trace.jsonl').write_text('{"frame":1}\n')
            for name in ('case.json','config.json','result.json'):(base/name).write_text('{}')
            addition=root/'work/case/scene-facts.jsonl';addition.parent.mkdir(parents=True)
            addition.write_text('{"centerline_x":0}\n')
            recipe=root/'work/case/fixture-recipe.json'
            recipe.write_text(json.dumps({'format':'worker-fixture-recipe-v1','base':'runtime/fixtures/base','remove':['case.json','config.json','result.json'],
                'additions':[{'path':'scene-facts.jsonl','source':'work/case/scene-facts.jsonl','sha256':sha(addition)}]}))
            result=materialize(root,recipe,root/'generated')
            self.assertTrue((root/'generated/scene-facts.jsonl').is_file())
            self.assertEqual(len(result['fixture_sha256']),64)
            addition.write_text('changed')
            with self.assertRaisesRegex(ValueError,'changed'):
                materialize(root,recipe,root/'second')


if __name__=='__main__':unittest.main()
