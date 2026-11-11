import importlib.util
import json
from hashlib import sha256
from pathlib import Path
import sys
import tempfile
import unittest

folder = Path(__file__).resolve().parents[1]
repo = folder.parents[1]
sys.path.insert(0, str(repo / 'runtime/scenario_pipeline'))
from worker_exchange.fixture_recipe import materialize

spec = importlib.util.spec_from_file_location('stopped_comparison_audit',
                                               folder / 'stopped_comparison_audit.py')
audit_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit_module)
branch_spec = importlib.util.spec_from_file_location('fire_branch', folder / 'fire_branch.py')
branch = importlib.util.module_from_spec(branch_spec)
branch_spec.loader.exec_module(branch)


class StoppedComparisonTests(unittest.TestCase):
    def test_source_bound_distance_order_and_changed_original_rejection(self):
        with tempfile.TemporaryDirectory(prefix='c109514-stop-audit-', dir=repo / '.runtime-work') as temp:
            rows = []
            for target in (499, 500, 501):
                root = Path(temp) / str(target)
                materialize(repo, folder / 'cases' / f'stopped_drive_to_{target}ft' /
                            'diagnostic-recipe.json', root)
                context = json.loads((root / 'fire_context.json').read_text())
                measured = branch.measure_branch(root / 'participant_footprints.jsonl',
                                                 root / 'participant_state.jsonl', 9,
                                                 'stopped_drive_to', context)
                measure_path = root / 'measurement.json'
                measure_path.write_text(json.dumps(measured))
                rows.append({'case_id': folder.name + f'__stopped_drive_to_{target}ft',
                             'target_ft': target,
                             'measurement_path': str(measure_path),
                             'measurement_sha256': sha256(measure_path.read_bytes()).hexdigest(),
                             'participant_path': str(root / 'participant_footprints.jsonl'),
                             'state_path': str(root / 'participant_state.jsonl')})
            self.assertTrue(audit_module.audit(rows)['passed'])
            changed = Path(rows[2]['participant_path'])
            changed.write_text(changed.read_text().replace('"ego_id":"ego"',
                                                           '"ego_id":"changed"', 1))
            with self.assertRaisesRegex(ValueError, 'source hash mismatch'):
                audit_module.audit(rows)


if __name__ == '__main__':
    unittest.main()
