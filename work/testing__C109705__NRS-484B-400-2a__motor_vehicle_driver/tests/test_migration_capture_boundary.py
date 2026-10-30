"""Static guard that Native capture cannot retain ownership for saved analysis."""
import ast
import unittest
from pathlib import Path

class CaptureBoundaryTests(unittest.TestCase):
    def runner(self):
        return ast.parse((Path(__file__).resolve().parents[1]/'runner.py').read_text())
    def test_live_capture_has_no_compose_or_finalize_call(self):
        tree=self.runner()
        run=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='run')
        calls=[n.func.id for n in ast.walk(run) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name)]
        self.assertNotIn('compose_four_views',calls)
        self.assertNotIn('finalize',calls)
        self.assertEqual(calls.count('seal_capture'),1)
    def test_seal_is_returned_after_guaranteed_cleanup(self):
        run=next(n for n in self.runner().body if isinstance(n,ast.FunctionDef) and n.name=='run')
        cleanup=next(n for n in run.body if isinstance(n,ast.Try))
        self.assertTrue(cleanup.finalbody)
        restoration=[n for n in ast.walk(cleanup) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='restore']
        seal=next(n for n in ast.walk(run) if isinstance(n,ast.Call) and isinstance(n.func,ast.Name) and n.func.id=='seal_capture')
        self.assertTrue(restoration)
        self.assertLess(max(n.lineno for n in restoration),seal.lineno)
        self.assertIsInstance(run.body[-1],ast.Return)
