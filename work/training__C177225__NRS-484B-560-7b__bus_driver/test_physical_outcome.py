import json
import tempfile
import unittest
from pathlib import Path
from physical_outcome import ASSIGNMENT, assess

class PhysicalOutcomeTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write('acquisition-provenance.json', {'provenance_kind':'synthetic_fixture','diagnostic_fixture':True})
        self.write('officer_signal_definition.json', {'authorized':True,'bus_id':'bus-1','crossing_id':'crossing-1','direction':1,'first_governing_frame':1,'hand_signal':'STOP','issued_frame':0,'last_governing_frame':600,'officer_id':'officer-1'})
        self.bus = [{'native_frame':i,'actor_id':'bus-1','station_m':-30,'velocity_native_xyz_mps':[1,0,0]} for i in range(1,601)]
        self.officer = [{'native_frame':i,'actor_id':'officer-1','recipient_actor_id':'bus-1','crossing_id':'crossing-1','direction':1,'authorized':True,'hand_signal':'STOP','governing':True,'pose_control_applied':True,'pose_bone_readback':'crl_arm__R'} for i in range(1,601)]
        self.mapping = [{'native_frame':i,'carla_frame':i,'video_frame':i-1,'time_s':i/20} for i in range(1,601)]
        self.save_rows()
    def write(self,name,value):
        (self.root/name).write_text(json.dumps(value)+'\n')
    def save_rows(self):
        for name,rows in [('bus_native_rows.jsonl',self.bus),('officer_signal_rows.jsonl',self.officer),('video_frames.jsonl',self.mapping)]:
            (self.root/name).write_text(''.join(json.dumps(row)+'\n' for row in rows))
    def result(self,suffix):
        case=ASSIGNMENT+'__'+suffix
        self.write('config.json',{'case_id':case,'frames':600,'rate_hz':20})
        return assess(self.root,case)
    def test_incomplete_reference_and_contrast(self):
        for suffix in ('reference','contrast'):
            result=self.result(suffix)
            check=result['physical_checks']['maneuver']
            self.assertEqual(check['status'],'not_met')
            self.assertFalse(result['maneuver_completed'])
            self.assertIn('bus_native_rows.jsonl',check['sources'])
            self.assertEqual(result['provenance_kind'],'synthetic_fixture')
    def test_synthetic_success_remains_unverified(self):
        self.bus[250]['velocity_native_xyz_mps']=[0,0,0]
        self.save_rows()
        result=self.result('reference')
        self.assertEqual(result['physical_checks']['maneuver']['status'],'unverified')
        self.assertTrue(result['physical_checks']['maneuver']['observed_target'])
        self.assertFalse(result['maneuver_completed'])
        self.assertFalse(result['realized_observables'])
        self.bus[250]['velocity_native_xyz_mps']=[1,0,0]
        self.bus[350]['station_m']=10
        self.save_rows()
        result=self.result('contrast')
        self.assertEqual(result['physical_checks']['maneuver']['status'],'unverified')
        self.assertTrue(result['physical_checks']['maneuver']['observed_target'])
    def test_missing_and_mismatched_sources_unverified(self):
        self.result('reference')
        (self.root/'officer_signal_rows.jsonl').unlink()
        result=assess(self.root,ASSIGNMENT+'__reference')
        self.assertEqual(result['physical_checks']['maneuver']['status'],'unverified')
        self.assertIn('officer_signal_rows.jsonl',result['physical_checks']['maneuver']['missing_evidence'])
        self.mapping[17]['carla_frame']=999
        self.save_rows()
        self.assertEqual(self.result('reference')['physical_checks']['maneuver']['status'],'unverified')
    def test_native_marker_without_seal_unverified(self):
        self.write('acquisition-provenance.json',{'provenance_kind':'native','diagnostic_fixture':False})
        result=self.result('reference')
        self.assertEqual(result['physical_checks']['maneuver']['status'],'unverified')
        self.assertIn('capture-seal.json',result['physical_checks']['maneuver']['missing_evidence'])
if __name__=='__main__':unittest.main()
