import json
import tempfile
import unittest
from pathlib import Path
from worker_exchange.common import sha
from worker_exchange.measurement_contract import validate,verify_report


class MeasurementContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.fixture=Path(self.tmp.name)
        (self.fixture/'road-geometry.json').write_text('{"centerline_x": 0}')
        self.dispositions=[{'status':'selected_required','requirement':'Approach relative to centerline','source':'law'},
                           {'status':'exception_pending','requirement':'officer','source':'law'}]
        self.contract={'format':'worker-measurement-contract-v1','requirements':[
            {'disposition_index':0,'requirement':'Approach relative to centerline','source':'law',
             'kind':'measured','method':'centerline_offset','value_type':'number',
             'output_key':'centerline_offset_m','inputs':['road-geometry.json']}],
             'negative':{'remove':['road-geometry.json'],'error_contains':'Missing required source: road-geometry.json'}}
        self.analysis='def centerline_offset(packet):\n return packet["centerline_x"]\n'
        self.report={'measurements':{'centerline_offset_m':{'method':'centerline_offset','value':2.1,
                     'sources':{'road-geometry.json':sha(self.fixture/'road-geometry.json')}}}}

    def test_valid_specific_measurement(self):
        validate(self.contract,self.dispositions,self.analysis)
        verify_report(self.contract,self.report,self.fixture)

    def test_speed_only_finalizer_rejected(self):
        with self.assertRaisesRegex(ValueError,'method/type'):
            validate(self.contract,self.dispositions,'def speed(packet): return 5\n')

    def test_placeholder_or_unbound_source_rejected(self):
        self.report['measurements']['centerline_offset_m']['value']=None
        with self.assertRaisesRegex(ValueError,'wrong type'):
            verify_report(self.contract,self.report,self.fixture)
        self.report['measurements']['centerline_offset_m']['value']=2.1
        self.report['measurements']['centerline_offset_m']['sources']['road-geometry.json']='0'*64
        with self.assertRaisesRegex(ValueError,'hash differs'):
            verify_report(self.contract,self.report,self.fixture)

    def test_negative_cannot_remove_generic_trace(self):
        self.contract['negative']={'remove':['trace.jsonl'],'error_contains':'Missing required source: trace.jsonl'}
        with self.assertRaisesRegex(ValueError,'case-specific'):
            validate(self.contract,self.dispositions,self.analysis)


if __name__=='__main__':unittest.main()
