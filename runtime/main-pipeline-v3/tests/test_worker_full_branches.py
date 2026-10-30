import tempfile
import unittest
from pathlib import Path
from worker_exchange.common import write,sha
from worker_exchange.branch_coverage import validate,assignments

class FullBranchTests(unittest.TestCase):
 def test_empty_comparisons_are_rejected(self):
  with tempfile.TemporaryDirectory() as t:
   r=Path(t);aid='testing__C1__L1__driver';batch={'batch_id':'v7','assignments':{aid:{}}}
   write(r/'inputs/coverage/branch-sources.json',{'laws':{'L1':{'topics':{'text-0':{}}}}})
   write(r/'inputs'/aid/'assignment.json',{'law_id':'L1'})
   write(r/'work'/aid/'case-plan.json',{'cases':[{'case_id':'a'},{'case_id':'b'}],'comparisons':[]})
   write(r/'work/_shared/branch-coverage.json',{'format':'worker-full-branch-coverage-v1','batch_id':'v7','laws':{'L1':{'branches':[{'branch_id':'branch','topic_ids':['text-0'],'status':'runnable','assignment_id':aid,'case_ids':['a','b'],'comparison_ids':['missing']}]}}})
   with self.assertRaisesRegex(ValueError,'comparison'):validate(r,batch,batch['assignments'])
 def test_case_filtered_measurement_contract(self):
  from worker_exchange.measurement_contract import validate as check
  ds=[{'status':'selected_required','requirement':'a','source':'law','case_ids':['a']},{'status':'selected_required','requirement':'b','source':'law','case_ids':['b']}]
  c={'format':'worker-measurement-contract-v1','requirements':[{'disposition_index':0,'requirement':'a','source':'law','output_key':'position','method':'measure','value_type':'number','kind':'measured','inputs':['position.json']}],'negative':{'remove':['position.json'],'error_contains':'Missing required source: position.json'}}
  check(c,ds,'def measure(): pass','a')
  with self.assertRaises(ValueError):check(c,ds,'def measure(): pass','b')
