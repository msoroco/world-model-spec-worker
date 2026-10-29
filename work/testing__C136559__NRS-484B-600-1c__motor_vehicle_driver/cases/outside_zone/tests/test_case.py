import unittest,tempfile,pathlib,json,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]))
import analyze
class TestMeasurement(unittest.TestCase):
 def test_exact_measurement(self):
  with tempfile.TemporaryDirectory() as t:
   p=pathlib.Path(t)
   ctx={'posted_rate':30,'posted_unit':'mph','governed_direction_xy':[1,0],'governed_station_interval_m':[200,1800],'authority_asserted':True}
   (p/'posted_speed_context.json').write_text(json.dumps(ctx))
   for mph in (29,30,31):
    (p/'speed_samples.jsonl').write_text(json.dumps({'frame':1,'time_s':.05,'position_m':[300,0,0],'velocity_mps':[mph*.44704,0,0],'speed_mps':mph*.44704})+'\n')
    v=analyze.speed_history(p)
    self.assertEqual(bool(v['above_posted_30_mph_original_frames']),mph>30)
   ctx['governed_direction_xy']=[-1,0];(p/'posted_speed_context.json').write_text(json.dumps(ctx))
   self.assertEqual(analyze.speed_history(p)['zone_sample_count'],0)

 def test_exact_unit_conversion(self):
  from decimal import Decimal
  self.assertEqual(Decimal('30')*Decimal('.44704'),Decimal('48.28032')/Decimal('3.6'))

 def test_sign_orientation_and_units(self):
  import runner,xml.etree.ElementTree as ET
  cfg=json.loads((runner.ROOT/'config.json').read_text());cfg.update(governed_direction_xy=[-1,0],posted_rate=48.28032,posted_unit='km/h')
  sign=ET.fromstring(runner.authored_scene(cfg)).find('.//signal[@type="274"]')
  self.assertEqual(sign.get('orientation'),'-');self.assertEqual(sign.get('value'),'48.28032');self.assertEqual(sign.get('unit'),'km/h')
