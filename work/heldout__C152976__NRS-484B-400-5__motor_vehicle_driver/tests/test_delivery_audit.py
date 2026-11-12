import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
from delivery_audit import audit_attempt
from one_way_saved import analyze
import test_one_way_finalizer as source_fixture


class DeliveryAuditTests(unittest.TestCase):
    def fixture(self, root):
        source_fixture.SourceJoinTests().make_sources(root)
        case='heldout__C152976__NRS-484B-400-5__motor_vehicle_driver__left_edge_reference'
        (root/'config.json').write_text(json.dumps({'law_id':'NRS-484B-400-5',
            'cell_id':'C152976','actor':'motor_vehicle_driver','selected_case_id':case}))
        frames=[json.loads(line) for line in (root/'video_frames.jsonl').read_text().splitlines()]
        for name in ('native/footprints.jsonl','native/road_edges.jsonl'):
            rows=[json.loads(line) for line in (root/name).read_text().splitlines()]
            for row,frame in zip(rows,frames):row['time_s']=frame['time_s']
            (root/name).write_text(''.join(json.dumps(row)+'\n' for row in rows))
        (root/'trace.jsonl').write_text(''.join(json.dumps({'frame':r['carla_frame'],
            'time_s':r['time_s']})+'\n' for r in frames))
        for name in ('overview','approach','reference_corner','driver_reference'):
            (root/(name+'.mkv')).write_bytes(name.encode())
        return case, analyze(root)

    def test_independent_source_and_camera_audit(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp);case,report=self.fixture(path)
            calls=[]
            def decoder(source,count,**kw):
                calls.append(source.name)
                return {'frames':count}
            result=audit_attempt(path,report,case,decoder=decoder)
            self.assertEqual(len(calls),4)
            self.assertEqual(set(result['segment_minima_m']),{'approach','turn','departure'})
            self.assertEqual(result['checks']['actual_pixels'],'source_frames_decoded_only')

    def test_rejects_missing_original_and_stale_analysis(self):
        with TemporaryDirectory() as tmp:
            path=Path(tmp);case,report=self.fixture(path)
            (path/'native/road_edges.jsonl').unlink()
            with self.assertRaisesRegex(ValueError,'Missing audited original source'):
                audit_attempt(path,report,case,decoder=lambda *a,**k:{'frames':3})
            self.fixture_repair(path)
            case,report=self.fixture(path)
            rows=[json.loads(line) for line in (path/'native/footprints.jsonl').read_text().splitlines()]
            rows[0]['body_corners_xy'][0][0]+=1
            (path/'native/footprints.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in rows))
            with self.assertRaisesRegex(ValueError,'source inventory differs'):
                audit_attempt(path,report,case,decoder=lambda *a,**k:{'frames':3})

    def fixture_repair(self,path):
        for name in ('video_frames.jsonl','native/footprints.jsonl','native/road_edges.jsonl','site.json'):
            (path/name).unlink(missing_ok=True)
        (path/'native').rmdir()


if __name__=='__main__':unittest.main()
