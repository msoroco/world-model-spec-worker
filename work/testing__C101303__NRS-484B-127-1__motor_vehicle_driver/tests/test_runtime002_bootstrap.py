"""CPU-only bootstrap isolation, immutability and concurrent-cache regressions."""
import contextlib
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

HELPER = Path(os.environ.get('WORKER_RUNTIME002_BOOTSTRAP',
    str(Path(__file__).resolve().parents[1] / 'runtime002_bootstrap.py'))).resolve()
module_spec = importlib.util.spec_from_file_location('migration_bootstrap_under_test', HELPER)
bootstrap = importlib.util.module_from_spec(module_spec); module_spec.loader.exec_module(bootstrap)


def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n')


RESOLVER = '''import hashlib,json,shutil\nfrom pathlib import Path\nROOT=Path(__file__).resolve().parent\ndef sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()\ndef effective_runtime():\n base=ROOT/'runtime/main-pipeline-v1';source=ROOT/'work/_shared/runtime-overlay';out=ROOT/'.runtime-work/overlay'\n counter=ROOT/'.runtime-work/materializations.txt';counter.parent.mkdir(exist_ok=True);counter.write_text(str(int(counter.read_text())+1 if counter.exists() else 1))\n if out.exists():shutil.rmtree(out)\n shutil.copytree(base,out);spec=json.loads((source/'overlay.json').read_text());files=json.loads((base/'SOURCE-MANIFEST.json').read_text())['files']\n for row in spec['files']:\n  shutil.copyfile(source/row['path'],out/row['path']);files[row['path']]=row['replacement_sha256']\n (out/'SOURCE-MANIFEST.json').write_text(json.dumps({'format':'worker-effective-runtime-v1','baseline_sha256':sha(base/'SOURCE-MANIFEST.json'),'overlay_sha256':sha(source/'overlay.json'),'files':files}))\n return out\n'''


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        self.old_path = list(sys.path)
        self.old_modules = {k:v for k,v in sys.modules.items() if k == 'overlay' or any(k == p or k.startswith(p + '.') for p in bootstrap.PACKAGES)}

    def tearDown(self):
        for name in list(sys.modules):
            if name == 'overlay' or any(name == p or name.startswith(p + '.') for p in bootstrap.PACKAGES): sys.modules.pop(name, None)
        sys.modules.update(self.old_modules); sys.path[:] = self.old_path

    def fixture(self, root):
        baseline = root/'runtime/main-pipeline-v1';source=root/'work/_shared/runtime-overlay'
        for relative,text in {
            'scenario_pipeline/worker_exchange/__init__.py':'"""baseline regular package"""\n',
            'scenario_pipeline/worker_exchange/common.py':"ORIGIN='baseline-common'\n",
            'scenario_pipeline/worker_exchange/saved_processing.py':"ORIGIN='baseline-saved'\n",
            'python/portable_helper.py':"VALUE=1\n"}.items():
            p=baseline/relative;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text)
        files={str(p.relative_to(baseline)):digest(p) for p in baseline.rglob('*') if p.is_file()}
        write(baseline/'SOURCE-MANIFEST.json',{'files':files})
        replacement=source/'scenario_pipeline/worker_exchange/saved_processing.py';replacement.parent.mkdir(parents=True,exist_ok=True);replacement.write_text("ORIGIN='repaired-saved'\n")
        write(source/'overlay.json',{'format':'worker-runtime-overlay-v1','baseline_sha256':digest(baseline/'SOURCE-MANIFEST.json'),'bootstrap_sha256':digest(HELPER),'files':[{'path':str(replacement.relative_to(source)),'baseline_sha256':files[str(replacement.relative_to(source))],'replacement_sha256':digest(replacement)}]})
        (root/'overlay.py').write_text(RESOLVER)
        write(root/'batch.json',{'runtime':{'root':'runtime/main-pipeline-v1','source_manifest_sha256':digest(baseline/'SOURCE-MANIFEST.json')},'frozen_files':{'overlay.py':digest(root/'overlay.py')}})
        (root/'runtime.py').write_text("import json\nfrom overlay import effective_runtime\nroot=effective_runtime()\nfrom worker_exchange import saved_processing\nprint(json.dumps({'origin':saved_processing.ORIGIN,'loaded_from':saved_processing.__file__,'batch_root':str(root.parents[1])}))\n")
        (root/'worker_check.py').write_text((root/'runtime.py').read_text())
        batch=json.loads((root/'batch.json').read_text());batch['frozen_files'].update({name:digest(root/name) for name in ('runtime.py','worker_check.py')});write(root/'batch.json',batch)
        return baseline

    def test_cached_baseline_package_is_rebound(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);baseline=self.fixture(root)
            for name in list(sys.modules):
                if any(name==p or name.startswith(p+'.') for p in bootstrap.PACKAGES):sys.modules.pop(name,None)
            sys.path.insert(0,str(baseline/'scenario_pipeline'))
            from worker_exchange import saved_processing
            self.assertEqual(saved_processing.ORIGIN,'baseline-saved')
            runtime=bootstrap.prepare_runtime(root);proof=bootstrap.activate_runtime(root,runtime)
            from worker_exchange import saved_processing as repaired
            self.assertEqual(repaired.ORIGIN,'repaired-saved')
            self.assertTrue(Path(repaired.__file__).is_relative_to(runtime));self.assertTrue(proof['immutable'])
            self.assertEqual(runtime.parents[1],root)

    def test_cached_runtime_materialized_once(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            first=bootstrap.prepare_runtime(root);second=bootstrap.prepare_runtime(root)
            self.assertEqual(first,second);self.assertEqual((root/'.runtime-work/materializations.txt').read_text(),'1')

    def test_concurrent_processes_share_immutable_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            code="import importlib.util,sys;from pathlib import Path;s=importlib.util.spec_from_file_location('b',sys.argv[1]);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);print(m.prepare_runtime(Path(sys.argv[2])))"
            processes=[subprocess.Popen([sys.executable,'-c',code,str(HELPER),str(root)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(3)]
            outputs=[p.communicate(timeout=60) for p in processes]
            self.assertTrue(all(p.returncode==0 for p in processes),outputs)
            self.assertEqual(len({out.strip() for out,_ in outputs}),1)
            self.assertEqual((root/'.runtime-work/materializations.txt').read_text(),'1')

    def test_mutated_immutable_source_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root);runtime=bootstrap.prepare_runtime(root)
            p=runtime/'scenario_pipeline/worker_exchange/saved_processing.py';p.write_text('tampered=True\n')
            with self.assertRaisesRegex(ValueError,'Immutable runtime source changed'):bootstrap.prepare_runtime(root)

    def test_mutated_replacement_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root)
            (root/'work/_shared/runtime-overlay/scenario_pipeline/worker_exchange/saved_processing.py').write_text('bad=True\n')
            with self.assertRaisesRegex(ValueError,'replacement source changed'):bootstrap.prepare_runtime(root)

    def test_frozen_launcher_resolves_selected_revision(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root);out=io.StringIO()
            with contextlib.redirect_stdout(out):self.assertEqual(bootstrap.main(['runtime.py'],repo=root),0)
            value=json.loads(out.getvalue());self.assertEqual(value['origin'],'repaired-saved');self.assertEqual(value['batch_root'],str(root))
            self.assertIn('/runtime002-',value['loaded_from'])

    def test_frozen_check_launcher_and_outside_script_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root);out=io.StringIO()
            with contextlib.redirect_stdout(out):self.assertEqual(bootstrap.main(['worker_check.py'],repo=root),0)
            self.assertEqual(json.loads(out.getvalue())['origin'],'repaired-saved')
            with self.assertRaisesRegex(ValueError,'Select the frozen'):bootstrap.main(['../outside.py'],repo=root)

    def test_missing_bootstrap_binding_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root);p=root/'work/_shared/runtime-overlay/overlay.json';spec=json.loads(p.read_text());spec.pop('bootstrap_sha256');write(p,spec)
            with self.assertRaisesRegex(ValueError,'Bootstrap source hash differs'):bootstrap.prepare_runtime(root)

    def test_mutated_frozen_launcher_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);self.fixture(root);(root/'runtime.py').write_text('tampered=True\n')
            with self.assertRaisesRegex(ValueError,'Selected launcher differs'):bootstrap.main(['runtime.py'],repo=root)


if __name__=='__main__': unittest.main()
