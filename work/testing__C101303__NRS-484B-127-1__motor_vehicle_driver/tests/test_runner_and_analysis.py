import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import fixtures
import package_spec as P


def env():
    """Runtime helper packages come from PYTHONPATH (runtime.py sets it); else locate this clone's runtime."""
    paths = [str(HERE)]
    try:
        import worker_exchange  # noqa: F401
    except ImportError:
        root = next(p for p in HERE.parents if (p / 'runtime/scenario_pipeline').is_dir())
        paths += [str(root / 'runtime/scenario_pipeline'), str(root / 'runtime/python')]
    return dict(os.environ, PYTHONPATH=os.pathsep.join(paths + [os.environ.get('PYTHONPATH', '')]), PYTHONDONTWRITEBYTECODE='1')


class RunnerCheck(unittest.TestCase):
    def test_check_is_cpu_only_for_every_case(self):
        for variant in P.CASES:
            with tempfile.TemporaryDirectory() as d:
                (Path(d) / 'config.json').write_text(json.dumps(P.config_for(variant)))
                out = subprocess.run([sys.executable, str(HERE / 'runner.py'), '--check', '--output-dir', d], env=env(), capture_output=True, text=True)
                self.assertEqual(out.returncode, 0, out.stderr)
                self.assertFalse(json.loads(out.stdout)['carla_imported'])

    def test_check_rejects_a_changed_case_table(self):
        with tempfile.TemporaryDirectory() as d:
            config = P.config_for('base')
            config['case_parameters']['initial_gap_m'] = 3.0
            (Path(d) / 'config.json').write_text(json.dumps(config))
            out = subprocess.run([sys.executable, str(HERE / 'runner.py'), '--check', '--output-dir', d], env=env(), capture_output=True, text=True)
            self.assertNotEqual(out.returncode, 0)
            self.assertIn('frozen case table', out.stderr)


class Finalizer(unittest.TestCase):
    def run_analysis(self, d):
        return subprocess.run([sys.executable, str(HERE / 'analyze.py'), '--attempt', str(d), '--output', str(Path(d) / 'analysis-report.json')],
                              cwd=d, env=env(), capture_output=True, text=True)

    def test_fixture_measurements_for_all_cases(self):
        for variant in P.CASES:
            with tempfile.TemporaryDirectory() as d:
                fixtures.build(d, variant)
                out = self.run_analysis(d)
                self.assertEqual(out.returncode, 0, variant + out.stderr)
                report = json.loads((Path(d) / 'analysis-report.json').read_text())
                self.assertEqual(report['physical_checks']['maneuver']['status'], 'met', variant)
                self.assertEqual(set(report['measurements']), set(P.measurement_inputs()))
                result = json.loads((Path(d) / 'result.json').read_text())
                self.assertFalse(result['physical_acceptance_claimed'])
                self.assertTrue(report['measurements']['lane_change_route_crest']['value']['route_contains_crest_apex'], variant)
                self.assertNotIn('legal_verdict', result)

    def test_following_interval_distinguishes_following_ends(self):
        with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
            fixtures.build(a, 'base'), fixtures.build(b, 'following_ends')
            self.run_analysis(a), self.run_analysis(b)
            ia = json.loads((Path(a) / 'analysis-report.json').read_text())['measurements']['following_separation']['value']
            ib = json.loads((Path(b) / 'analysis-report.json').read_text())['measurements']['following_separation']['value']
            self.assertGreater(ib['max'], ia['max'] + 50)

    def test_missing_source_is_rejected_with_specific_error(self):
        with tempfile.TemporaryDirectory() as d:
            fixtures.build(d, 'base')
            (Path(d) / 'surface_context.json').unlink()
            out = self.run_analysis(d)
            self.assertNotEqual(out.returncode, 0)
            self.assertIn('Missing required source: surface_context.json', out.stderr)

    def test_no_lane_change_is_not_met(self):
        with tempfile.TemporaryDirectory() as d:
            fixtures.build(d, 'base')
            path = Path(d) / 'following_samples.jsonl'
            rows = [json.loads(l) for l in path.read_text().splitlines()]
            for r in rows:
                r['ego_lane_id'] = -1
            path.write_text(''.join(json.dumps(r) + '\n' for r in rows))
            out = self.run_analysis(d)
            self.assertNotEqual(out.returncode, 0)  # no lane change observed => lane_change_route refuses


if __name__ == '__main__':
    unittest.main()
