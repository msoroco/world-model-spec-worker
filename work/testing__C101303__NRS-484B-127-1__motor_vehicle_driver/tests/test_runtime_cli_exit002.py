"""Capture subprocess exit bookkeeping; fake process, no CARLA or server contact."""
import importlib.util,json,sys,tempfile,types,unittest
from pathlib import Path
from unittest import mock
ROOT=Path(__file__).resolve().parents[3]
OWNER=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'runtime/main-pipeline-v1/scenario_pipeline'))
import worker_exchange
from worker_exchange.common import read,write
spec=importlib.util.spec_from_file_location('exit_patch',OWNER/'runtime_cli_exit002_patch.py');patch=importlib.util.module_from_spec(spec);spec.loader.exec_module(patch)
module=types.ModuleType('worker_exchange.runtime_cli_exit_test');module.__package__='worker_exchange';module.__file__=str(ROOT/'work/_shared/runtime-overlay/scenario_pipeline/worker_exchange/runtime_cli.py');exec(compile(Path(module.__file__).read_text(),module.__file__,'exec'),module.__dict__)
# Exercise the actual repaired closure helper against fake files, independent of bootstrap mutation races.
spec=importlib.util.spec_from_file_location('worker_exchange.saved_processing_exit_test',ROOT/'work/_shared/runtime-overlay/scenario_pipeline/worker_exchange/saved_processing.py');saved=importlib.util.module_from_spec(spec);spec.loader.exec_module(saved)
class CaptureExitTests(unittest.TestCase):
 def fixture(self,path):
  path.mkdir();write(path/'construction.json',{'case_id':'fake'});(path/'runner.py').write_text('# fake Native runner\n')
 def execute(self,path,error=None,record=None):
  def fake_materialize(*args):return {'entrypoint':'runner.py'}
  outcomes=[mock.Mock(returncode=0),error or mock.Mock(returncode=0)]
  with mock.patch.object(module,'native_preflight',return_value={'fake':True}),mock.patch.object(module,'materialize',side_effect=fake_materialize),mock.patch.object(module.subprocess,'run',side_effect=outcomes),mock.patch.dict(sys.modules,{'worker_exchange.saved_processing':types.SimpleNamespace(record_native_exit=record or saved.record_native_exit)}):
   return module.capture('manifest.json','fake',path,'fake-host',1234,'fake-python')
 def test_failed_process_records_exit_and_preserves_same_exception(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'capture';self.fixture(p);write(p/'native-run-status.json',{'errors':[{'spawn':'failure'}]})
   error=module.subprocess.CalledProcessError(7,['fake-python','runner.py'])
   with self.assertRaises(module.subprocess.CalledProcessError) as raised:self.execute(p,error)
   self.assertIs(raised.exception,error);value=read(p/'native-exit.json');self.assertEqual(value['event'],'native_exit');self.assertEqual(value['native_process_exit_code'],7);self.assertTrue(value['capture_failed']);self.assertTrue(value['capture_command_failed'])
 def test_exit_receipt_failure_never_masks_original_process_failure(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'capture';self.fixture(p);error=module.subprocess.CalledProcessError(9,['fake'])
   with self.assertRaises(module.subprocess.CalledProcessError) as raised:self.execute(p,error,record=mock.Mock(side_effect=ValueError('unverified closure')))
   self.assertIs(raised.exception,error);self.assertEqual(read(p/'native-exit-feedback.json')['native_process_exit_code'],9);self.assertFalse((p/'native-exit.json').exists())
 def test_failed_process_without_status_keeps_nonzero_error_and_feedback(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'capture';self.fixture(p);error=module.subprocess.CalledProcessError(4,['fake'])
   with self.assertRaises(module.subprocess.CalledProcessError) as raised:self.execute(p,error)
   self.assertIs(raised.exception,error);self.assertTrue((p/'native-exit-feedback.json').is_file());self.assertFalse((p/'native-exit.json').exists())
 def test_success_records_zero_exit_only_after_ordered_seal(self):
  with tempfile.TemporaryDirectory() as t:
   p=Path(t)/'capture';self.fixture(p);write(p/'capture-seal.json',{'events':['capture_finished','encoders_closed','restoration_verified'],'native_revision':{'test':True}})
   result=self.execute(p);self.assertTrue(result['capture_executed']);value=read(p/'native-exit.json');self.assertEqual(value['native_process_exit_code'],0);self.assertFalse(value['capture_command_failed'])
if __name__=='__main__':unittest.main()
